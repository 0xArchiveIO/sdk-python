"""HIP-3 market breadth API resource."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from ..http import HttpClient
from ..types import BreadthSnapshot, CursorResponse, Timestamp

BreadthInterval = Literal["5m", "1h", "1d"]
BREADTH_INTERVALS = frozenset({"5m", "1h", "1d"})


class BreadthResource:
    """HIP-3 percent-above-session-VWAP market breadth.

    The current route returns one validated snapshot. History defaults to the
    last 24 hours of raw one-minute snapshots; the server applies the
    last-snapshot-per-bucket rule when ``interval`` is supplied. Collection
    began on 2026-08-28, so callers must not infer synthetic pre-launch history.
    """

    def __init__(
        self,
        http: HttpClient,
        base_path: str = "/v1/hyperliquid/hip3",
    ) -> None:
        self._http = http
        self._base_path = base_path
        self._max_limit = 1000

    def _validate_limit(self, limit: Optional[int]) -> None:
        if limit is not None and not 1 <= limit <= self._max_limit:
            raise ValueError(f"limit must be between 1 and {self._max_limit} for HIP-3 breadth")

    @staticmethod
    def _validate_interval(interval: Optional[BreadthInterval]) -> None:
        if interval is not None and interval not in BREADTH_INTERVALS:
            choices = ", ".join(sorted(BREADTH_INTERVALS))
            raise ValueError(f"interval must be one of {choices} for HIP-3 breadth")

    @staticmethod
    def _convert_timestamp(ts: Optional[Timestamp]) -> Optional[int]:
        """Convert an ISO timestamp or datetime to Unix milliseconds."""
        if ts is None:
            return None
        if isinstance(ts, int):
            return ts
        if isinstance(ts, datetime):
            return int(ts.timestamp() * 1000)
        if isinstance(ts, str):
            try:
                parsed = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                return int(parsed.timestamp() * 1000)
            except ValueError:
                return int(ts)
        return None

    @staticmethod
    def _history_response(payload: dict) -> CursorResponse[list[BreadthSnapshot]]:
        return CursorResponse(
            data=[BreadthSnapshot.model_validate(item) for item in payload["data"]],
            next_cursor=payload.get("meta", {}).get("next_cursor"),
        )

    def current(self) -> BreadthSnapshot:
        """Return the latest validated HIP-3 breadth snapshot."""
        payload = self._http.get(f"{self._base_path}/breadth/above-vwap/current")
        return BreadthSnapshot.model_validate(payload["data"])

    async def acurrent(self) -> BreadthSnapshot:
        """Async version of :meth:`current`."""
        payload = await self._http.aget(f"{self._base_path}/breadth/above-vwap/current")
        return BreadthSnapshot.model_validate(payload["data"])

    def history(
        self,
        *,
        start: Optional[Timestamp] = None,
        end: Optional[Timestamp] = None,
        interval: Optional[BreadthInterval] = None,
        cursor: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> CursorResponse[list[BreadthSnapshot]]:
        """Return ascending HIP-3 breadth history with cursor pagination.

        ``start`` defaults to 24 hours before ``end`` and ``end`` defaults to
        now. ``cursor`` is the epoch-millisecond string returned by
        ``meta.next_cursor`` and is passed back unchanged. History begins on
        2026-08-28; a pre-launch window may be empty with coverage metadata.
        """
        self._validate_interval(interval)
        self._validate_limit(limit)
        payload = self._http.get(
            f"{self._base_path}/breadth/above-vwap",
            params={
                "start": self._convert_timestamp(start),
                "end": self._convert_timestamp(end),
                "interval": interval,
                "cursor": cursor,
                "limit": limit,
            },
        )
        return self._history_response(payload)

    async def ahistory(
        self,
        *,
        start: Optional[Timestamp] = None,
        end: Optional[Timestamp] = None,
        interval: Optional[BreadthInterval] = None,
        cursor: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> CursorResponse[list[BreadthSnapshot]]:
        """Async version of :meth:`history`."""
        self._validate_interval(interval)
        self._validate_limit(limit)
        payload = await self._http.aget(
            f"{self._base_path}/breadth/above-vwap",
            params={
                "start": self._convert_timestamp(start),
                "end": self._convert_timestamp(end),
                "interval": interval,
                "cursor": cursor,
                "limit": limit,
            },
        )
        return self._history_response(payload)
