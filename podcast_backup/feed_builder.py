"""RSS feed XML building and generation."""

import xml.etree.ElementTree as ET
import xml.dom.minidom


class FeedBuilder:
    """Builds modified RSS feed XML from podcast data."""

    def __init__(self, source_feed, base_url: str):
        """Initialize feed builder.

        Args:
            source_feed: Parsed feedparser feed object
            base_url: Base URL for serving episode files
        """
        self.source_feed = source_feed
        self.base_url = base_url.rstrip('/')
        self.feed_xml = ET.Element("rss")
        self.channel = ET.SubElement(self.feed_xml, "channel")
        self._add_feed_metadata()

    def _add_feed_metadata(self):
        """Add feed-level metadata elements from source feed."""
        feed = self.source_feed.feed

        ET.SubElement(self.channel, "title").text = feed.get('title', 'Podcast')
        ET.SubElement(self.channel, "description").text = feed.get('description', '')

        if 'link' in feed:
            ET.SubElement(self.channel, "link").text = feed.link

        if 'language' in feed:
            ET.SubElement(self.channel, "language").text = feed.language

        self._add_feed_image(feed)

    def _add_feed_image(self, feed):
        """Add podcast artwork/image if present."""
        if 'image' not in feed:
            return

        image = ET.SubElement(self.channel, "image")

        if 'href' in feed.image:
            ET.SubElement(image, "url").text = feed.image.href

        if 'title' in feed.image:
            ET.SubElement(image, "title").text = feed.image.title

        if 'link' in feed.image:
            ET.SubElement(image, "link").text = feed.image.link

    def add_episode(self, entry, filename: str, downloaded: bool):
        """Add an episode item to the feed.

        Args:
            entry: Feedparser entry object
            filename: Local filename for the episode
            downloaded: Whether the episode file was downloaded
        """
        item = ET.SubElement(self.channel, "item")

        title = self._get_episode_title(entry.title, downloaded)
        ET.SubElement(item, "title").text = title
        ET.SubElement(item, "description").text = entry.description

        self._add_enclosure(item, filename, entry.enclosures[0])

    def _get_episode_title(self, title: str, downloaded: bool) -> str:
        """Get episode title with backup status prefix."""
        if not downloaded:
            return f"NOT BACKED UP: {title}"
        return title

    def _add_enclosure(self, item, filename: str, enclosure):
        """Add enclosure element with episode file URL."""
        enc_element = ET.SubElement(item, "enclosure")
        enc_element.set("url", f"{self.base_url}/{filename}")
        enc_element.set("length", enclosure.length)
        enc_element.set("type", enclosure.type)

    def add_deleted_episode(self, episode_data: dict, filename: str):
        """Add a deleted episode to the feed.

        Args:
            episode_data: Episode metadata dictionary
            filename: Local filename for the episode
        """
        item = ET.SubElement(self.channel, "item")

        title = f"DELETED UPSTREAM: {episode_data['title']}"
        ET.SubElement(item, "title").text = title
        ET.SubElement(item, "description").text = episode_data.get('description', '')

        # Add enclosure pointing to deleted folder
        enclosure = ET.SubElement(item, "enclosure")
        enclosure.set("url", f"{self.base_url}/deleted/{filename}")
        enclosure.set("length", "0")
        enclosure.set("type", "audio/mpeg")

        # Add published date if available
        if episode_data.get('published'):
            ET.SubElement(item, "pubDate").text = episode_data['published']

    def save(self, output_path: str):
        """Save the feed XML to file with human-readable formatting.

        Args:
            output_path: Path to save the XML file
        """
        # Convert to string first
        xml_str = ET.tostring(self.feed_xml, encoding='utf-8')

        # Pretty print using minidom
        dom = xml.dom.minidom.parseString(xml_str)
        pretty_xml = dom.toprettyxml(indent="  ", encoding='utf-8')

        # Write to file
        with open(output_path, 'wb') as f:
            f.write(pretty_xml)
