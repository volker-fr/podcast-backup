"""Episode processing logic for podcast backup."""

import os
import uuid
from datetime import datetime, timedelta
from typing import Optional, Tuple

from .downloader import download_mp3, get_remote_file_info
from .metadata import MetadataManager
from .rss import save_episode_rss
from .utils import parse_pub_date, format_pub_date_for_filename
from .deleted import restore_from_deleted
from .versioning import create_versioned_backup
from .logger import logger


class EpisodeProcessor:
    """Handles episode download and update logic."""

    def __init__(
        self,
        storage_dir: str,
        deleted_dir: str,
        metadata_mgr: MetadataManager,
        metadata: dict,
        max_downloads: int,
        days_to_download: int,
    ):
        """Initialize episode processor.

        Args:
            storage_dir: Directory for storing episodes
            deleted_dir: Directory for deleted episodes
            metadata_mgr: Metadata manager instance
            metadata: Metadata dictionary
            max_downloads: Maximum downloads per run
            days_to_download: Days to look back for new episodes (0 = all)
        """
        self.storage_dir = storage_dir
        self.deleted_dir = deleted_dir
        self.metadata_mgr = metadata_mgr
        self.metadata = metadata
        self.max_downloads = max_downloads
        self.downloads_count = 0
        self.skipped_old_count = 0
        self.cutoff_date = self._calculate_cutoff_date(days_to_download)

    def _calculate_cutoff_date(self, days_to_download: int) -> Optional[datetime]:
        """Calculate cutoff date for episode downloads."""
        if days_to_download <= 0:
            return None
        return datetime.now() - timedelta(days=days_to_download)

    def _format_episode_log(self, entry) -> str:
        """Format episode information for logging.

        Returns:
            Format: "YYYY-MM-DD: Title" if date known, otherwise just "Title"
        """
        if "published" in entry and entry.published:
            pub_date = format_pub_date_for_filename(entry.published)
            if pub_date:
                return f"{pub_date}: {entry.title}"
        return entry.title

    def process_entry(self, entry, entry_idx: int = 0) -> Tuple[bool, str]:
        """Process a single feed entry.

        Args:
            entry: Feedparser entry object
            entry_idx: Index of the entry in the feed (for logging)

        Returns:
            Tuple of (downloaded, filename)
        """
        if not entry.enclosures:
            return False, ""

        mp3_url = entry.enclosures[0].href

        # Process existing episode
        if mp3_url in self.metadata:
            return self._process_existing_episode(entry, mp3_url)

        # Process new episode
        return self._process_new_episode(entry, mp3_url, entry_idx)

    def _process_existing_episode(self, entry, mp3_url: str) -> Tuple[bool, str]:
        """Process an episode that exists in metadata."""
        filename = self.metadata[mp3_url]["filename"]
        is_deleted = self.metadata[mp3_url].get("deleted", False)

        # Restore if episode is back in feed after being deleted
        if is_deleted:
            self._restore_deleted_episode(mp3_url, filename, entry.title)

        file_path = os.path.join(self.storage_dir, filename)

        # Check for metadata changes (independent of file content changes)
        metadata_changed = self._check_metadata_changes(filename, entry, mp3_url)

        # Update title in global metadata if changed
        self._update_title_if_changed(entry, mp3_url)

        # Handle missing file
        if not os.path.exists(file_path):
            return self._handle_missing_file(entry, mp3_url, filename, file_path)

        # Check for updates to existing file
        return self._check_for_updates(
            entry, mp3_url, filename, file_path, metadata_changed
        )

    def _restore_deleted_episode(self, mp3_url: str, filename: str, title: str):
        """Restore episode from deleted folder if it's back in feed."""
        if restore_from_deleted(self.storage_dir, self.deleted_dir, filename, title):
            self.metadata[mp3_url]["deleted"] = False

    def _update_title_if_changed(self, entry, mp3_url: str):
        """Update metadata if episode title changed."""
        old_title = self.metadata[mp3_url]["title"]
        new_title = entry.title

        if old_title != new_title:
            logger.info(f"Title changed: '{old_title}' → '{new_title}'")
            self.metadata[mp3_url]["title"] = new_title

    def _check_metadata_changes(self, filename: str, entry, mp3_url: str) -> bool:
        """Check if episode metadata changed and archive old version if needed.

        Args:
            filename: Episode filename
            entry: Feedparser entry with new metadata
            mp3_url: URL of the MP3 file

        Returns:
            True if metadata changed, False otherwise
        """
        # Load existing metadata from sidecar JSON
        episode_meta = self.metadata_mgr.load_episode_metadata(filename)
        if not episode_meta:
            return False

        # Extract feed metadata from old (exclude file-related fields)
        old_metadata = {
            "title": episode_meta.get("title", ""),
            "description": episode_meta.get("description", ""),
            "published": episode_meta.get("published"),
            "mp3_url": episode_meta.get("mp3_url", ""),
        }

        # Extract feed metadata from new
        new_metadata = {
            "title": entry.title,
            "description": getattr(entry, "description", ""),
            "published": entry.published if "published" in entry else None,
            "mp3_url": mp3_url,
        }

        # Compare the metadata blobs
        if old_metadata == new_metadata:
            return False

        # Metadata changed - log what changed
        logger.info(f"Metadata changed for: {new_metadata['title']}")
        for key in old_metadata:
            if old_metadata[key] != new_metadata[key]:
                old_val = old_metadata[key]
                new_val = new_metadata[key]

                # Truncate long values for logging
                if isinstance(old_val, str) and len(old_val) > 50:
                    old_val = old_val[:50] + "..."
                if isinstance(new_val, str) and len(new_val) > 50:
                    new_val = new_val[:50] + "..."

                logger.info(f"  • {key}: '{old_val}' → '{new_val}'")

        # Archive old metadata JSON
        json_path = os.path.join(self.storage_dir, f"{filename}.json")
        version_info = create_versioned_backup(json_path)

        if version_info:
            # Track in global metadata
            changed_fields = ", ".join(
                [key for key in old_metadata if old_metadata[key] != new_metadata[key]]
            )
            reason = f"Metadata changed ({changed_fields})"
            self.metadata_mgr.track_version(
                mp3_url,
                version_type="metadata",
                archived_file=version_info["archived_file"],
                reason=reason,
            )

        return True

    def _handle_missing_file(
        self, entry, mp3_url: str, filename: str, file_path: str
    ) -> Tuple[bool, str]:
        """Download or re-download file if it's missing but in metadata."""
        if not self._can_download():
            return False, filename

        # Check if episode is within date range (if filter is set)
        if not self._is_within_date_range(entry):
            self.skipped_old_count += 1
            logger.debug(
                f"⊘ Skipping (outside date range): {self._format_episode_log(entry)}"
            )
            return False, filename

        # Check if file was previously downloaded
        was_downloaded = self.metadata[mp3_url].get("downloaded", False)

        episode_info = self._format_episode_log(entry)
        if was_downloaded:
            logger.info(f"↓ Re-downloading (file missing): {episode_info}")
        else:
            logger.info(f"↓ Downloading: {episode_info}")

        remote_info = get_remote_file_info(mp3_url)
        remote_etag = remote_info.get("etag") if remote_info else None

        result = download_mp3(mp3_url, file_path)
        self.downloads_count += 1

        self._save_episode_files(
            filename,
            entry,
            mp3_url,
            result["hash"],
            remote_etag,
            is_new=not was_downloaded,
        )

        return True, filename

    def _check_for_updates(
        self,
        entry,
        mp3_url: str,
        filename: str,
        file_path: str,
        metadata_changed: bool = False,
    ) -> Tuple[bool, str]:
        """Check if remote file changed and update if needed."""
        # Load existing metadata
        episode_meta = self.metadata_mgr.load_episode_metadata(filename)
        if not episode_meta:
            return True, filename

        stored_etag = episode_meta.get("etag")
        stored_hash = episode_meta.get("file_hash_sha256")

        # Get remote file info
        remote_info = get_remote_file_info(mp3_url)
        if not remote_info:
            return True, filename

        remote_etag = remote_info.get("etag")

        # Check ETag first (fastest check)
        if self._etags_match(stored_etag, remote_etag):
            logger.debug(f"✓ Unchanged (ETag match): {entry.title}")
            return True, filename

        # Check file size
        if self._size_changed(file_path, remote_info):
            return self._update_episode(
                entry, mp3_url, filename, file_path, stored_hash, remote_etag
            )

        # ETag changed but size same - verify by hash
        if self._etag_changed(stored_etag, remote_etag):
            return self._verify_episode(
                entry, mp3_url, filename, file_path, stored_hash, remote_etag
            )

        # If metadata changed but file didn't, save new metadata
        if metadata_changed:
            self._save_episode_files(
                filename, entry, mp3_url, stored_hash, remote_etag, is_new=False
            )

        return True, filename

    def _etags_match(
        self, stored_etag: Optional[str], remote_etag: Optional[str]
    ) -> bool:
        """Check if ETags match."""
        return stored_etag and remote_etag and stored_etag == remote_etag

    def _etag_changed(
        self, stored_etag: Optional[str], remote_etag: Optional[str]
    ) -> bool:
        """Check if ETag changed."""
        return remote_etag and remote_etag != stored_etag

    def _size_changed(self, file_path: str, remote_info: dict) -> bool:
        """Check if file size changed."""
        local_size = os.path.getsize(file_path)
        remote_size = remote_info.get("content_length")
        return remote_size and str(local_size) != str(remote_size)

    def _update_episode(
        self,
        entry,
        mp3_url: str,
        filename: str,
        file_path: str,
        stored_hash: Optional[str],
        remote_etag: Optional[str],
    ) -> Tuple[bool, str]:
        """Update episode when size changed."""
        if not self._can_download():
            return True, filename

        # Check if episode is within date range (if filter is set)
        if not self._is_within_date_range(entry):
            self.skipped_old_count += 1
            logger.debug(
                f"⊘ Skipping update (outside date range): {self._format_episode_log(entry)}"
            )
            return True, filename

        episode_info = self._format_episode_log(entry)
        logger.info(f"↓ Updating (size changed): {episode_info}")

        result = download_mp3(mp3_url, file_path, existing_hash=stored_hash)
        self.downloads_count += 1

        if result["changed"] and result.get("version_info"):
            # Track MP3 version in global metadata
            self.metadata_mgr.track_version(
                mp3_url,
                version_type="content",
                archived_file=result["version_info"]["archived_file"],
                reason="Content changed",
                file_hash=stored_hash,
            )

        if result["changed"]:
            self._save_episode_files(
                filename, entry, mp3_url, result["hash"], remote_etag, is_new=False
            )

        return True, filename

    def _verify_episode(
        self,
        entry,
        mp3_url: str,
        filename: str,
        file_path: str,
        stored_hash: Optional[str],
        remote_etag: Optional[str],
    ) -> Tuple[bool, str]:
        """Verify episode when ETag changed but size same."""
        if not self._can_download():
            return True, filename

        # Check if episode is within date range (if filter is set)
        if not self._is_within_date_range(entry):
            self.skipped_old_count += 1
            logger.debug(
                f"⊘ Skipping verification (outside date range): {self._format_episode_log(entry)}"
            )
            return True, filename

        episode_info = self._format_episode_log(entry)
        logger.info(f"↓ Verifying (ETag changed): {episode_info}")

        result = download_mp3(mp3_url, file_path, existing_hash=stored_hash)
        self.downloads_count += 1

        if result["changed"] and result.get("version_info"):
            # Track MP3 version in global metadata
            self.metadata_mgr.track_version(
                mp3_url,
                version_type="content",
                archived_file=result["version_info"]["archived_file"],
                reason="Content changed",
                file_hash=stored_hash,
            )

        if result["changed"]:
            self._save_episode_files(
                filename, entry, mp3_url, result["hash"], remote_etag, is_new=False
            )

        return True, filename

    def _process_new_episode(
        self, entry, mp3_url: str, entry_idx: int = 0
    ) -> Tuple[bool, str]:
        """Process a new episode not in metadata."""
        pub_date = entry.published if "published" in entry else None
        filename = self._generate_filename(entry.title, pub_date)
        file_path = os.path.join(self.storage_dir, filename)

        # Add to metadata BEFORE downloading so track_current_version can find it
        self._add_to_metadata(mp3_url, filename, entry, downloaded=False)

        should_download = self._should_download_new_episode(entry)
        downloaded = False

        if should_download:
            downloaded = self._download_new_episode(entry, mp3_url, filename, file_path)
        elif self._download_limit_reached():
            logger.warning(
                f"skipped #{entry_idx} due to download limit of {self.max_downloads}"
            )

        return downloaded, filename

    def _generate_filename(self, title: str, pub_date_str: Optional[str] = None) -> str:
        """Generate filename with date prefix and UUID.

        Format: YYYY-MM-DD-uuid.mp3

        Args:
            title: Episode title from RSS feed
            pub_date_str: Optional publication date string from RSS feed

        Returns:
            Filename in format YYYY-MM-DD-uuid.mp3
        """
        # Get publication date, fall back to today if not available
        pub_date = format_pub_date_for_filename(pub_date_str)
        if not pub_date:
            pub_date = datetime.now().strftime("%Y-%m-%d")

        # Include date in UUID generation for determinism
        combined_key = f"{title}:{pub_date}"
        title_uuid = uuid.uuid5(uuid.NAMESPACE_DNS, combined_key)

        return f"{pub_date}-{title_uuid}.mp3"

    def _is_within_date_range(self, entry) -> bool:
        """Check if episode is within the configured date range.

        Args:
            entry: Feedparser entry object

        Returns:
            True if episode is within date range (or no filter set), False otherwise
        """
        # No date filter set - all episodes allowed
        if self.cutoff_date is None:
            return True

        # No publication date - exclude it when date filter is active
        if "published" not in entry:
            return False

        pub_date = parse_pub_date(entry.published)
        return pub_date >= self.cutoff_date

    def _should_download_new_episode(self, entry) -> bool:
        """Check if new episode should be downloaded."""
        if not self._can_download():
            return False

        return self._is_within_date_range(entry)

    def _download_new_episode(
        self, entry, mp3_url: str, filename: str, file_path: str
    ) -> bool:
        """Download a new episode."""
        episode_info = self._format_episode_log(entry)
        logger.info(f"↓ Downloading new episode: {episode_info}")

        remote_info = get_remote_file_info(mp3_url)
        remote_etag = remote_info.get("etag") if remote_info else None

        result = download_mp3(mp3_url, file_path)
        self.downloads_count += 1

        self._save_episode_files(
            filename, entry, mp3_url, result["hash"], remote_etag, is_new=True
        )

        return True

    def _add_to_metadata(
        self, mp3_url: str, filename: str, entry, downloaded: bool = False
    ):
        """Add episode to metadata dictionary."""
        file_path = os.path.join(self.storage_dir, filename)
        self.metadata[mp3_url] = {
            "filename": filename,
            "title": entry.title,
            "published": entry.published if "published" in entry else None,
            "downloaded": downloaded or os.path.exists(file_path),
        }

    def _save_episode_files(
        self,
        filename: str,
        entry,
        mp3_url: str,
        file_hash: str,
        etag: Optional[str],
        is_new: bool = False,
    ):
        """Save episode metadata and RSS sidecar files."""
        published = entry.published if "published" in entry else None

        self.metadata_mgr.save_episode_metadata(
            filename,
            entry.title,
            entry.description,
            mp3_url,
            published,
            file_hash,
            etag=etag,
        )
        save_episode_rss(self.storage_dir, filename, entry)

        # Track current version in metadata
        reason = "Initial download" if is_new else "Updated content"
        self.metadata_mgr.track_current_version(mp3_url, filename, file_hash, reason)

        # Update downloaded field
        file_path = os.path.join(self.storage_dir, filename)
        if mp3_url in self.metadata:
            self.metadata[mp3_url]["downloaded"] = os.path.exists(file_path)

    def _can_download(self) -> bool:
        """Check if we can download more episodes.

        Returns False if:
        - max_downloads < 0 (downloads disabled)
        - max_downloads > 0 and download limit already reached

        Returns True if:
        - max_downloads == 0 (unlimited downloads)
        - max_downloads > 0 and under limit
        """
        if self.max_downloads < 0:
            return False
        if self.max_downloads == 0:
            return True
        return self.downloads_count < self.max_downloads

    def _download_limit_reached(self) -> bool:
        """Check if download limit was reached."""
        return self.downloads_count >= self.max_downloads

    def get_downloads_count(self) -> int:
        """Get total number of downloads performed."""
        return self.downloads_count

    def get_skipped_old_count(self) -> int:
        """Get total number of episodes skipped due to date filter."""
        return self.skipped_old_count
