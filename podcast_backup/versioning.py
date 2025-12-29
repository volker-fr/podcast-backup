"""File versioning utilities for keeping old versions of files."""

import os
import shutil
from datetime import datetime
from .logger import logger


def create_versioned_backup(file_path: str) -> dict:
    """Create a versioned backup of a file.

    Appends .pre-<timestamp> after the full filename.

    Args:
        file_path: Path to the file to backup

    Returns:
        dict: {'backup_path': str, 'timestamp': str, 'archived_file': str}
        Empty dict if file doesn't exist

    Example:
        /path/to/file.mp3 -> /path/to/file.mp3.pre-20251225-103045
        /path/to/file.json -> /path/to/file.json.pre-20251225-103045
    """
    if not os.path.exists(file_path):
        return {}

    # Generate timestamp
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")

    # Append .pre-timestamp after full filename
    backup_path = f"{file_path}.pre-{timestamp}"

    # Move the file
    shutil.move(file_path, backup_path)
    logger.info(f"  → Archived old version: {os.path.basename(backup_path)}")

    return {
        "backup_path": backup_path,
        "timestamp": timestamp,
        "archived_file": os.path.basename(backup_path),
    }


def archive_old_files(
    mp3_path: str, json_path: str, archive_mp3: bool = True, archive_json: bool = True
):
    """Archive old versions of MP3 and/or JSON files.

    Args:
        mp3_path: Path to the MP3 file
        json_path: Path to the JSON metadata file
        archive_mp3: Whether to archive the MP3 file
        archive_json: Whether to archive the JSON file
    """
    if archive_mp3 and os.path.exists(mp3_path):
        create_versioned_backup(mp3_path)

    if archive_json and os.path.exists(json_path):
        create_versioned_backup(json_path)
