from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Playback:
    """
    Represents a single playback event from Tautulli.
    """
    playback_date: datetime
    duration: float  # Minutes watched
    user_id: str
    user_name: str
    item_id: str  # Plex rating key

    def __repr__(self) -> str:
        """
        Provides a developer-friendly representation of the Playback object.
        """
        return (
            f"Playback(item_id='{self.item_id}', user='{self.user_name}', "
            f"date='{self.playback_date.strftime('%Y-%m-%d')}', duration={self.duration}m)"
        )


if __name__ == '__main__':
    # Example usage for testing the dataclass

    # Create a sample playback record
    sample_playback = Playback(
        playback_date=datetime.now(),
        duration=45,
        user_id="user123",
        user_name="testuser",
        item_id="item789"
    )

    # Print the object and its representation
    print("--- Testing Playback Dataclass ---")
    print(f"Playback Object: {sample_playback}")
    print(f"Item ID: {sample_playback.item_id}")
    print(f"User: {sample_playback.user_name}")
    print("---------------------------------")
