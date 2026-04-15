#!/usr/bin/env python3
"""
Reclaimarr Interactive Setup Wizard

Prompts for API credentials, validates connections, and generates a .env file.
Automatically discovers credentials from locally installed services when possible.
"""

import configparser
import os
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

try:
    import requests
except ImportError:
    print("Error: 'requests' package is required. Install it with:")
    print("  pip install requests")
    sys.exit(1)

# Resolve paths relative to this script's location
SCRIPT_DIR = Path(__file__).parent.resolve()
ENV_FILE = SCRIPT_DIR / ".env"

# Service definitions: each entry drives the prompting and validation loop
SERVICES = [
    {
        "name": "Plex",
        "url_var": "PLEX_URL",
        "key_var": "PLEX_TOKEN",
        "key_label": "Plex Token",
        "default_url": "http://localhost:32400",
        "validate_endpoint": "/",
        "auth_mode": "header",
        "auth_header": "X-Plex-Token",
        "help": "Find your token: https://support.plex.tv/articles/204059436-finding-an-authentication-token-x-plex-token/",
    },
    {
        "name": "Tautulli",
        "url_var": "TAUTULLI_URL",
        "key_var": "TAUTULLI_API_KEY",
        "key_label": "API Key",
        "default_url": "http://localhost:8181",
        "validate_endpoint": "/api/v2",
        "auth_mode": "query",
        "auth_query_param": "apikey",
        "validate_extra_params": {"cmd": "get_tautulli_info"},
        "help": "Find your key: Tautulli > Settings > Web Interface > API > API Key",
    },
    {
        "name": "Radarr",
        "url_var": "RADARR_URL",
        "key_var": "RADARR_API_KEY",
        "key_label": "API Key",
        "default_url": "http://localhost:7878",
        "validate_endpoint": "/api/v3/system/status",
        "auth_mode": "header",
        "auth_header": "X-Api-Key",
        "help": "Find your key: Radarr > Settings > General > API Key",
    },
    {
        "name": "Sonarr",
        "url_var": "SONARR_URL",
        "key_var": "SONARR_API_KEY",
        "key_label": "API Key",
        "default_url": "http://localhost:8989",
        "validate_endpoint": "/api/v3/system/status",
        "auth_mode": "header",
        "auth_header": "X-Api-Key",
        "help": "Find your key: Sonarr > Settings > General > API Key",
    },
]

DELETION_DEFAULTS = {
    "TARGET_USAGE": "80",
    "MIN_AGE_DAYS": "90",
    "MEDIA_PATH": r"D:\Media",
    "DRY_RUN": "true",
    "VERBOSE": "false",
    "CRON_SCHEDULE": "0 3 * * *",
}


# ---------------------------------------------------------------------------
# Auto-discovery
# ---------------------------------------------------------------------------

def _expand(path: str) -> Path:
    """Expand Windows environment variables and return a Path."""
    return Path(os.path.expandvars(path))


def _read_arr_config(candidate_paths: list[str]) -> dict[str, str]:
    """
    Try to read API key and port from an *Arr config.xml.
    Returns {"api_key": "...", "port": "..."} or {}.
    """
    for path_str in candidate_paths:
        config_path = _expand(path_str)
        if not config_path.is_file():
            continue
        try:
            root = ET.parse(config_path).getroot()
            api_key = root.findtext("ApiKey") or ""
            port = root.findtext("Port") or ""
            if api_key:
                return {"api_key": api_key, "port": port}
        except Exception:
            continue
    return {}


def _discover_radarr() -> dict[str, str]:
    return _read_arr_config([
        r"%APPDATA%\Radarr\config.xml",
        r"%ProgramData%\Radarr\config.xml",
    ])


def _discover_sonarr() -> dict[str, str]:
    return _read_arr_config([
        r"%APPDATA%\Sonarr\config.xml",
        r"%APPDATA%\Roaming\Sonarr\config.xml",
        r"%ProgramData%\Sonarr\config.xml",
    ])


