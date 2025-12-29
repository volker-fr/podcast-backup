"""Podcast RSS feed proxy that downloads and hosts episodes locally."""

try:
    from importlib.metadata import version

    __version__ = version("podcast-backup")
except Exception:
    __version__ = "unknown"
