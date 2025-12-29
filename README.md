# Podcast Backup

A comprehensive podcast archival tool that downloads episodes locally and meticulously tracks all changes made to podcast content and metadata over time.

## Purpose

This tool serves two primary purposes:

1. **Archive Podcasts**: Create a reliable local backup of podcast episodes with deterministic UUID-based filenames
2. **Detect Changes**: Monitor and archive any modifications made to podcast episodes, including:
   - Content changes to MP3 files (tracked via SHA256 hashes)
   - Metadata updates (title, description, publication date)
   - Episode deletions and restorations
   - Publisher corrections or stealth edits

When podcasters modify episodes (fixing audio issues, updating content, or removing episodes), this tool captures and preserves both the original and updated versions with full change history.

## Features

### Core Archival

- Downloads podcast episodes from RSS feeds with deterministic UUID-based filenames
- Supports single or multiple podcast feeds via `config.toml`
- Stores comprehensive episode metadata (title, description, URL, publication date, file hashes)
- Generates modified RSS feeds pointing to local files for playback
- Configurable download limits and date filters

### Change Detection & Versioning

- **Content Change Detection**: Uses ETag headers and SHA256 hashes to detect modified MP3 files
- **Metadata Change Tracking**: Detects and archives changes to episode titles, descriptions, and publication dates
- **Automatic Versioning**: Preserves old versions when content or metadata changes (timestamped `.pre-YYYYMMDD-HHMMSS` files)
- **Deleted Episode Tracking**: Monitors episodes removed from feeds and can restore them if they return
- **Version History**: Maintains complete history of all changes with timestamps and reasons in `episodes_metadata.json`

### Smart Updates

- ETag-based change detection minimizes unnecessary downloads
- File size comparison for quick change detection
- Hash verification for content integrity
- Only re-downloads when actual changes detected

## Installation

### Local Installation

```bash
make install
```

### Docker Installation

Build the Docker image:

```bash
docker compose build
```

Or build manually:

```bash
docker build -t podcast-backup .
```

## Usage

### Using Docker (Recommended)

1. Create a `config.toml` file in the project directory (see Configuration section below)

2. Run the backup:

```bash
docker compose run --rm podcast-backup
```

3. Run with debug logging:

```bash
docker compose run --rm podcast-backup --debug
```

4. Schedule regular backups with cron (example):

```bash
# Add to crontab: Run every 6 hours
0 */6 * * * cd /path/to/podcast-backup && docker compose run --rm podcast-backup
```

The Docker container will:

- Read configuration from `./config.toml` (mounted as read-only)
- Store downloaded podcasts in `./podcasts/` directory
- Preserve all metadata and version history

### Using Local Installation

Set the required environment variables or create a `config.toml` file (see `config.toml.example`):

```bash
export PODCAST_URL="https://feeds.example.com/podcast.rss"
export PODCAST_STORAGE_DIR="/path/to/podcast/archive"
export PODCAST_BASE_URL="http://archive.example.com/podcasts"  # For local archival access
export MAX_DOWNLOADS=3  # Optional, defaults to 3
```

Run the backup:

```bash
make run
# or
uv run podcast-backup
```

## Configuration

### Using config.toml (Recommended)

Copy `config.toml.example` to `config.toml` and edit with your settings. Supports:

- Single or multiple podcast feeds
- Per-podcast configuration overrides
- Global defaults with podcast-specific overrides

See `config.toml.example` for detailed configuration options.

### Using Environment Variables

- `PODCAST_URL` (required): The URL of the podcast RSS feed
- `PODCAST_STORAGE_DIR` (required): Directory where episodes will be stored
- `PODCAST_BASE_URL` (required): Base URL for local archival access (e.g., `http://archive.example.com/podcasts`)
- `MAX_DOWNLOADS` (optional): Maximum number of new episodes to download per run (default: 3)
- `DAYS_TO_DOWNLOAD` (optional): Only download episodes from the last N days (default: 0 = all)

## Output

### File Structure

For each podcast in `PODCAST_STORAGE_DIR/podcast-name/`:

```
podcast-name/
├── episodes_metadata.json          # Global metadata with version history
├── modified_podcast_feed.xml       # Modified RSS feed with local URLs
├── 2025-12-11-uuid.mp3            # Current episode file
├── 2025-12-11-uuid.mp3.json       # Episode metadata sidecar
├── 2025-12-11-uuid.rss            # Original RSS entry
├── 2025-12-11-uuid.pre-20251225-164211.mp3      # Archived version (if changed)
├── 2025-12-11-uuid.pre-20251225-164211.mp3.json # Archived metadata (if changed)
└── deleted/                        # Episodes removed from feed
    └── 2025-11-01-uuid.mp3        # Deleted episode (preserved)
```

### Version History Tracking

The `episodes_metadata.json` file tracks complete version history:

```json
{
  "https://example.com/episode.mp3": {
    "filename": "2025-12-11-uuid.mp3",
    "title": "Episode Title",
    "published": "Thu, 11 Dec 2025 02:35:13 GMT",
    "downloaded": true,
    "versions": [
      {
        "filename": "2025-12-11-uuid.pre-20251220-100000.mp3",
        "type": "content",
        "archived_at": "2025-12-20T10:00:00",
        "reason": "Content changed",
        "file_hash": "abc123...",
        "is_current": false
      },
      {
        "filename": "2025-12-11-uuid.mp3",
        "type": "current",
        "downloaded_at": "2025-12-25T16:42:11",
        "file_hash": "def456...",
        "is_current": true,
        "reason": "Initial download"
      }
    ]
  }
}
```

### Change Detection Examples

The tool logs all detected changes:

```
Metadata changed for: Episode Title
  • description: 'Old description...' → 'Updated description...'

↓ Updating (size changed): 2025-12-11: Episode Title
Archived old version: 2025-12-11-uuid.pre-20251225-164211.mp3

Title changed: 'Old Title' → 'New Title'
```

## Changelog

### Version 0.2.1

- Fix: Stylesheet href now properly updates to local path after backup

### Version 0.2.0

- Docker rootless support
- Fix: RSS feed compliance for podcast clients
- Caching of downloads in debug mode
- Move to lxml

### Version 0.1.0

- Initial release
- Podcast episode downloading and archival
- Change detection and versioning
- Metadata tracking

## Development

```bash
# Format code
make format

# Lint code
make lint

# Clean build artifacts
make clean
```
