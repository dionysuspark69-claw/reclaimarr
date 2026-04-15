#!/usr/bin/env python3
"""
Reclaimarr Interactive Setup Wizard

Prompts for API credentials, validates connections, and generates a .env file.
"""

import os
import sys
import tempfile
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
    "MEDIA_PATH": "/media",
    "DRY_RUN": "true",
    "VERBOSE": "false",
    "CRON_SCHEDULE": "0 3 * * *",
}


def prompt(message: str, default: str | None = None) -> str:
    """Prompt the user for input with an optional default."""
    if default:
        display = f"{message} [{default}]: "
    else:
        display = f"{message}: "

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


def validate_connection(url: str, api_key: str, service: dict) -> tuple[bool, str]:
    """
    Validate a connection to a service by hitting its validation endpoint.

    Returns:
        tuple of (success, message)
    """
    endpoint = service["validate_endpoint"]
    full_url = url.rstrip("/") + endpoint

    headers = {"Accept": "application/json"}
    params = {}

    if service["auth_mode"] == "header":
        headers[service["auth_header"]] = api_key
    elif service["auth_mode"] == "query":
        params[service["auth_query_param"]] = api_key

    extra_params = service.get("validate_extra_params", {})
    params.update(extra_params)

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


def prompt_service(service: dict) -> dict[str, str]:
    """Prompt for a service's URL and API key, with optional validation."""
    print(f"\n--- {service['name']} ---")
    if service.get("help"):
        print(f"  {service['help']}")

    while True:
        url = prompt(f"  {service['name']} URL", service["default_url"])
        url = url.rstrip("/")
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

    media_path = prompt("  Media library path (inside container)", DELETION_DEFAULTS["MEDIA_PATH"])
    if not media_path:
        media_path = DELETION_DEFAULTS["MEDIA_PATH"]
    config["MEDIA_PATH"] = media_path

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
        f"MEDIA_PATH={config.get('MEDIA_PATH', '/media')}",
        f"DRY_RUN={config.get('DRY_RUN', 'true')}",
        f"VERBOSE={config.get('VERBOSE', 'false')}",
        "",
        "# --- Scheduler Settings ---",
        f'CRON_SCHEDULE="{config.get("CRON_SCHEDULE", "0 3 * * *")}"',
    ]

    content = "\n".join(lines) + "\n"

    # Atomic write: write to temp file then rename
    fd, tmp_path = tempfile.mkstemp(dir=SCRIPT_DIR, prefix=".env.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", newline="\n") as f:
            f.write(content)
        os.replace(tmp_path, ENV_FILE)
    except Exception:
        # Clean up temp file on failure
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise

    print(f"\n.env file written to: {ENV_FILE}")


def mask_key(key: str) -> str:
    """Mask an API key, showing only the last 4 characters."""
    if not key or len(key) <= 4:
        return "****"
    return "*" * (len(key) - 4) + key[-4:]


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
    print(f"    Media Path:    {config.get('MEDIA_PATH', '/media')}")
    print(f"    Dry Run:       {config.get('DRY_RUN', 'true')}")
    print(f"    Verbose:       {config.get('VERBOSE', 'false')}")
    print(f"    Cron Schedule: {config.get('CRON_SCHEDULE', '')}")

    print("\n  Next Steps:")
    print("    1. Start with Docker:")
    print("       docker-compose up -d")
    print("    2. View logs:")
    print("       docker-compose logs -f reclaimarr")
    print("    3. Or run without Docker:")
    print("       pip install -r requirements.txt")
    print("       python -m src.main")
    print(f"\n  DRY_RUN is {'enabled' if config.get('DRY_RUN') == 'true' else 'DISABLED'}.")
    if config.get("DRY_RUN") == "true":
        print("  No files will be deleted until you set DRY_RUN=false in .env.")
    print("=" * 50)


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

    # Collect service credentials
    config = {}
    for service in SERVICES:
        result = prompt_service(service)
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
