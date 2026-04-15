from dataclasses import dataclass, field
from datetime import datetime
from .playback import Playback


@dataclass
class Media:
    """
    Base class for a media item in the library.
    """
    plex_rating_key: str
    title: str
    added_date: datetime | None
    file_size: int  # In bytes

    # Playback data from Tautulli
    playbacks: list[Playback] = field(default_factory=list)

    # Calculated fields
    watch_ratio: float = 0.0
    last_watch_date: datetime | None = None

    def __post_init__(self):
        """Calculate metrics after the object is initialized."""
        self.calculate_last_watch_date()

    def calculate_last_watch_date(self):
        """
        Determines the most recent watch date from all playbacks.
        """
        if not self.playbacks:
            self.last_watch_date = None
            return

        self.last_watch_date = max(p.playback_date for p in self.playbacks)

    def get_total_watch_time(self) -> float:
        """
        Calculates the total time watched for this media item in minutes.
        """
        return sum(p.duration for p in self.playbacks)

    def calculate_watch_ratio(self):
        """
        Placeholder for watch ratio calculation. Must be implemented in subclasses.
        """
        raise NotImplementedError("Watch ratio calculation must be implemented in a subclass.")

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(title='{self.title}', added='{self.added_date.date()}')"


@dataclass
class Movie(Media):
    """
    Represents a Movie, inheriting from Media.
    """
    radarr_id: int | None = None
    duration: float = 0.0  # In minutes

    def calculate_watch_ratio(self):
        """
        Calculates the watch ratio for a movie.
        Ratio = (total time watched) / (total duration)
        """
        if self.duration > 0:
            total_watch_time = self.get_total_watch_time()
            self.watch_ratio = total_watch_time / self.duration
        else:
            self.watch_ratio = 0.0


@dataclass
class TVShow(Media):
    """
    Represents a TV Show, inheriting from Media.
    """
    sonarr_id: int | None = None
    total_duration: float = 0.0  # Sum of all episode durations in minutes
    total_episodes: int = 0

    def calculate_watch_ratio(self):
        """
        Calculates the watch ratio for a TV show.
        Ratio = (total time watched across all episodes) / (total duration of all episodes)
        """
        if self.total_duration > 0:
            total_watch_time = self.get_total_watch_time()
            self.watch_ratio = total_watch_time / self.total_duration
        else:
            self.watch_ratio = 0.0


if __name__ == '__main__':
    # Example usage for testing the media models

    print("--- Testing Media Models ---")

    # --- Movie Test ---
    movie_playbacks = [
        Playback(datetime(2023, 1, 15), 90, "user1", "Alice", "movie1"),
        Playback(datetime(2023, 5, 20), 30, "user2", "Bob", "movie1"),
    ]

    test_movie = Movie(
        plex_rating_key="movie1",
        title="Test Movie",
        added_date=datetime(2023, 1, 1),
        file_size=4 * 1024**3,  # 4 GB
        duration=125,
        playbacks=movie_playbacks
    )
    test_movie.calculate_watch_ratio()

    print("\n--- Movie Example ---")
    print(f"Movie: {test_movie}")
    print(f"Total watch time: {test_movie.get_total_watch_time()} minutes")
    print(f"Last watch date: {test_movie.last_watch_date.date() if test_movie.last_watch_date else 'Never'}")
    print(f"Watch ratio: {test_movie.watch_ratio:.2%}")

    # --- TV Show Test ---
    show_playbacks = [
        Playback(datetime(2022, 10, 5), 22, "user1", "Alice", "show1_ep1"),
        Playback(datetime(2022, 10, 6), 23, "user1", "Alice", "show1_ep2"),
        Playback(datetime(2023, 8, 1), 15, "user3", "Charlie", "show1_ep3"),  # Partial watch
    ]

    test_show = TVShow(
        plex_rating_key="show1",
        title="Test Show",
        added_date=datetime(2022, 9, 1),
        file_size=20 * 1024**3,  # 20 GB
        total_duration=10 * 24,  # 10 episodes, 24 mins each
        total_episodes=10,
        playbacks=show_playbacks
    )
    test_show.calculate_watch_ratio()

    print("\n--- TV Show Example ---")
    print(f"TV Show: {test_show}")
    print(f"Total watch time: {test_show.get_total_watch_time()} minutes")
    print(f"Last watch date: {test_show.last_watch_date.date() if test_show.last_watch_date else 'Never'}")
    print(f"Watch ratio: {test_show.watch_ratio:.2%}")

    print("\n------------------------")
