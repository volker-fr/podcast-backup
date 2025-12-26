"""RSS feed processing and generation."""

import sys
import feedparser
import xml.etree.ElementTree as ET
import os
from .logger import logger


def download_feed(url):
    """Download and parse RSS feed."""
    try:
        logger.info(f"Fetching feed from: {url}")
        feed = feedparser.parse(url)
        logger.info(f"✓ Found {len(feed.entries)} episodes in feed")
        return feed
    except Exception as e:
        logger.error(f"Error downloading feed: {e}")
        sys.exit(1)


def save_episode_rss(storage_dir, filename, entry):
    """Save original RSS entry as XML sidecar file."""
    rss_file = os.path.join(storage_dir, f"{filename}.rss.xml")

    # Create item element from feed entry
    item = ET.Element("item")
    ET.SubElement(item, "title").text = entry.title
    if hasattr(entry, 'description'):
        ET.SubElement(item, "description").text = entry.description
    if hasattr(entry, 'link'):
        ET.SubElement(item, "link").text = entry.link
    if hasattr(entry, 'published'):
        ET.SubElement(item, "pubDate").text = entry.published
    if hasattr(entry, 'author'):
        ET.SubElement(item, "author").text = entry.author

    # Add enclosure
    if entry.enclosures:
        enclosure = ET.SubElement(item, "enclosure")
        enclosure.set("url", entry.enclosures[0].href)
        enclosure.set("length", entry.enclosures[0].length)
        enclosure.set("type", entry.enclosures[0].type)

    # Write to file
    tree = ET.ElementTree(item)
    tree.write(rss_file, encoding="utf-8", xml_declaration=True)
