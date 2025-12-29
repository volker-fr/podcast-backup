"""RSS feed XML building and generation."""

import os
import re
import hashlib
import json
from io import BytesIO
from lxml import etree
import requests
from urllib.parse import urljoin, urlparse
from .logger import logger


class FeedBuilder:
    """Builds modified RSS feed XML from podcast data."""

    def __init__(
        self,
        source_feed,
        raw_xml: bytes,
        base_url: str,
        storage_dir: str,
        deleted_dir: str,
        feed_url: str,
    ):
        """Initialize feed builder.

        Args:
            source_feed: Parsed feedparser feed object
            raw_xml: Raw XML bytes from the original feed
            base_url: Base URL for serving episode files
            storage_dir: Directory containing episode files and sidecars
            deleted_dir: Directory containing deleted episode files
            feed_url: Original feed URL (for resolving relative stylesheet URLs)
        """
        self.source_feed = source_feed
        self.base_url = base_url.rstrip("/")
        self.storage_dir = storage_dir
        self.deleted_dir = deleted_dir
        self.raw_xml = raw_xml
        self.feed_url = feed_url

        # Parse with lxml preserving as much as possible
        # remove_blank_text=False preserves whitespace
        # strip_cdata=False preserves CDATA sections
        parser = etree.XMLParser(remove_blank_text=False, strip_cdata=False)
        self.tree = etree.parse(BytesIO(raw_xml), parser)
        self.root = self.tree.getroot()

        # Find the channel element
        self.channel = self.root.find("channel")
        if self.channel is None:
            raise ValueError("No channel element found in RSS feed")

        # Update channel description
        title_elem = self.channel.find("title")
        desc_elem = self.channel.find("description")
        if title_elem is not None and title_elem.text:
            title = title_elem.text
            # Create description element if it doesn't exist
            if desc_elem is None:
                desc_elem = etree.Element("description")
                # Insert after title
                title_index = list(self.channel).index(title_elem)
                self.channel.insert(title_index + 1, desc_elem)
            # Update description text
            desc_elem.text = f"{title} podcast-backup"

        # Update atom:link self-reference to point to archival feed
        atom_ns = {"atom": "http://www.w3.org/2005/Atom"}
        atom_link = self.channel.find("atom:link[@rel='self']", atom_ns)
        if atom_link is not None:
            # Construct the archival feed URL
            # Extract podcast name from storage_dir (last part of path)
            podcast_name = os.path.basename(self.storage_dir)
            archival_feed_url = f"{self.base_url}/{podcast_name}/archival_backup.xml"
            atom_link.set("href", archival_feed_url)

        # Track which episodes we've processed
        self.processed_urls = set()

    def add_episode(self, entry, filename: str, downloaded: bool):
        """Update an existing episode item in the feed.

        Args:
            entry: Feedparser entry object
            filename: Local filename for the episode
            downloaded: Whether the episode file was downloaded
        """
        if not entry.enclosures:
            return

        original_url = entry.enclosures[0].href
        self.processed_urls.add(original_url)

        # Find the matching item in the feed by enclosure URL
        for item in self.channel.findall("item"):
            enclosure = item.find("enclosure")
            if enclosure is not None and enclosure.get("url") == original_url:
                # Update enclosure URL to point to our backed up file
                enclosure.set("url", f"{self.base_url}/{filename}")

                # Update title if not downloaded
                if not downloaded:
                    title_elem = item.find("title")
                    if title_elem is not None and title_elem.text:
                        title_elem.text = f"NOT BACKED UP: {title_elem.text}"

                break

    def add_deleted_episode(self, filename: str):
        """Add a deleted episode to the feed using its sidecar RSS file.

        Args:
            filename: Local filename for the episode
        """
        # Try to load from storage_dir first, then deleted_dir
        rss_file = os.path.join(self.storage_dir, f"{filename}.rss.xml")
        if not os.path.exists(rss_file):
            rss_file = os.path.join(self.deleted_dir, f"{filename}.rss.xml")

        if not os.path.exists(rss_file):
            # Can't add without sidecar file
            return

        # Parse the sidecar RSS file
        try:
            parser = etree.XMLParser(remove_blank_text=False, strip_cdata=False)
            item_tree = etree.parse(rss_file, parser)
            item = item_tree.getroot()

            # Update title to indicate deletion
            title_elem = item.find("title")
            if title_elem is not None and title_elem.text:
                title_elem.text = f"DELETED UPSTREAM: {title_elem.text}"

            # Update enclosure URL to point to deleted folder
            enclosure = item.find("enclosure")
            if enclosure is not None:
                enclosure.set("url", f"{self.base_url}/deleted/{filename}")

            # Add the item to our channel
            self.channel.append(item)

        except Exception:
            # Skip if we can't parse
            pass

    def _download_stylesheet(self, href: str) -> str:
        """Download stylesheet file to storage directory and return local filename.

        Args:
            href: Stylesheet href attribute (relative or absolute URL)

        Returns:
            Local filename of downloaded stylesheet, or original href if download fails
        """
        # Resolve relative URLs against the feed URL
        absolute_url = urljoin(self.feed_url, href)

        # Extract filename from URL
        parsed = urlparse(absolute_url)
        filename = os.path.basename(parsed.path)
        if not filename:
            filename = "rss-stylesheet.xsl"

        local_path = os.path.join(self.storage_dir, filename)
        metadata_path = os.path.join(self.storage_dir, f"{filename}.json")

        # Load existing metadata if available
        existing_etag = None
        existing_hash = None
        if os.path.exists(metadata_path):
            try:
                with open(metadata_path, "r") as f:
                    metadata = json.load(f)
                    existing_etag = metadata.get("etag")
                    existing_hash = metadata.get("file_hash_sha256")
            except Exception:
                pass

        # Download stylesheet with conditional request
        try:
            headers = {}
            if existing_etag:
                headers["If-None-Match"] = existing_etag

            response = requests.get(absolute_url, headers=headers, timeout=30)

            # 304 Not Modified - file hasn't changed
            if response.status_code == 304:
                logger.debug(f"Stylesheet unchanged (304): {filename}")
                return filename

            response.raise_for_status()

            # Calculate hash of new content
            new_hash = hashlib.sha256(response.content).hexdigest()

            # Check if content actually changed
            if os.path.exists(local_path) and existing_hash == new_hash:
                logger.debug(f"Stylesheet unchanged (hash match): {filename}")
                return filename

            # Content changed - save new version
            if os.path.exists(local_path):
                logger.info(f"Updating stylesheet (content changed): {filename}")
            else:
                logger.info(f"Downloading stylesheet: {filename}")

            with open(local_path, "wb") as f:
                f.write(response.content)

            # Save metadata
            metadata = {
                "url": absolute_url,
                "file_hash_sha256": new_hash,
                "etag": response.headers.get("ETag"),
            }
            with open(metadata_path, "w") as f:
                json.dump(metadata, f, indent=2)

            logger.info(f"✓ Stylesheet saved: {filename}")
            return filename

        except Exception as e:
            logger.warning(f"Failed to download stylesheet: {e}")
            # Return filename if local copy exists, otherwise original href
            if os.path.exists(local_path):
                return filename
            return href

    def save(self, output_path: str):
        """Save the feed XML to file with human-readable formatting.

        Args:
            output_path: Path to save the XML file
        """
        # Handle stylesheet processing instructions
        # Find and update any xml-stylesheet processing instructions
        # We need to get the root element and iterate over preceding PIs
        root = self.tree.getroot()
        for pi in root.itersiblings(preceding=True):
            if (
                isinstance(pi, etree._ProcessingInstruction)
                and pi.target == "xml-stylesheet"
                and pi.text
            ):
                # Parse the PI text to extract href
                href_match = re.search(r'href=["\']([^"\']+)["\']', pi.text)
                if href_match:
                    original_href = href_match.group(1)
                    # Download stylesheet and get local filename
                    local_filename = self._download_stylesheet(original_href)
                    # Update href to point to local file using relative path
                    new_text = pi.text.replace(
                        href_match.group(0), f'href="{local_filename}"'
                    )
                    # Update the PI text directly (works for both document-level and nested PIs)
                    # We can't easily "replace" document-level PIs, so modify in place
                    pi.text = new_text

        # Serialize with lxml preserving structure
        # pretty_print=True for human-readable formatting
        # xml_declaration=True to include <?xml...?>
        # encoding='utf-8' for proper character encoding
        self.tree.write(
            output_path, encoding="utf-8", xml_declaration=True, pretty_print=True
        )
