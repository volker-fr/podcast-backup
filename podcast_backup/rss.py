"""RSS feed processing and generation."""

import sys
import hashlib
import feedparser
from lxml import etree
import os
import requests
from .logger import logger


def _get_feed_cache_path(url: str) -> str:
    """Generate cache file path in cache directory based on URL hash.

    Args:
        url: The feed URL to cache

    Returns:
        Path to cache file
    """
    # Use /tmp/podcast-backup-cache if it exists (Docker), otherwise /tmp
    cache_dir = (
        "/tmp/podcast-backup-cache"
        if os.path.exists("/tmp/podcast-backup-cache")
        else "/tmp"
    )
    url_hash = hashlib.sha256(url.encode()).hexdigest()[:16]
    return os.path.join(cache_dir, f"podcast_feed_{url_hash}.xml")


def download_feed(url, debug: bool = False):
    """Download and parse RSS feed, returning both parsed and raw XML.

    Args:
        url: RSS feed URL to download
        debug: If True, cache feed in /tmp and load from cache if available

    Returns:
        Tuple of (parsed feed, raw XML content)
    """
    cache_path = _get_feed_cache_path(url)

    # Try loading from cache if debug mode is enabled
    if debug and os.path.exists(cache_path):
        try:
            logger.info(f"Loading feed from cache: {cache_path}")
            with open(cache_path, "rb") as f:
                raw_xml = f.read()

            # Parse with feedparser
            feed = feedparser.parse(raw_xml)
            logger.info(f"✓ Found {len(feed.entries)} episodes in cached feed")

            return feed, raw_xml
        except Exception as e:
            logger.warning(f"Failed to load cached feed: {e}, downloading from remote")

    # Download from remote
    try:
        logger.info(f"Fetching feed from: {url}")

        # Download raw XML
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        raw_xml = response.content

        # Parse with feedparser
        feed = feedparser.parse(raw_xml)
        logger.info(f"✓ Found {len(feed.entries)} episodes in feed")

        # Cache the feed if debug mode is enabled
        if debug:
            try:
                with open(cache_path, "wb") as f:
                    f.write(raw_xml)
                logger.debug(f"Cached feed to {cache_path}")
            except Exception as e:
                logger.debug(f"Failed to cache feed: {e}")

        return feed, raw_xml
    except Exception as e:
        logger.error(f"Error downloading feed: {e}")
        sys.exit(1)


def save_episode_rss(storage_dir, filename, entry):
    """Save original RSS entry as XML sidecar file."""
    rss_file = os.path.join(storage_dir, f"{filename}.rss.xml")

    # Create item element from feed entry
    item = etree.Element("item")
    etree.SubElement(item, "title").text = entry.title
    if hasattr(entry, "description"):
        etree.SubElement(item, "description").text = entry.description
    if hasattr(entry, "link"):
        etree.SubElement(item, "link").text = entry.link
    if hasattr(entry, "published"):
        etree.SubElement(item, "pubDate").text = entry.published
    if hasattr(entry, "author"):
        etree.SubElement(item, "author").text = entry.author

    # Add enclosure
    if entry.enclosures:
        enclosure = etree.SubElement(item, "enclosure")
        enclosure.set("url", entry.enclosures[0].href)
        enclosure.set("length", entry.enclosures[0].length)
        enclosure.set("type", entry.enclosures[0].type)

    # Write to file
    tree = etree.ElementTree(item)
    tree.write(rss_file, encoding="utf-8", xml_declaration=True, pretty_print=True)
