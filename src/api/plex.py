import requests
from typing import Any
from ..config import PLEX_URL, PLEX_TOKEN
from ..utils.logger import setup_logger

# Initialize logger
logger = setup_logger()


class PlexClient:
    """
    A client for interacting with the Plex Media Server API.
    """

    def __init__(self, base_url: str = PLEX_URL, token: str = PLEX_TOKEN):
        """
        Initializes the PlexClient.

        Args:
            base_url (str): The base URL of the Plex server (e.g., http://localhost:32400).
            token (str): The X-Plex-Token for authentication.
        """
        if not base_url or not token:
            raise ValueError("Plex URL and token must be provided.")

        self.base_url = base_url.rstrip('/')
        self.token = token
        self.headers = {
            "X-Plex-Token": self.token,
            "Accept": "application/json",
        }
        self._movie_section_ids: list[str] = []
        self._show_section_ids: list[str] = []
        self._discover_sections()

    def _discover_sections(self):
        """Discovers library sections and categorizes them by type."""
        logger.info("Discovering Plex library sections...")
        data = self._get("/library/sections")
        if not data:
            logger.warning("Could not discover Plex library sections.")
            return

        directories = data.get("MediaContainer", {}).get("Directory", [])
        for section in directories:
            section_type = section.get("type")
            section_key = section.get("key")
            section_title = section.get("title")

            if section_type == "movie":
                self._movie_section_ids.append(section_key)
                logger.info(f"Found movie library: '{section_title}' (section {section_key})")
            elif section_type == "show":
                self._show_section_ids.append(section_key)
                logger.info(f"Found TV show library: '{section_title}' (section {section_key})")

    def _get(self, endpoint: str, params: dict[str, Any] | None = None) -> Any | None:
        """
        Performs a GET request to a Plex API endpoint.

        Args:
            endpoint (str): The API endpoint to call.
            params (dict[str, Any] | None): Query parameters for the request.

        Returns:
            Any | None: The JSON response from the API, or None if an error occurs.
        """
        url = f"{self.base_url}{endpoint}"
        try:
            response = requests.get(url, headers=self.headers, params=params, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Error calling Plex API endpoint {endpoint}: {e}")
            return None

    def get_all_movies(self) -> list[dict[str, Any]]:
        """
        Fetches all movies from all movie library sections.

        Returns:
            list[dict[str, Any]]: A list of movie items.
        """
        logger.info("Fetching all movies from Plex...")
        all_movies = []
        for section_id in self._movie_section_ids:
            data = self._get(f"/library/sections/{section_id}/all", params={"includeGuids": 1})
            if data:
                movies = data.get("MediaContainer", {}).get("Metadata", [])
                all_movies.extend(movies)
        logger.info(f"Found {len(all_movies)} movies in Plex.")
        return all_movies

    def get_all_shows(self) -> list[dict[str, Any]]:
        """
        Fetches all TV shows from all show library sections.

        Returns:
            list[dict[str, Any]]: A list of TV show items.
        """
        logger.info("Fetching all TV shows from Plex...")
        all_shows = []
        for section_id in self._show_section_ids:
            data = self._get(f"/library/sections/{section_id}/all", params={"includeGuids": 1})
            if data:
                shows = data.get("MediaContainer", {}).get("Metadata", [])
                all_shows.extend(shows)
        logger.info(f"Found {len(all_shows)} TV shows in Plex.")
        return all_shows

    def get_episodes_for_show(self, show_rating_key: str) -> list[dict[str, Any]]:
        """
        Gets all episodes for a given TV show using allLeaves.

        Args:
            show_rating_key (str): The ratingKey of the Plex TV show.

        Returns:
            list[dict[str, Any]]: A list of episode items for the show.
        """
        logger.debug(f"Fetching episodes for show ratingKey: {show_rating_key}")
        data = self._get(f"/library/metadata/{show_rating_key}/allLeaves")
        if not data:
            return []
        episodes = data.get("MediaContainer", {}).get("Metadata", [])
        logger.debug(f"Found {len(episodes)} episodes for show ratingKey: {show_rating_key}")
        return episodes

    @staticmethod
    def extract_imdb_id(guids: list[dict] | None) -> str | None:
        """
        Extracts the IMDB ID from a Plex Guid list.

        Args:
            guids: List of Guid dicts, e.g. [{"id": "imdb://tt1234567"}, {"id": "tmdb://12345"}]

        Returns:
            str | None: The IMDB ID (e.g., "tt1234567") or None if not found.
        """
        if not guids:
            return None
        for guid in guids:
            guid_id = guid.get("id", "")
            if guid_id.startswith("imdb://"):
                return guid_id[7:]  # Strip "imdb://" prefix
        return None

    @staticmethod
    def get_file_size(media_list: list[dict] | None) -> int:
        """
        Extracts the total file size from Plex Media metadata.

        Args:
            media_list: The "Media" array from a Plex metadata item.

        Returns:
            int: Total file size in bytes across all parts.
        """
        if not media_list:
            return 0
        total_size = 0
        for media in media_list:
            for part in media.get("Part", []):
                total_size += part.get("size", 0)
        return total_size


if __name__ == '__main__':
    from pprint import pp

    logger = setup_logger(verbose=True)

    try:
        client = PlexClient()

        # Test fetching movies
        movies = client.get_all_movies()
        if movies:
            pp(movies[0])

        # Test fetching shows
        shows = client.get_all_shows()
        if shows:
            pp(shows[0])
            # Test fetching episodes
            first_show_key = str(shows[0].get("ratingKey"))
            episodes = client.get_episodes_for_show(first_show_key)
            if episodes:
                pp(episodes[0])

    except ValueError as e:
        logger.error(f"Configuration error: {e}")
    except Exception as e:
        logger.error(f"An unexpected error occurred during testing: {e}")