def _discover_tautulli() -> dict[str, str]:
    candidates = [
        r"%APPDATA%\Tautulli\config.ini",
        r"%ProgramData%\Tautulli\config.ini",
    ]
    for path_str in candidates:
        config_path = _expand(path_str)
        if not config_path.is_file():
            continue
        try:
            cp = configparser.ConfigParser()
            cp.read(config_path, encoding="utf-8")
            api_key = cp.get("General", "api_key", fallback="").strip()
            port = cp.get("General", "http_port", fallback="8181").strip()
            if api_key:
                return {"api_key": api_key, "port": port}
        except Exception:
            continue
    return {}


def _discover_plex() -> dict[str, str]:
    pref_path = _expand(r"%LOCALAPPDATA%\Plex Media Server\Preferences.xml")
    if not pref_path.is_file():
        return {}
    try:
        root = ET.parse(pref_path).getroot()
        token = root.get("PlexOnlineToken", "").strip()
        if token:
            return {"api_key": token}
    except Exception:
        pass
    return {}


def discover_all() -> dict[str, dict[str, str]]:
    """
    Scan local config files and return discovered credentials per service.
    Keys in each dict: "api_key" and optionally "port".
    """
    return {
        "Plex": _discover_plex(),
        "Tautulli": _discover_tautulli(),
        "Radarr": _discover_radarr(),
        "Sonarr": _discover_sonarr(),
    }


def _build_url(default_url: str, discovered_port: str) -> str:
    """Replace the port in a default URL with a discovered port."""
    if not discovered_port:
        return default_url
    # Strip trailing port from default and append discovered port
    parts = default_url.rsplit(":", 1)
    if len(parts) == 2:
        return f"{parts[0]}:{discovered_port}"
    return default_url


# ---------------------------------------------------------------------------
# Prompting helpers
# ---------------------------------------------------------------------------

def prompt(message: str, default: str | None = None) -> str:
    """Prompt the user for input with an optional default."""
    display = f"{message} [{default}]: " if default else f"{message}: "
    value = input(display).strip()
    if not value and default is not None:
        return default
    return value


def prompt_yes_no(message: str, default: bool = True) -> bool:
    """Prompt the user for a yes/no answer."""
    suffix = "[Y/n]" if default else "[y/N]"
    value = input(f"{message} {suffix}: ").strip().lower()
    if not value:
        return default
    return value in ("y", "yes")


def mask_key(key: str) -> str:
    """Mask an API key, showing only the last 4 characters."""
    if not key or len(key) <= 4:
        return "****"
    return "*" * (len(key) - 4) + key[-4:]


# ---------------------------------------------------------------------------
# Connection validation
# ---------------------------------------------------------------------------

def validate_connection(url: str, api_key: str, service: dict) -> tuple[bool, str]:
    """
    Validate a connection to a service by hitting its validation endpoint.
    Returns (success, message).
    """
    full_url = url.rstrip("/") + service["validate_endpoint"]
    headers = {"Accept": "application/json"}
    params = {}

    if service["auth_mode"] == "header":
        headers[service["auth_header"]] = api_key
    elif service["auth_mode"] == "query":
        params[service["auth_query_param"]] = api_key

    params.update(service.get("validate_extra_params", {}))

    try:
        response = requests.get(full_url, headers=headers, params=params, timeout=10)
        if response.status_code in (401, 403):
            return False, "Authentication failed. Check your API key/token."
        response.raise_for_status()
        return True, "Connected successfully."
    except requests.exceptions.ConnectionError:
        return False, f"Could not connect to {url}. Is the service running?"
    except requests.exceptions.Timeout:
        return False, f"Connection to {url} timed out."
    except requests.exceptions.RequestException as e:
        return False, str(e)


# ---------------------------------------------------------------------------
# Service prompting
# ---------------------------------------------------------------------------

