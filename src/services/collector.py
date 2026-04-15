from datetime import datetime, timezone

from ..api.plex import PlexClient
from ..api.tautulli import TautulliClient
from ..api.radarr import RadarrClient
from ..api.sonarr import SonarrClient
from ..models.media import Media, Movie, TVShow
from ..models.playback import Playback
from ..utils.logger import setup_logger

logger = setup_logger()


class DataCollector:
    """
    Collects and merges data from all configured APIs.
    """

    def __init__(self):
        """Initializes the DataCollector and all API clients."""
        logger.info("Initializing API clients...")
        self.plex = PlexClient()
        self.tautulli = TautulliClient()
        self.radarr = RadarrClient()
        self.sonarr = SonarrClient()
        logger.info("All API clients initialized.")

    def collect_all_media(self) -> list[Media]:
        """
        Orchestrates the collection and merging of all media data.

        Returns:
            list[Media]: A list of populated Movie and TVShow objects.
        """
        logger.info("Starting data collection process...")

        # 1. Fetch raw data from all APIs
        plex_movies = self.plex.get_all_movies()
        plex_shows = self.plex.get_all_shows()
        radarr_movies = self.radarr.get_all_movies()
        sonarr_series = self.sonarr.get_all_series()
        playback_history = self.tautulli.get_playback_history()

        # 2. Create lookup maps for efficient merging
        radarr_map_imdb = {movie['imdbId']: movie for movie in radarr_movies if 'imdbId' in movie and movie['imdbId']}
        radarr_map_title = {movie['title']: movie for movie in radarr_movies}

        sonarr_map_imdb = {series['imdbId']: series for series in sonarr_series if 'imdbId' in series and series['imdbId']}
        sonarr_map_title = {series['title']: series for series in sonarr_series}

        # 3. Process and merge media items
        movies = self._merge_movie_data(plex_movies, radarr_map_imdb, radarr_map_title)
        tv_shows, episode_to_show_map = self._merge_tv_show_data(plex_shows, sonarr_map_imdb, sonarr_map_title)

        all_media = movies + tv_shows

        # 4. Attach playback data
        self._attach_playback_data(all_media, playback_history, episode_to_show_map)

        # 5. Final calculations
        for media in all_media:
            media.calculate_watch_ratio()
            media.calculate_last_watch_date()

        logger.info(f"Data collection complete. Total media items processed: {len(all_media)}")
        return all_media

    def _merge_movie_data(self, plex_movies: list[dict], radarr_map_imdb: dict, radarr_map_title: dict) -> list[Movie]:
        """Merges Plex and Radarr data for movies."""
        merged_movies = []
        for plex_movie in plex_movies:
            title = plex_movie.get('title')
            rating_key = str(plex_movie.get('ratingKey'))
            imdb_id = PlexClient.extract_imdb_id(plex_movie.get('Guid'))

            radarr_data = None
            if imdb_id and imdb_id in radarr_map_imdb:
                radarr_data = radarr_map_imdb[imdb_id]
            else:
                radarr_data = radarr_map_title.get(title)

            # Basic info from Plex
            movie = Movie(
                plex_rating_key=rating_key,
                title=title,
                added_date=None,  # Will be populated from Radarr or Plex
                file_size=PlexClient.get_file_size(plex_movie.get('Media')),
                duration=plex_movie.get('duration', 0) / 60000,  # Milliseconds to minutes
            )

            # Add Radarr info
            if radarr_data:
                movie.radarr_id = radarr_data.get('id')
                if not movie.file_size:
                    movie.file_size = radarr_data.get('movieFile', {}).get('size', 0)
                # Prioritize Radarr's added date
                radarr_added_date = radarr_data.get('movieFile', {}).get('dateAdded')
                if radarr_added_date:
                    movie.added_date = self._parse_date(radarr_added_date)

            # Fallback to Plex added date
            if not movie.added_date:
                added_at = plex_movie.get('addedAt')
                if added_at:
                    movie.added_date = datetime.fromtimestamp(added_at, tz=timezone.utc)

            merged_movies.append(movie)
        logger.info(f"Merged {len(merged_movies)} movies.")
        return merged_movies

    def _merge_tv_show_data(self, plex_shows: list[dict], sonarr_map_imdb: dict, sonarr_map_title: dict) -> tuple[list[TVShow], dict[str, str]]:
        """Merges Plex and Sonarr data for TV shows."""
        merged_shows = []
        episode_to_show_map = {}
        for plex_show in plex_shows:
            title = plex_show.get('title')
            rating_key = str(plex_show.get('ratingKey'))
            imdb_id = PlexClient.extract_imdb_id(plex_show.get('Guid'))

            sonarr_data = None
            if imdb_id and imdb_id in sonarr_map_imdb:
                sonarr_data = sonarr_map_imdb[imdb_id]
            else:
                sonarr_data = sonarr_map_title.get(title)

            # Get episode details from Plex to calculate total duration and count
            episodes = self.plex.get_episodes_for_show(rating_key)
            total_duration = sum(ep.get('duration', 0) / 60000 for ep in episodes)  # ms to minutes

            show = TVShow(
                plex_rating_key=rating_key,
                title=title,
                added_date=None,  # Will be populated from Sonarr or Plex
                file_size=0,  # Will be set from Sonarr if available
                total_duration=total_duration,
                total_episodes=len(episodes)
            )

            # Add Sonarr info
            if sonarr_data:
                show.sonarr_id = sonarr_data.get('id')
                show.file_size = sonarr_data.get('statistics', {}).get('sizeOnDisk', 0)
                sonarr_added_date = sonarr_data.get('added')
                if sonarr_added_date:
                    show.added_date = self._parse_date(sonarr_added_date)

            # Fallback to Plex added date
            if not show.added_date:
                added_at = plex_show.get('addedAt')
                if added_at:
                    show.added_date = datetime.fromtimestamp(added_at, tz=timezone.utc)

            # Map episode rating keys to show rating key
            for episode in episodes:
                ep_rating_key = str(episode.get('ratingKey'))
                episode_to_show_map[ep_rating_key] = rating_key

            merged_shows.append(show)
        logger.info(f"Merged {len(merged_shows)} TV shows.")
        return merged_shows, episode_to_show_map

    def _attach_playback_data(self, media_list: list[Media], playback_history: list[dict], episode_to_show_map: dict[str, str]):
        """Attaches Tautulli playback history to the corresponding media items."""
        media_map = {media.plex_rating_key: media for media in media_list}

        for record in playback_history:
            item_id = str(record.get('rating_key', ''))
            if not item_id:
                continue

            media_item = media_map.get(item_id)

            # If not found, it might be an episode. Find the parent show.
            if not media_item:
                show_id = episode_to_show_map.get(item_id)
                if show_id:
                    media_item = media_map.get(show_id)

            if media_item:
                # Tautulli 'date' is a unix timestamp
                playback_date = record.get('date')
                if not playback_date:
                    continue

                try:
                    parsed_date = datetime.fromtimestamp(int(playback_date), tz=timezone.utc)
                except (ValueError, TypeError, OSError):
                    logger.warning(f"Could not parse Tautulli date: {playback_date}")
                    continue

                playback = Playback(
                    playback_date=parsed_date,
                    duration=record.get('duration', 0) / 60,  # Seconds to minutes
                    user_id=str(record.get('user_id', '')),
                    user_name=record.get('friendly_name', ''),
                    item_id=item_id
                )
                media_item.playbacks.append(playback)

        logger.info("Attached playback data to media items.")

    def _parse_date(self, date_str: str) -> datetime | None:
        """Safely parses an ISO 8601 date string."""
        if not date_str:
            return None
        try:
            return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        except (ValueError, TypeError):
            logger.warning(f"Could not parse date: {date_str}. Returning None as fallback.")
            return None


if __name__ == '__main__':
    logger.info("--- Testing DataCollector ---")
    try:
        collector = DataCollector()
        all_media = collector.collect_all_media()

        if all_media:
            logger.info(f"Successfully collected {len(all_media)} media items.")

            movies = [m for m in all_media if isinstance(m, Movie)]
            shows = [m for m in all_media if isinstance(m, TVShow)]

            logger.info(f"Movies found: {len(movies)}")
            logger.info(f"TV Shows found: {len(shows)}")

            first_movie_with_playback = next((m for m in movies if m.playbacks), None)
            if first_movie_with_playback:
                logger.info("--- Example Movie ---")
                logger.info(f"Title: {first_movie_with_playback.title}")
                logger.info(f"Watch Ratio: {first_movie_with_playback.watch_ratio:.2%}")
                logger.info(f"Last Watched: {first_movie_with_playback.last_watch_date}")
                logger.info(f"Playbacks: {len(first_movie_with_playback.playbacks)}")

    except Exception as e:
        logger.error(f"An error occurred during DataCollector test: {e}", exc_info=True)
