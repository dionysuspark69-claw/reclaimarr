# Reclaimarr

A Python CLI tool to automatically manage disk space by intelligently deleting media from a Plex media stack based on watch history, age, and usage patterns.

## Features

- **Intelligent Deletion:** Prioritizes media for deletion based on watch history (never watched, last watched date).
- **Multi-API Integration:** Fetches data from Plex, Tautulli, Radarr, and Sonarr for a holistic view of your media.
- **Disk Space Management:** Automatically deletes media to keep disk usage below a configurable target percentage.
- **Safety First:** Includes a `DRY_RUN` mode to preview deletions without affecting your files.
- **Configurable:** Easily configure API endpoints, keys, and deletion thresholds via a `.env` file.
- **Dockerized:** Comes with a `Dockerfile` and `docker-compose.yml` for easy, containerized deployment.

## Quick Start (Self-Hosting)

### Prerequisites

- Python 3.12+
- Docker and Docker Compose (for containerized deployment)
- Running instances of:
  - [Plex Media Server](https://www.plex.tv/)
  - [Tautulli](https://tautulli.com/) (for watch history tracking)
  - [Radarr](https://radarr.video/) (for movie management)
  - [Sonarr](https://sonarr.tv/) (for TV series management)

### Step 1: Clone the Repository

```bash
git clone https://github.com/okhr/reclaimarr.git
cd reclaimarr
```

### Step 2: Run the Setup Wizard

The setup wizard will prompt you for each service's URL and API key, validate the connections, and generate a `.env` file.

```bash
pip install requests
python setup.py
```

**Where to find your API keys:**

| Service | Location |
|---------|----------|
| Plex | [Finding your token](https://support.plex.tv/articles/204059436-finding-an-authentication-token-x-plex-token/) |
| Tautulli | Settings > Web Interface > API > API Key |
| Radarr | Settings > General > API Key |
| Sonarr | Settings > General > API Key |

### Step 3: Deploy with Docker

```bash
docker-compose up -d
```

> **Note:** Edit `docker-compose.yml` to adjust the volume mount (`/srv/media:/media`) to match your media library's location on the host. The `docker-compose.yml` uses Docker-internal hostnames for service URLs (e.g., `http://plex:32400`). Your `.env` file provides the API keys via variable substitution. If running without Docker, the URLs in `.env` are used directly.

### Step 4: Verify with a Dry Run

```bash
docker-compose logs -f reclaimarr
```

By default, `DRY_RUN=true` so no files will be deleted. Review the logs to confirm Reclaimarr connects to all services and identifies media correctly. When satisfied, set `DRY_RUN=false` in your `.env` file and restart:

```bash
docker-compose restart reclaimarr
```

### Running Without Docker

```bash
pip install -r requirements.txt
python -m src.main
```

## Deployment

Reclaimarr is designed to run as a long-running container with a built-in scheduler. The easiest way to deploy it is by adding it to your existing media stack's `docker-compose.yml`.

### Docker Compose Example

Here is a sample `docker-compose.yml` configuration for Reclaimarr. You can add this service to your main compose file.

```yaml
version: '3.8'

services:
  reclaimarr:
    image: ghcr.io/okhr/reclaimarr:latest
    container_name: reclaimarr
    restart: on-failure
    environment:
      # --- Required API Settings ---
      # Assumes you are running Reclaimarr in the same Docker network as your other services.
      - PLEX_URL=http://plex:32400
      - PLEX_TOKEN=${PLEX_TOKEN}
      - TAUTULLI_URL=http://tautulli:8181
      - TAUTULLI_API_KEY=${TAUTULLI_API_KEY}
      - RADARR_URL=http://radarr:7878
      - RADARR_API_KEY=${RADARR_API_KEY}
      - SONARR_URL=http://sonarr:8989
      - SONARR_API_KEY=${SONARR_API_KEY}
      
      # --- Required Path ---
      - MEDIA_PATH=/media

      # --- Optional Settings ---
      - TARGET_USAGE=80
      - MIN_AGE_DAYS=90
      - DRY_RUN=true
      - VERBOSE=false
      - CRON_SCHEDULE="0 3 * * *" # Runs every day at 3 AM. If blank, runs once.
    volumes:
      # Mount your media library. This path must match the one used by your other services.
      # Example: /srv/media on your host machine.
      - /srv/media:/media
```

### Running the Service

The `restart: on-failure` policy is used to ensure the container behaves correctly in both modes:
- **With `CRON_SCHEDULE`:** The container runs continuously as a service. If it ever crashes, Docker will restart it.
- **Without `CRON_SCHEDULE`:** The script runs once and exits cleanly. The `on-failure` policy ensures Docker will **not** restart it, allowing it to act as a one-off task.

To start the service, create a `.env` file for your secrets (or run `python setup.py`) and run:
```bash
docker-compose up -d
```
The container will start in the background. You can view its logs with `docker-compose logs -f reclaimarr`.

### Important Considerations

#### Network Shares and Snapshots

If your media library is located on a network share (e.g., NFS, SMB) that uses a snapshotting filesystem like ZFS or Btrfs, you may encounter a situation where disk space is not immediately freed after files are deleted. This is because the deleted files are still held by recent snapshots.

If Reclaimarr runs, deletes files, and then runs again before the snapshots containing those files have expired, it will see that the disk usage has not changed and may attempt to delete more content unnecessarily.

**Recommendation:** Configure your `CRON_SCHEDULE` to run at an interval longer than your snapshot retention period. For example, if your snapshots are kept for 24 hours, set the cron schedule to run every 25 hours (`"0 */25 * * *"`) or once a day at a specific time to ensure the snapshots have been cleared.

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
PLEX_URL=http://your-plex-url:32400
PLEX_TOKEN=your-plex-token

# Tautulli
TAUTULLI_URL=http://your-tautulli-url:8181
TAUTULLI_API_KEY=your-tautulli-api-key

# Radarr
RADARR_URL=http://your-radarr-url:7878
RADARR_API_KEY=your-radarr-api-key

# Sonarr
SONARR_URL=http://your-sonarr-url:8989
SONARR_API_KEY=your-sonarr-api-key
```

### Deletion & Scheduler Settings
```
# The target disk usage percentage (e.g., 80 for 80%).
TARGET_USAGE=80
# The minimum age in days before a media item can be deleted.
MIN_AGE_DAYS=90
# The path to your media library inside the Docker container.
MEDIA_PATH=/media
# Set to "true" to run in dry-run mode (no files deleted), or "false" to perform deletions.
DRY_RUN=true
# Set to "true" for verbose logging.
VERBOSE=false
# A cron-style string to schedule runs (e.g., "0 3 * * *"). If blank, runs once.
CRON_SCHEDULE="0 3 * * *"
```