def prompt_service(service: dict, discovered: dict[str, str] | None = None) -> dict[str, str]:
    """
    Prompt for a service's URL and API key.
    If discovered credentials are provided, they are pre-filled as defaults.
    """
    disc = discovered or {}
    discovered_key = disc.get("api_key", "")
    discovered_port = disc.get("port", "")
    default_url = _build_url(service["default_url"], discovered_port)

    print(f"\n--- {service['name']} ---")
    if discovered_key:
        print(f"  Auto-discovered {service['key_label']}: {mask_key(discovered_key)}")
    elif service.get("help"):
        print(f"  {service['help']}")

    while True:
        url = prompt(f"  {service['name']} URL", default_url).rstrip("/")

        # Key prompt: show masked discovered key as default
        if discovered_key:
            raw = input(f"  {service['key_label']} [{mask_key(discovered_key)}]: ").strip()
            key = raw if raw else discovered_key
        else:
            key = prompt(f"  {service['key_label']}")

        if not key:
            print(f"  Warning: No key provided for {service['name']}.")
            if prompt_yes_no("  Continue without a key?", default=False):
                return {service["url_var"]: url, service["key_var"]: ""}
            continue

        print(f"  Validating connection to {service['name']}...", end=" ", flush=True)
        success, message = validate_connection(url, key, service)

        if success:
            print(f"OK - {message}")
            return {service["url_var"]: url, service["key_var"]: key}
        else:
            print(f"FAILED - {message}")
            print("  Options: [r]etry, [s]kip validation, [q]uit")
            choice = input("  Choice: ").strip().lower()
            if choice == "s":
                return {service["url_var"]: url, service["key_var"]: key}
            elif choice == "q":
                print("\nSetup cancelled.")
                sys.exit(0)
            # else retry (loop continues)


# ---------------------------------------------------------------------------
# Deletion settings
# ---------------------------------------------------------------------------

def prompt_deletion_settings() -> dict[str, str]:
    """Prompt for deletion and scheduler settings."""
    print("\n--- Deletion Settings ---")
    config = {}

    target = prompt("  Target disk usage % (1-99)", DELETION_DEFAULTS["TARGET_USAGE"])
    try:
        val = int(target)
        if not 1 <= val <= 99:
            raise ValueError
    except ValueError:
        print(f"  Invalid value '{target}', using default {DELETION_DEFAULTS['TARGET_USAGE']}.")
        target = DELETION_DEFAULTS["TARGET_USAGE"]
    config["TARGET_USAGE"] = target

    min_age = prompt("  Minimum age in days before deletion", DELETION_DEFAULTS["MIN_AGE_DAYS"])
    try:
        val = int(min_age)
        if val < 0:
            raise ValueError
    except ValueError:
        print(f"  Invalid value '{min_age}', using default {DELETION_DEFAULTS['MIN_AGE_DAYS']}.")
        min_age = DELETION_DEFAULTS["MIN_AGE_DAYS"]
    config["MIN_AGE_DAYS"] = min_age

    media_path = prompt(r"  Media library path (e.g., D:\Media)", DELETION_DEFAULTS["MEDIA_PATH"])
    config["MEDIA_PATH"] = media_path or DELETION_DEFAULTS["MEDIA_PATH"]

    dry_run = prompt("  Dry run mode (true/false)", DELETION_DEFAULTS["DRY_RUN"]).lower()
    if dry_run not in ("true", "false", "yes", "no"):
        dry_run = DELETION_DEFAULTS["DRY_RUN"]
    config["DRY_RUN"] = "true" if dry_run in ("true", "yes") else "false"

    verbose = prompt("  Verbose logging (true/false)", DELETION_DEFAULTS["VERBOSE"]).lower()
    if verbose not in ("true", "false", "yes", "no"):
        verbose = DELETION_DEFAULTS["VERBOSE"]
    config["VERBOSE"] = "true" if verbose in ("true", "yes") else "false"

    print("\n--- Scheduler Settings ---")
    cron = prompt("  Cron schedule (leave blank for one-off run)", DELETION_DEFAULTS["CRON_SCHEDULE"])
    config["CRON_SCHEDULE"] = cron

    return config


# ---------------------------------------------------------------------------
# .env writing
# ---------------------------------------------------------------------------

