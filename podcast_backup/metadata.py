"""Metadata management for podcast episodes."""

import json
import os
from datetime import datetime
from typing import Optional
from .logger import logger


class MetadataManager:
    """Manages episode metadata storage and retrieval."""

    def __init__(self, storage_dir):
        """Initialize metadata manager with storage directory."""
        self.storage_dir = storage_dir
        self.metadata_file = os.path.join(storage_dir, 'episodes_metadata.json')
        self._metadata = None

    def load(self):
        """Load episode metadata from JSON file."""
        if os.path.exists(self.metadata_file):
            with open(self.metadata_file, 'r') as f:
                self._metadata = json.load(f)
            return self._metadata

        self._metadata = {}
        return self._metadata

    def save(self):
        """Save episode metadata to JSON file."""
        if self._metadata is not None:
            with open(self.metadata_file, 'w') as f:
                json.dump(self._metadata, f, indent=2)

    def get(self):
        """Get the metadata dictionary."""
        if self._metadata is None:
            self.load()
        return self._metadata

    def save_episode_metadata(self, filename, title, description, mp3_url, published, file_hash, etag=None):
        """Save episode metadata as JSON sidecar file."""
        metadata_file = os.path.join(self.storage_dir, f"{filename}.json")
        metadata = {
            'title': title,
            'description': description,
            'mp3_url': mp3_url,
            'published': published,
            'downloaded_at': datetime.now().isoformat(),
            'file_hash_sha256': file_hash,
            'etag': etag
        }
        with open(metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2)

    def load_episode_metadata(self, filename):
        """Load episode metadata from JSON sidecar file."""
        metadata_file = os.path.join(self.storage_dir, f"{filename}.json")
        if os.path.exists(metadata_file):
            with open(metadata_file, 'r') as f:
                return json.load(f)
        return None

    def track_version(self, mp3_url: str, version_type: str, archived_file: str, reason: str = "", file_hash: Optional[str] = None):
        """Track a versioned file in the global metadata.

        Args:
            mp3_url: Episode URL (key in metadata)
            version_type: "content" or "metadata"
            archived_file: Filename of archived version (e.g., "uuid.pre-20251225-103045.mp3")
            reason: Human-readable reason for the change
            file_hash: Optional file hash for content versions
        """
        if self._metadata is None:
            self.load()

        if mp3_url not in self._metadata:
            return

        # Initialize versions list if it doesn't exist
        if 'versions' not in self._metadata[mp3_url]:
            self._metadata[mp3_url]['versions'] = []

        # Mark all existing versions as not current
        for version in self._metadata[mp3_url]['versions']:
            version['is_current'] = False

        # Add version entry
        version_entry = {
            'filename': archived_file,
            'type': version_type,
            'archived_at': datetime.now().isoformat(),
            'reason': reason,
            'is_current': False
        }

        if file_hash:
            version_entry['file_hash'] = file_hash

        self._metadata[mp3_url]['versions'].append(version_entry)

    def track_current_version(self, mp3_url: str, filename: str, file_hash: str, reason: str = "Initial download"):
        """Track the current version of an episode.

        Args:
            mp3_url: Episode URL (key in metadata)
            filename: Current filename (e.g., "uuid.mp3")
            file_hash: SHA256 hash of current file
            reason: Human-readable reason (e.g., "Initial download", "Updated content")
        """
        if self._metadata is None:
            self.load()

        if mp3_url not in self._metadata:
            return

        # Initialize versions list if it doesn't exist
        if 'versions' not in self._metadata[mp3_url]:
            self._metadata[mp3_url]['versions'] = []

        # Mark all existing versions as not current
        for version in self._metadata[mp3_url]['versions']:
            version['is_current'] = False

        # Add current version entry
        version_entry = {
            'filename': filename,
            'type': 'current',
            'downloaded_at': datetime.now().isoformat(),
            'file_hash': file_hash,
            'is_current': True,
            'reason': reason
        }

        self._metadata[mp3_url]['versions'].append(version_entry)
