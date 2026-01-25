"""Trades API resource."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from ..http import HttpClient
from ..types import CursorResponse, Trade, Timestamp


class TradesResource:
    """
    Trades API resource.

    Example:
        >>> # Get recent trades
        >>> trades = client.trades.recent("BTC")
        >>>
        >>> # Get trade history with cursor-based pagination (recommended)
        >>> result = client.trades.list("BTC", start="2024-01-01", end="2024-01-02")
        >>> trades = result.data
        >>>
        >>> # Get all pages
        >>> while result.next_cursor:
        ...     result = client.trades.list("BTC", start="2024-01-01", end="2024-01-02", cursor=result.next_cursor)
        ...     trades.extend(result.data)
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

    def list(
        self,
        coin: str,
        *,
        start: Timestamp,
        end: Timestamp,
        cursor: Optional[Timestamp] = None,
        limit: Optional[int] = None,
        side: Optional[Literal["buy", "sell"]] = None,
    ) -> CursorResponse[list[Trade]]:
        """
        Get trade history for a coin using cursor-based pagination.

        Uses cursor-based pagination by default, which is more efficient for large datasets.
        Use the next_cursor from the response as the cursor parameter to get the next page.

        Args:
            coin: The coin symbol (e.g., 'BTC', 'ETH')
            start: Start timestamp (required)
            end: End timestamp (required)
            cursor: Cursor from previous response's next_cursor (timestamp)
            limit: Maximum number of results (default: 100, max: 1000)
            side: Filter by trade side

        Returns:
            CursorResponse with trades and next_cursor for pagination

        Example:
            >>> # First page
            >>> result = client.trades.list("BTC", start=start, end=end, limit=1000)
            >>> trades = result.data
            >>>
            >>> # Subsequent pages
            >>> while result.next_cursor:
            ...     result = client.trades.list(
            ...         "BTC", start=start, end=end, cursor=result.next_cursor, limit=1000
            ...     )
            ...     trades.extend(result.data)
        """
        data = self._http.get(
            f"/v1/trades/{coin.upper()}",
            params={
                "start": self._convert_timestamp(start),
                "end": self._convert_timestamp(end),
                "cursor": self._convert_timestamp(cursor),
                "limit": limit,
                "side": side,
            },
        )
        return CursorResponse(
            data=[Trade.model_validate(item) for item in data["data"]],
            next_cursor=data.get("meta", {}).get("next_cursor"),
        )

    async def alist(
        self,
        coin: str,
        *,
        start: Timestamp,
        end: Timestamp,
        cursor: Optional[Timestamp] = None,
        limit: Optional[int] = None,
        side: Optional[Literal["buy", "sell"]] = None,
    ) -> CursorResponse[list[Trade]]:
        """
        Async version of list().

        Uses cursor-based pagination by default.
        """
        data = await self._http.aget(
            f"/v1/trades/{coin.upper()}",
            params={
                "start": self._convert_timestamp(start),
                "end": self._convert_timestamp(end),
                "cursor": self._convert_timestamp(cursor),
                "limit": limit,
                "side": side,
            },
        )
        return CursorResponse(
            data=[Trade.model_validate(item) for item in data["data"]],
            next_cursor=data.get("meta", {}).get("next_cursor"),
        )

    def recent(self, coin: str, limit: Optional[int] = None) -> list[Trade]:
        """
        Get most recent trades for a coin.

        Args:
            coin: The coin symbol (e.g., 'BTC', 'ETH')
            limit: Number of trades to return (default: 100)

        Returns:
            List of recent trades
        """
        data = self._http.get(
            f"/v1/trades/{coin.upper()}/recent",
            params={"limit": limit},
        )
        return [Trade.model_validate(item) for item in data["data"]]

    async def arecent(self, coin: str, limit: Optional[int] = None) -> list[Trade]:
        """Async version of recent()."""
        data = await self._http.aget(
            f"/v1/trades/{coin.upper()}/recent",
            params={"limit": limit},
        )
        return [Trade.model_validate(item) for item in data["data"]]
