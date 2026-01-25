"""Funding rates API resource."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from ..http import HttpClient
from ..types import CursorResponse, FundingRate, Timestamp


class FundingResource:
    """
    Funding rates API resource.

    Example:
        >>> # Get current funding rate
        >>> current = client.funding.current("BTC")
        >>>
        >>> # Get funding rate history
        >>> history = client.funding.history("ETH", start="2024-01-01", end="2024-01-07")
    """

    def __init__(self, http: HttpClient):
        self._http = http

    def _convert_timestamp(self, ts: Optional[Timestamp]) -> Optional[int]:
        """Convert timestamp to Unix milliseconds."""
        if ts is None:
            return None
        if isinstance(ts, int):
            return ts
        if isinstance(ts, datetime):
            return int(ts.timestamp() * 1000)
        if isinstance(ts, str):
            try:
                dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                return int(dt.timestamp() * 1000)
            except ValueError:
                return int(ts)
        return None

    def history(
        self,
        coin: str,
        *,
        start: Timestamp,
        end: Timestamp,
        cursor: Optional[Timestamp] = None,
        limit: Optional[int] = None,
    ) -> CursorResponse[list[FundingRate]]:
        """
        Get funding rate history for a coin with cursor-based pagination.

        Args:
            coin: The coin symbol (e.g., 'BTC', 'ETH')
            start: Start timestamp (required)
            end: End timestamp (required)
            cursor: Cursor from previous response's next_cursor (timestamp)
            limit: Maximum number of results (default: 100, max: 1000)

        Returns:
            CursorResponse with funding rate records and next_cursor for pagination

        Example:
            >>> result = client.funding.history("BTC", start=start, end=end, limit=1000)
            >>> rates = result.data
            >>> while result.next_cursor:
            ...     result = client.funding.history(
            ...         "BTC", start=start, end=end, cursor=result.next_cursor, limit=1000
            ...     )
            ...     rates.extend(result.data)
        """
        data = self._http.get(
            f"/v1/funding/{coin.upper()}",
            params={
                "start": self._convert_timestamp(start),
                "end": self._convert_timestamp(end),
                "cursor": self._convert_timestamp(cursor),
                "limit": limit,
            },
        )
        return CursorResponse(
            data=[FundingRate.model_validate(item) for item in data["data"]],
            next_cursor=data.get("meta", {}).get("next_cursor"),
        )

    async def ahistory(
        self,
        coin: str,
        *,
        start: Timestamp,
        end: Timestamp,
        cursor: Optional[Timestamp] = None,
        limit: Optional[int] = None,
    ) -> CursorResponse[list[FundingRate]]:
        """Async version of history(). start and end are required."""
        data = await self._http.aget(
            f"/v1/funding/{coin.upper()}",
            params={
                "start": self._convert_timestamp(start),
                "end": self._convert_timestamp(end),
                "cursor": self._convert_timestamp(cursor),
                "limit": limit,
            },
        )
        return CursorResponse(
            data=[FundingRate.model_validate(item) for item in data["data"]],
            next_cursor=data.get("meta", {}).get("next_cursor"),
        )

    def current(self, coin: str) -> FundingRate:
        """
        Get current funding rate for a coin.

        Args:
            coin: The coin symbol (e.g., 'BTC', 'ETH')

        Returns:
            Current funding rate
        """
        data = self._http.get(f"/v1/funding/{coin.upper()}/current")
        return FundingRate.model_validate(data["data"])

    async def acurrent(self, coin: str) -> FundingRate:
        """Async version of current()."""
        data = await self._http.aget(f"/v1/funding/{coin.upper()}/current")
        return FundingRate.model_validate(data["data"])
