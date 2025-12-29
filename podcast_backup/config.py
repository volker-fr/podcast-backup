"""Configuration loader for podcast backup."""

import os
import sys
from pathlib import Path
from typing import Optional

try:
    import tomllib
except ModuleNotFoundError:
    try:
        import tomli as tomllib
    except ModuleNotFoundError:
        tomllib = None


class PodcastConfig:
    """Configuration for a single podcast."""

    def __init__(
        self,
        name: str,
        podcast_url: str,
        base_url: str,
        storage_dir: Optional[str] = None,
        max_downloads: Optional[int] = None,
        days_to_download: Optional[int] = None,
    ):
        self.name = name
        self.podcast_url = podcast_url
        self.base_url = base_url
        self.storage_dir = storage_dir
        self.max_downloads = max_downloads
        self.days_to_download = days_to_download


class Config:
    """Configuration container for podcast backup settings."""

    def __init__(
        self,
        podcasts: list,
        global_storage_dir: str,
        global_max_downloads: int = 0,
        global_days_to_download: int = 0,
    ):
        self.podcasts = podcasts
        self.global_storage_dir = global_storage_dir
        self.global_max_downloads = global_max_downloads
        self.global_days_to_download = global_days_to_download

    def get_podcast_storage_dir(self, podcast: PodcastConfig) -> str:
        """Get storage directory for a podcast (podcast-specific or global/name)."""
        if podcast.storage_dir:
            return podcast.storage_dir
        return os.path.join(self.global_storage_dir, podcast.name)

    def get_podcast_max_downloads(self, podcast: PodcastConfig) -> int:
        """Get max downloads for a podcast (podcast-specific or global)."""
        return (
            podcast.max_downloads
            if podcast.max_downloads is not None
            else self.global_max_downloads
        )

    def get_podcast_days_to_download(self, podcast: PodcastConfig) -> int:
        """Get days to download for a podcast (podcast-specific or global)."""
        return (
            podcast.days_to_download
            if podcast.days_to_download is not None
            else self.global_days_to_download
        )


def load_config(config_path: Optional[str] = None) -> Config:
    """
    Load configuration from TOML file or environment variables.

    Supports two formats:
    1. Multi-podcast format with [[podcasts]] array
    2. Single-podcast format (backward compatible with env vars)

    Priority order:
    1. Specified config file path
    2. config.toml in current directory
    3. Environment variables (single podcast only)

    Args:
        config_path: Optional path to config file

    Returns:
        Config object with loaded settings

    Raises:
        SystemExit: If required configuration is missing
    """
    config_data = {}
    config_file_exists = False

    # Try to load from TOML file
    if config_path:
        config_file = Path(config_path)
    else:
        config_file = Path("config.toml")

    if config_file.exists():
        config_file_exists = True
        if tomllib is None:
            print(
                "Warning: tomllib/tomli not available. Install tomli for Python < 3.11",
                file=sys.stderr,
            )

        if tomllib is not None:
            with open(config_file, "rb") as f:
                config_data = tomllib.load(f)

    # Check if environment variables are set and warn if both are present
    env_vars_set = any(
        [
            os.environ.get("PODCAST_URL"),
            os.environ.get("PODCAST_STORAGE_DIR"),
            os.environ.get("PODCAST_BASE_URL"),
        ]
    )

    if config_file_exists and env_vars_set:
        print(
            f"Warning: Both config file ({config_file}) and environment variables are set. "
            "Using config file values only.",
            file=sys.stderr,
        )

    # Check if this is multi-podcast format or single-podcast format
    if "podcasts" in config_data:
        # Multi-podcast format
        podcasts = []
        for podcast_data in config_data["podcasts"]:
            if "name" not in podcast_data:
                print("Error: Each podcast must have a 'name' field", file=sys.stderr)
                sys.exit(1)
            if "podcast_url" not in podcast_data:
                print(
                    f"Error: Podcast '{podcast_data.get('name')}' missing 'podcast_url'",
                    file=sys.stderr,
                )
                sys.exit(1)
            if "base_url" not in podcast_data:
                print(
                    f"Error: Podcast '{podcast_data.get('name')}' missing 'base_url'",
                    file=sys.stderr,
                )
                sys.exit(1)

            podcasts.append(
                PodcastConfig(
                    name=podcast_data["name"],
                    podcast_url=podcast_data["podcast_url"],
                    base_url=podcast_data["base_url"],
                    storage_dir=podcast_data.get("storage_dir"),
                    max_downloads=podcast_data.get("max_downloads"),
                    days_to_download=podcast_data.get("days_to_download"),
                )
            )

        # Get global settings
        global_storage_dir = config_data.get("storage_dir")
        if not global_storage_dir:
            print(
                "Error: 'storage_dir' is required for multi-podcast configuration",
                file=sys.stderr,
            )
            sys.exit(1)

        global_max_downloads = config_data.get("max_downloads", 0)
        global_days_to_download = config_data.get("days_to_download", 0)

        return Config(
            podcasts=podcasts,
            global_storage_dir=global_storage_dir,
            global_max_downloads=int(global_max_downloads),
            global_days_to_download=int(global_days_to_download),
        )

    # Single-podcast format (backward compatible)
    # Load values with environment variable fallback
    podcast_url = config_data.get("podcast_url") or os.environ.get("PODCAST_URL")
    storage_dir = config_data.get("storage_dir") or os.environ.get(
        "PODCAST_STORAGE_DIR"
    )
    base_url = config_data.get("base_url") or os.environ.get("PODCAST_BASE_URL")
    max_downloads = config_data.get("max_downloads") or os.environ.get("MAX_DOWNLOADS")
    days_to_download = config_data.get("days_to_download") or os.environ.get(
        "DAYS_TO_DOWNLOAD"
    )
    podcast_name = (
        config_data.get("name") or os.environ.get("PODCAST_NAME") or "default"
    )

    # Validate required fields
    missing = []
    if not podcast_url:
        missing.append("podcast_url (or PODCAST_URL env var)")
    if not storage_dir:
        missing.append("storage_dir (or PODCAST_STORAGE_DIR env var)")
    if not base_url:
        missing.append("base_url (or PODCAST_BASE_URL env var)")

    if missing:
        print(
            f"Error: Missing required configuration: {', '.join(missing)}",
            file=sys.stderr,
        )
        print("\nConfiguration can be provided via:", file=sys.stderr)
        print("  1. config.toml file in current directory", file=sys.stderr)
        print("  2. Environment variables", file=sys.stderr)
        print("  3. Custom config file with --config option", file=sys.stderr)
        sys.exit(1)

    # Convert to int with defaults
    max_downloads = int(max_downloads) if max_downloads is not None else 0
    days_to_download = int(days_to_download) if days_to_download is not None else 0

    # Create a single podcast config
    podcast = PodcastConfig(
        name=podcast_name,
        podcast_url=podcast_url,
        base_url=base_url,
        storage_dir=storage_dir,
        max_downloads=max_downloads,
        days_to_download=days_to_download,
    )

    return Config(
        podcasts=[podcast],
        global_storage_dir=storage_dir,
        global_max_downloads=max_downloads,
        global_days_to_download=days_to_download,
    )
