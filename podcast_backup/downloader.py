"""Download functionality for podcast episodes."""

import os
import requests
from tqdm import tqdm
from .logger import logger
from .versioning import create_versioned_backup


def get_remote_file_info(url):
    """Get remote file size and etag without downloading."""
    try:
        response = requests.head(url, allow_redirects=True)
        return {
            "content_length": response.headers.get("content-length"),
            "etag": response.headers.get("etag"),
        }
    except Exception as e:
        logger.warning(f"Could not get remote file info: {e}")
        return None


def download_mp3(mp3_url, local_filename, existing_hash=None):
    """
    Download MP3 file with progress bar.

    Args:
        mp3_url: URL to download from
        local_filename: Path to save file
        existing_hash: Optional hash of existing file to compare

    Returns:
        dict with 'changed' (bool) and 'hash' (str) keys
    """
    temp_filename = local_filename + ".part"

    try:
        # Send an HTTP GET request to the enclosure URL
        response = requests.get(mp3_url, stream=True)
        response.raise_for_status()  # Raise an exception for bad requests

        # Get the total file size (if available)
        total_size = int(response.headers.get("content-length", 0))

        # Create a progress bar
        progress_bar = tqdm(total=total_size, unit="B", unit_scale=True)

        # Open a temporary file for writing in binary mode
        with open(temp_filename, "wb") as temp_file:
            for chunk in response.iter_content(chunk_size=8192):
                temp_file.write(chunk)
                progress_bar.update(len(chunk))

        progress_bar.close()

        # Calculate hash of downloaded file
        from .utils import calculate_file_hash

        new_hash = calculate_file_hash(temp_filename)

        # Check if file actually changed
        file_changed = True
        if existing_hash and new_hash == existing_hash:
            # Downloaded file has same content as existing file - keep original (preserves timestamp)
            file_changed = False
            logger.debug("  → Content identical (same hash), keeping existing file")
            os.remove(temp_filename)
            return {"changed": file_changed, "hash": new_hash}

        # File content changed - archive old version before replacing
        version_info = {}
        if existing_hash and os.path.exists(local_filename):
            # Archive the old MP3 file
            version_info = create_versioned_backup(local_filename)
            logger.debug(
                f"  → Content changed: {existing_hash[:8]}... → {new_hash[:8]}..."
            )

        # Replace the old file with the new one
        os.rename(temp_filename, local_filename)

        return {"changed": file_changed, "hash": new_hash, "version_info": version_info}

    except requests.exceptions.RequestException as e:
        logger.error(f"Download failed: {e}")
        if os.path.exists(temp_filename):
            os.remove(temp_filename)
        return {"changed": False, "hash": None}
