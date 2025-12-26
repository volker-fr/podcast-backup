"""Handling of deleted episodes."""

import os
import glob
from .logger import logger


def move_to_deleted(storage_dir, deleted_dir, filename, title):
    """
    Move episode file to deleted folder.

    This happens when an episode is no longer present in the RSS feed.
    Reasons this occurs:
    - Podcast host removed episode permanently
    - Episode expired (some podcasts only keep recent episodes in feed)
    - Feed migrated to new URL without old episodes
    """
    old_file = os.path.join(storage_dir, filename)
    new_file = os.path.join(deleted_dir, filename)

    if os.path.exists(old_file):
        # Create deleted directory only when we need it
        os.makedirs(deleted_dir, exist_ok=True)

        logger.info(f"⊗ Deleted upstream (moved to deleted/): {title}")
        os.rename(old_file, new_file)

        # Also move sidecar files
        for ext in ['.json', '.rss.xml']:
            sidecar = os.path.join(storage_dir, f"{filename}{ext}")
            if os.path.exists(sidecar):
                os.rename(sidecar, os.path.join(deleted_dir, f"{filename}{ext}"))

        # Move all versioned files (filename.ext.pre-* pattern)
        pattern = os.path.join(storage_dir, f"{filename}.pre-*")
        versioned_files = glob.glob(pattern)

        for versioned_file in versioned_files:
            versioned_basename = os.path.basename(versioned_file)
            new_versioned_file = os.path.join(deleted_dir, versioned_basename)
            os.rename(versioned_file, new_versioned_file)
            logger.debug(f"  → Also moved versioned file: {versioned_basename}")

        # Also move versioned metadata files (filename.ext.json.pre-* pattern)
        json_pattern = os.path.join(storage_dir, f"{filename}.json.pre-*")
        versioned_json_files = glob.glob(json_pattern)

        for versioned_file in versioned_json_files:
            versioned_basename = os.path.basename(versioned_file)
            new_versioned_file = os.path.join(deleted_dir, versioned_basename)
            os.rename(versioned_file, new_versioned_file)
            logger.debug(f"  → Also moved versioned metadata: {versioned_basename}")

        return True
    return False


def restore_from_deleted(storage_dir, deleted_dir, filename, title):
    """
    Restore episode file from deleted folder.

    This happens when an episode reappears in the RSS feed after being removed.
    Reasons this occurs:
    - Podcast temporarily removed episode for editing and re-added it
    - Feed was corrected after accidental removal
    - Episode was moved between different feeds
    """
    deleted_file = os.path.join(deleted_dir, filename)
    active_file = os.path.join(storage_dir, filename)

    if os.path.exists(deleted_file):
        logger.info(f"⊙ Restored (back in feed): {title}")
        os.rename(deleted_file, active_file)

        # Also restore sidecar files
        for ext in ['.json', '.rss.xml']:
            sidecar = os.path.join(deleted_dir, f"{filename}{ext}")
            if os.path.exists(sidecar):
                os.rename(sidecar, os.path.join(storage_dir, f"{filename}{ext}"))

        # Restore all versioned files (filename.ext.pre-* pattern)
        pattern = os.path.join(deleted_dir, f"{filename}.pre-*")
        versioned_files = glob.glob(pattern)

        for versioned_file in versioned_files:
            versioned_basename = os.path.basename(versioned_file)
            restored_file = os.path.join(storage_dir, versioned_basename)
            os.rename(versioned_file, restored_file)
            logger.debug(f"  → Also restored versioned file: {versioned_basename}")

        # Also restore versioned metadata files (filename.ext.json.pre-* pattern)
        json_pattern = os.path.join(deleted_dir, f"{filename}.json.pre-*")
        versioned_json_files = glob.glob(json_pattern)

        for versioned_file in versioned_json_files:
            versioned_basename = os.path.basename(versioned_file)
            restored_file = os.path.join(storage_dir, versioned_basename)
            os.rename(versioned_file, restored_file)
            logger.debug(f"  → Also restored versioned metadata: {versioned_basename}")

        return True
    return False


def process_deleted_episodes(metadata, current_feed_urls, storage_dir, deleted_dir):
    """Mark episodes as deleted if they're no longer in the feed."""
    for mp3_url, episode_data in list(metadata.items()):
        if mp3_url not in current_feed_urls:
            filename = episode_data['filename']

            # Move file to deleted folder if it exists and not already marked as deleted
            if not episode_data.get('deleted', False):
                if move_to_deleted(storage_dir, deleted_dir, filename, episode_data['title']):
                    episode_data['deleted'] = True
