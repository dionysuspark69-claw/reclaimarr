from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import niquests
from tenacity import (
    retry,
    retry_if_exception,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from backend.core.logger import LOG
from backend.core.utils.request import should_retry_on_status


@dataclass(slots=True, frozen=True)
class TautulliWatchRecord:
    """A single watch history record from Tautulli."""

    rating_key: str
    parent_rating_key: str | None
    grandparent_rating_key: str | None
    media_type: str  # "movie", "episode", "track"
    title: str
    full_title: str
    user_id: int
    friendly_name: str
    date: int  # unix timestamp
    duration: int  # seconds
    watched_status: float  # 0-1 completion


class TautulliClient:
    """Client for the Tautulli API (Plex watch statistics)."""

    def __init__(self, api_key: str, base_url: str) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.session = niquests.AsyncSession()

    @retry(
        stop=stop_after_attempt(4),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=(
            retry_if_exception_type((ConnectionError, TimeoutError))
            | retry_if_exception(should_retry_on_status)
        ),
    )
    async def _make_request(
        self, cmd: str, extra_params: dict[str, Any] | None = None
    ) -> dict | list | None:
        """Make a request to the Tautulli API.

        Args:
            cmd: Tautulli API command (e.g., "get_history").
            extra_params: Additional query parameters.

        Returns:
            The 'data' portion of the response, or None on failure.
        """
        params: dict[str, Any] = {"apikey": self.api_key, "cmd": cmd}
        if extra_params:
            params.update(extra_params)

        url = f"{self.base_url}/api/v2"
        response = await self.session.get(url, params=params)
        response.raise_for_status()

        result = response.json()
        resp = result.get("response", {})
        if resp.get("result") != "success":
            raise ValueError(
                f"Tautulli API error for cmd '{cmd}': {resp.get('message', 'Unknown error')}"
            )
        return resp.get("data")

    async def health(self) -> bool:
        """Check server health and API key."""
        try:
            data = await self._make_request("get_tautulli_info")
            return data is not None
        except Exception:
            return False

    async def get_history(
        self,
        length: int = 5000,
        start: int = 0,
        media_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch playback history from Tautulli with pagination.

        Args:
            length: Number of records per page.
            start: Starting offset.
            media_type: Optional filter ("movie", "episode", etc.).

        Returns:
            List of raw history record dicts.
        """
        params: dict[str, Any] = {"length": length, "start": start}
        if media_type:
            params["media_type"] = media_type

        data = await self._make_request("get_history", params)
        if not isinstance(data, dict):
            return []
        return data.get("data", [])

    async def get_all_history(
        self, media_type: str | None = None
    ) -> list[dict[str, Any]]:
        """Fetch all playback history, handling pagination.

        Args:
            media_type: Optional filter ("movie", "episode", etc.).

        Returns:
            Complete list of history records.
        """
        all_records: list[dict[str, Any]] = []
        page_size = 5000
        start = 0

        while True:
            params: dict[str, Any] = {"length": page_size, "start": start}
            if media_type:
                params["media_type"] = media_type

            data = await self._make_request("get_history", params)
            if not isinstance(data, dict):
                break

            records = data.get("data", [])
            if not records:
                break

            all_records.extend(records)
            total = data.get("recordsFiltered", 0)

            if len(all_records) >= total:
                break

            start += page_size

        return all_records

    async def get_item_watch_stats(
        self, rating_key: str
    ) -> dict[str, Any] | None:
        """Get aggregated watch statistics for a specific item.

        Args:
            rating_key: Plex rating key for the item.

        Returns:
            Watch statistics dict or None.
        """
        data = await self._make_request(
            "get_item_watch_time_stats",
            {"rating_key": rating_key, "grouping": 1},
        )
        if isinstance(data, list) and data:
            return data[0]
        return None

    @staticmethod
    async def test_service(url: str, api_key: str) -> bool:
        """Test Tautulli service connection without full initialization."""
        async with niquests.AsyncSession() as session:
            response = await session.get(
                f"{url.rstrip('/')}/api/v2",
                params={"apikey": api_key, "cmd": "get_tautulli_info"},
            )
            response.raise_for_status()
            result = response.json()
            resp = result.get("response", {})
            if resp.get("result") == "success":
                return True
            raise ValueError(f"Tautulli test failed: {resp.get('message', 'Unknown error')}")