def write_env_file(config: dict[str, str]):
    """Write the .env file atomically."""
    lines = [
        "# Plex",
        f"PLEX_URL={config.get('PLEX_URL', '')}",
        f"PLEX_TOKEN={config.get('PLEX_TOKEN', '')}",
        "",
        "# Tautulli",
        f"TAUTULLI_URL={config.get('TAUTULLI_URL', '')}",
        f"TAUTULLI_API_KEY={config.get('TAUTULLI_API_KEY', '')}",
        "",
        "# Radarr",
        f"RADARR_URL={config.get('RADARR_URL', '')}",
        f"RADARR_API_KEY={config.get('RADARR_API_KEY', '')}",
        "",
        "# Sonarr",
        f"SONARR_URL={config.get('SONARR_URL', '')}",
        f"SONARR_API_KEY={config.get('SONARR_API_KEY', '')}",
        "",
        "# --- Deletion Settings ---",
        f"TARGET_USAGE={config.get('TARGET_USAGE', '80')}",
        f"MIN_AGE_DAYS={config.get('MIN_AGE_DAYS', '90')}",
        f"MEDIA_PATH={config.get('MEDIA_PATH', r'D:\Media')}",
        f"DRY_RUN={config.get('DRY_RUN', 'true')}",
        f"VERBOSE={config.get('VERBOSE', 'false')}",
        "",
        "# --- Scheduler Settings ---",
        f'CRON_SCHEDULE="{config.get("CRON_SCHEDULE", "0 3 * * *")}"',
    ]

    content = "\n".join(lines) + "\n"

    fd, tmp_path = tempfile.mkstemp(dir=SCRIPT_DIR, prefix=".env.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", newline="\n") as f:
            f.write(content)
        os.replace(tmp_path, ENV_FILE)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise

    print(f"\n.env file written to: {ENV_FILE}")


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

def print_summary(config: dict[str, str]):
    """Print a summary of the configuration."""
    print("\n" + "=" * 50)
    print("  Configuration Summary")
    print("=" * 50)

    print("\n  Services:")
    for service in SERVICES:
        url = config.get(service["url_var"], "")
        key = config.get(service["key_var"], "")
        print(f"    {service['name']:12s} {url}")
        print(f"    {'':12s} Key: {mask_key(key)}")

    print("\n  Deletion Settings:")
    print(f"    Target Usage:  {config.get('TARGET_USAGE', '80')}%")
    print(f"    Min Age:       {config.get('MIN_AGE_DAYS', '90')} days")
    print(f"    Media Path:    {config.get('MEDIA_PATH', r'D:\Media')}")
    print(f"    Dry Run:       {config.get('DRY_RUN', 'true')}")
    print(f"    Verbose:       {config.get('VERBOSE', 'false')}")
    print(f"    Cron Schedule: {config.get('CRON_SCHEDULE', '')}")

    print("\n  Next Steps:")
    print("    1. Install dependencies:")
    print("       pip install -r requirements.txt")
    print("    2. Do a dry run first:")
    print("       python -m src.main")
    print("    3. When satisfied, set DRY_RUN=false in .env and run again.")
    print(f"\n  DRY_RUN is {'enabled' if config.get('DRY_RUN') == 'true' else 'DISABLED'}.")
    if config.get("DRY_RUN") == "true":
        print("  No files will be deleted until you set DRY_RUN=false in .env.")
    print("=" * 50)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 50)
    print("  Reclaimarr Setup Wizard")
    print("  Plex media stack disk space manager")
    print("=" * 50)

    # Check for existing .env
    if ENV_FILE.exists():
        print(f"\nAn existing .env file was found at: {ENV_FILE}")
        if not prompt_yes_no("Overwrite it?", default=False):
            print("Setup cancelled. Your existing .env was not modified.")
            return

    # Auto-discover credentials from local installs
    print("\nScanning for locally installed services...")
    discovered = discover_all()
    found = [name for name, data in discovered.items() if data]
    if found:
        print(f"  Found config for: {', '.join(found)}")
        print("  Keys will be pre-filled — just press Enter to accept.")
    else:
        print("  No local configs found. You'll need to enter keys manually.")

    # Collect service credentials
    config = {}
    for service in SERVICES:
        result = prompt_service(service, discovered.get(service["name"]))
        config.update(result)

    # Collect deletion settings
    deletion_config = prompt_deletion_settings()
    config.update(deletion_config)

    # Write and summarize
    write_env_file(config)
    print_summary(config)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nSetup cancelled.")
        sys.exit(0)
