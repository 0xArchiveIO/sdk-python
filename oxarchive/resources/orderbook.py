"""Order book API resource."""

from __future__ import annotations

from datetime import datetime
from typing import Optional, Union

from ..http import HttpClient
from ..types import CursorResponse, OrderBook, Timestamp


class OrderBookResource:
    """
    Order book API resource.

    Example:
        >>> # Get current order book
        >>> orderbook = client.orderbook.get("BTC")
        >>>
        >>> # Get order book at specific timestamp
        >>> historical = client.orderbook.get("ETH", timestamp=1704067200000)
        >>>
        >>> # Get order book history
        >>> history = client.orderbook.history("BTC", start="2024-01-01", end="2024-01-02")
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
            # Try parsing ISO format
            try:
                dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                return int(dt.timestamp() * 1000)
            except ValueError:
                return int(ts)
        return None

    def get(
        self,
        coin: str,
        *,
        timestamp: Optional[Timestamp] = None,
        depth: Optional[int] = None,
    ) -> OrderBook:
        """
        Get order book snapshot for a coin.

        Args:
            coin: The coin symbol (e.g., 'BTC', 'ETH')
            timestamp: Optional timestamp to get historical snapshot
            depth: Number of price levels to return per side

        Returns:
            Order book snapshot
        """
        data = self._http.get(
            f"/v1/orderbook/{coin.upper()}",
            params={
                "timestamp": self._convert_timestamp(timestamp),
                "depth": depth,
            },
        )
        return OrderBook.model_validate(data["data"])

    async def aget(
        self,
        coin: str,
        *,
        timestamp: Optional[Timestamp] = None,
        depth: Optional[int] = None,
    ) -> OrderBook:
        """Async version of get()."""
        data = await self._http.aget(
            f"/v1/orderbook/{coin.upper()}",
            params={
                "timestamp": self._convert_timestamp(timestamp),
                "depth": depth,
            },
        )
        return OrderBook.model_validate(data["data"])

    def history(
        self,
        coin: str,
        *,
        start: Timestamp,
        end: Timestamp,
        cursor: Optional[Timestamp] = None,
        limit: Optional[int] = None,
        depth: Optional[int] = None,
    ) -> CursorResponse[list[OrderBook]]:
        """
        Get historical order book snapshots with cursor-based pagination.

        Args:
            coin: The coin symbol (e.g., 'BTC', 'ETH')
            start: Start timestamp (required)
            end: End timestamp (required)
            cursor: Cursor from previous response's next_cursor (timestamp)
            limit: Maximum number of results (default: 100, max: 1000)
            depth: Number of price levels per side

        Returns:
            CursorResponse with order book snapshots and next_cursor for pagination

        Example:
            >>> result = client.orderbook.history("BTC", start=start, end=end, limit=1000)
            >>> snapshots = result.data
            >>> while result.next_cursor:
            ...     result = client.orderbook.history(
            ...         "BTC", start=start, end=end, cursor=result.next_cursor, limit=1000
            ...     )
            ...     snapshots.extend(result.data)
        """
        data = self._http.get(
            f"/v1/orderbook/{coin.upper()}/history",
            params={
                "start": self._convert_timestamp(start),
                "end": self._convert_timestamp(end),
                "cursor": self._convert_timestamp(cursor),
                "limit": limit,
                "depth": depth,
            },
        )
        return CursorResponse(
            data=[OrderBook.model_validate(item) for item in data["data"]],
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
        depth: Optional[int] = None,
    ) -> CursorResponse[list[OrderBook]]:
        """Async version of history(). start and end are required."""
        data = await self._http.aget(
            f"/v1/orderbook/{coin.upper()}/history",
            params={
                "start": self._convert_timestamp(start),
                "end": self._convert_timestamp(end),
                "cursor": self._convert_timestamp(cursor),
                "limit": limit,
                "depth": depth,
            },
        )
        return CursorResponse(
            data=[OrderBook.model_validate(item) for item in data["data"]],
            next_cursor=data.get("meta", {}).get("next_cursor"),
        )
