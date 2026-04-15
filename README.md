# Reclaimarr

A Python CLI tool to automatically manage disk space by intelligently deleting media from a Plex media stack based on watch history, age, and usage patterns.

## Features

- **Intelligent Deletion:** Prioritizes media for deletion based on watch history (never watched, last watched date).
- **Multi-API Integration:** Fetches data from Plex, Tautulli, Radarr, and Sonarr for a holistic view of your media.
- **Disk Space Management:** Automatically deletes media to keep disk usage below a configurable target percentage.
- **Safety First:** Includes a `DRY_RUN` mode to preview deletions without affecting your files.
- **Configurable:** Easily configure API endpoints, keys, and deletion thresholds via a `.env` file.
- **Scheduled Runs:** Built-in cron scheduler to run automatically on a schedule.

## Quick Start

### Prerequisites

- **Windows 10/11**
- **Python 3.12+** ([Download from python.org](https://www.python.org/downloads/) — check "Add to PATH" during install)
- Running instances of:
  - [Plex Media Server](https://www.plex.tv/)
  - [Tautulli](https://tautulli.com/) (for watch history tracking)
  - [Radarr](https://radarr.video/) (for movie management)
  - [Sonarr](https://sonarr.tv/) (for TV series management)

### Step 1: Clone the Repository

```powershell
git clone https://github.com/okhr/reclaimarr.git
cd reclaimarr
```

### Step 2: Install Dependencies

```powershell
pip install -r requirements.txt
```

### Step 3: Run the Setup Wizard

The setup wizard will prompt you for each service's URL and API key, validate the connections, and generate a `.env` file.

```powershell
python setup.py
```

**Where to find your API keys:**

| Service | Location |
|---------|----------|
| Plex | [Finding your token](https://support.plex.tv/articles/204059436-finding-an-authentication-token-x-plex-token/) |
| Tautulli | Settings > Web Interface > API > API Key |
| Radarr | Settings > General > API Key |
| Sonarr | Settings > General > API Key |

### Step 4: Verify with a Dry Run

```powershell
python -m src.main
```

By default, `DRY_RUN=true` so no files will be deleted. Review the output to confirm Reclaimarr connects to all services and identifies media correctly.

When satisfied, open the `.env` file in a text editor, set `DRY_RUN=false`, and run again.

### Running on a Schedule

Reclaimarr has a built-in scheduler. Set `CRON_SCHEDULE` in your `.env` file (e.g., `"0 3 * * *"` for 3 AM daily) and leave it running:

```powershell
python -m src.main
```

The process will stay alive and execute on schedule. To run it in the background on Windows, you can use **Task Scheduler**:

1. Open Task Scheduler and create a new task
2. Set the trigger to run at startup (or your preferred schedule)
3. Set the action to run `python -m src.main` in the `reclaimarr` directory
4. Under Settings, set "If the task is already running: Do not start a new instance"

Alternatively, if `CRON_SCHEDULE` is left blank, the script will run once and exit.

### Important Considerations

#### Network Shares and Snapshots

If your media library is located on a network share (e.g., SMB) that uses a snapshotting filesystem like ZFS or Btrfs, disk space may not be immediately freed after files are deleted because the deleted files are still held by recent snapshots.

**Recommendation:** Configure your `CRON_SCHEDULE` to run at an interval longer than your snapshot retention period.

## Deletion Algorithm

The script prioritizes media for deletion based on the following logic:

1.  **Filter by Age:** Only media older than `MIN_AGE_DAYS` (default: 90) is considered.
2.  **Primary Sort (Never Watched):** Media that has never been watched is prioritized first, sorted by the date it was added (oldest first).
3.  **Secondary Sort (Watched):** Media that has been watched is sorted by the last watched date (oldest first).

The script will delete items from this prioritized list one by one until the disk usage of your media library drops below the `TARGET_USAGE` percentage.

## Configuration

All configuration is handled via the `.env` file. You can either run `python setup.py` for interactive setup, or copy `.env.example` to `.env` and fill in the values manually.

### Required API Settings
```
# Plex
PLEX_URL=http://localhost:32400
PLEX_TOKEN=your-plex-token

# Tautulli
TAUTULLI_URL=http://localhost:8181
TAUTULLI_API_KEY=your-tautulli-api-key

# Radarr
RADARR_URL=http://localhost:7878
RADARR_API_KEY=your-radarr-api-key

# Sonarr
SONARR_URL=http://localhost:8989
SONARR_API_KEY=your-sonarr-api-key
```

### Deletion & Scheduler Settings
```
# The target disk usage percentage (e.g., 80 for 80%).
TARGET_USAGE=80
# The minimum age in days before a media item can be deleted.
MIN_AGE_DAYS=90
# The path to your media library (e.g., D:\Media or \\server\media).
MEDIA_PATH=D:\Media
# Set to "true" to run in dry-run mode (no files deleted), or "false" to perform deletions.
DRY_RUN=true
# Set to "true" for verbose logging.
VERBOSE=false
# A cron-style string to schedule runs (e.g., "0 3 * * *"). If blank, runs once.
CRON_SCHEDULE="0 3 * * *"
```
