import requests
from typing import Any
from ..config import TAUTULLI_URL, TAUTULLI_API_KEY
from ..utils.logger import setup_logger

# Initialize logger
logger = setup_logger()

# Number of records to fetch per page
PAGE_SIZE = 5000


class TautulliClient:
    """
    A client for interacting with the Tautulli API.
    """

    def __init__(self, base_url: str = TAUTULLI_URL, api_key: str = TAUTULLI_API_KEY):
        """
        Initializes the TautulliClient.

        Args:
            base_url (str): The base URL of the Tautulli server.
            api_key (str): The API key for authentication.
        """
        if not base_url or not api_key:
            raise ValueError("Tautulli URL and API key must be provided.")

        self.base_url = base_url.rstrip('/')
        self.api_key = api_key

    def _get(self, cmd: str, extra_params: dict[str, Any] | None = None) -> Any | None:
        """
        Performs a GET request to the Tautulli API.

        Args:
            cmd (str): The Tautulli API command (e.g., "get_history").
            extra_params (dict[str, Any] | None): Additional query parameters.

        Returns:
            Any | None: The response data, or None if an error occurs.
        """
        url = f"{self.base_url}/api/v2"
        params = {"apikey": self.api_key, "cmd": cmd}
        if extra_params:
            params.update(extra_params)

        try:
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            result = response.json()
            resp = result.get("response", {})
            if resp.get("result") != "success":
                logger.error(f"Tautulli API error for cmd '{cmd}': {resp.get('message', 'Unknown error')}")
                return None
            return resp.get("data")
        except requests.exceptions.RequestException as e:
            logger.error(f"Error calling Tautulli API cmd '{cmd}': {e}")
            return None

    def get_playback_history(self) -> list[dict[str, Any]]:
        """
        Fetches all playback history from Tautulli, handling pagination.

        Returns:
            list[dict[str, Any]]: A list of playback activity records.
        """
        logger.info("Fetching playback history from Tautulli...")
        all_records = []
        start = 0

        while True:
            data = self._get("get_history", {"start": start, "length": PAGE_SIZE})
            if not data:
                break

            records = data.get("data", [])
            if not records:
                break

            all_records.extend(records)
            total_count = data.get("recordsFiltered", 0)

            if len(all_records) >= total_count:
                break

            start += PAGE_SIZE

        logger.info(f"Found {len(all_records)} playback records in Tautulli.")
        return all_records


if __name__ == '__main__':
    import json

    logger = setup_logger(verbose=True)
    logger.info("--- Testing Tautulli Playback History ---")

    try:
        client = TautulliClient()
        playback_history = client.get_playback_history()

        if not playback_history:
            logger.warning("No playback history found.")
        else:
            logger.info(f"Successfully fetched {len(playback_history)} playback records.")
            logger.info("--- First Playback Record ---")
            logger.info(json.dumps(playback_history[0], indent=2))

    except ValueError as e:
        logger.error(f"Configuration error: {e}")
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}", exc_info=True)
