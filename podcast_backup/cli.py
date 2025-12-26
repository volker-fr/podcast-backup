#!/usr/bin/env python3
"""Main CLI entry point for podcast backup."""

import argparse
import logging
import os

from .config import load_config, PodcastConfig, Config
from .metadata import MetadataManager
from .rss import download_feed
from .deleted import process_deleted_episodes
from .logger import logger, setup_logger
from .feed_builder import FeedBuilder
from .episode_processor import EpisodeProcessor


def process_podcast(podcast: PodcastConfig, config: Config):
    """Process a single podcast: download episodes and generate RSS feed."""
    logger.info(f"Processing podcast: {podcast.name}")

    # Setup directories and metadata
    storage_dir = config.get_podcast_storage_dir(podcast)
    deleted_dir = os.path.join(storage_dir, 'deleted')
    os.makedirs(storage_dir, exist_ok=True)

    metadata_mgr = MetadataManager(storage_dir)
    metadata = metadata_mgr.load()

    # Download and parse feed
    feed = download_feed(podcast.podcast_url)
    current_feed_urls = _extract_feed_urls(feed)

    # Move deleted episodes
    process_deleted_episodes(metadata, current_feed_urls, storage_dir, deleted_dir)

    # Initialize processors
    feed_builder = FeedBuilder(feed, podcast.base_url)
    episode_processor = EpisodeProcessor(
        storage_dir=storage_dir,
        deleted_dir=deleted_dir,
        metadata_mgr=metadata_mgr,
        metadata=metadata,
        max_downloads=config.get_podcast_max_downloads(podcast),
        days_to_download=config.get_podcast_days_to_download(podcast),
    )

    # Process all episodes
    for idx, entry in enumerate(feed.entries, 1):
        downloaded, filename = episode_processor.process_entry(entry, idx)
        if filename:
            feed_builder.add_episode(entry, filename, downloaded)

    # Add deleted episodes to feed
    _add_deleted_episodes_to_feed(feed_builder, metadata, current_feed_urls)

    # Save metadata and feed
    metadata_mgr.save()
    output_file = os.path.join(storage_dir, 'archival_backup.xml')
    feed_builder.save(output_file)

    downloads_count = episode_processor.get_downloads_count()
    skipped_old_count = episode_processor.get_skipped_old_count()
    logger.info(f"✓ Feed saved to: {output_file}")

    # Build summary message
    summary_parts = [f"{downloads_count} downloads"]
    if skipped_old_count > 0:
        days_filter = config.get_podcast_days_to_download(podcast)
        summary_parts.append(f"{skipped_old_count} skipped (>{days_filter} days old)")

    logger.info(f"✓ Backup complete for '{podcast.name}' ({', '.join(summary_parts)})")




def _extract_feed_urls(feed) -> set:
    """Extract episode URLs from feed entries."""
    urls = set()
    for entry in feed.entries:
        if entry.enclosures:
            urls.add(entry.enclosures[0].href)
    return urls


def _add_deleted_episodes_to_feed(feed_builder: FeedBuilder, metadata: dict, current_feed_urls: set):
    """Add deleted episodes to the feed."""
    for mp3_url, episode_data in metadata.items():
        if mp3_url in current_feed_urls:
            continue

        if not episode_data.get('deleted', False):
            continue

        filename = episode_data['filename']
        feed_builder.add_deleted_episode(episode_data, filename)


def main():
    """Main entry point: load config and process all podcasts."""
    # Parse CLI arguments
    parser = argparse.ArgumentParser(description='Backup podcast RSS feeds')
    parser.add_argument('--config', '-c', type=str,
                       help='Path to config file (default: config.toml)')
    parser.add_argument('--debug', '-d', action='store_true',
                       help='Enable debug logging')
    args = parser.parse_args()

    # Setup logging level
    if args.debug:
        setup_logger(level=logging.DEBUG)

    # Load config with custom path (None will use default)
    config = load_config(args.config)

    logger.info(f"Processing {len(config.podcasts)} podcast(s)...")

    for podcast in config.podcasts:
        try:
            process_podcast(podcast, config)
        except Exception as e:
            logger.error(f"Error processing podcast '{podcast.name}': {e}")
            continue

    logger.info("✓ All podcasts processed")


if __name__ == "__main__":
    main()
