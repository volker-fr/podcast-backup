"""Utility functions for podcast backup."""

import hashlib
import os
from datetime import datetime
from typing import Optional


def parse_pub_date(pub_date_str):
    """Parse publication date from RSS feed."""
    # Attempt to parse the date with two common date formats
    try:
        pub_date = datetime.strptime(pub_date_str, "%a, %d %b %Y %H:%M:%S %z")
    except ValueError:
        pub_date = datetime.strptime(pub_date_str, "%a, %d %b %Y %H:%M:%S GMT")
    return pub_date


def format_pub_date_for_filename(pub_date_str: Optional[str]) -> Optional[str]:
    """Format publication date string for use in filename (YYYY-MM-DD format).

    Args:
        pub_date_str: Publication date from RSS feed

    Returns:
        Date in YYYY-MM-DD format, or None if parsing fails
    """
    if not pub_date_str:
        return None

    try:
        pub_date = parse_pub_date(pub_date_str)
        return pub_date.strftime("%Y-%m-%d")
    except (ValueError, AttributeError):
        return None


def calculate_file_hash(filepath):
    """Calculate SHA256 hash of a file."""
    if not os.path.exists(filepath):
        return None

    sha256 = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()
