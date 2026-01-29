"""Order book API resource."""

from __future__ import annotations

from datetime import datetime
from typing import Optional, Union

from ..http import HttpClient
from typing import Literal

from ..types import CursorResponse, OrderBook, Timestamp

# Lighter orderbook granularity levels (Lighter.xyz only)
LighterGranularity = Literal["checkpoint", "30s", "10s", "1s", "tick"]


class OrderBookResource:
    """
    Order book API resource.

    Example:
        >>> # Get current order book (Hyperliquid)
        >>> orderbook = client.hyperliquid.orderbook.get("BTC")
        >>>
        >>> # Get order book at specific timestamp
        >>> historical = client.hyperliquid.orderbook.get("ETH", timestamp=1704067200000)
        >>>
        >>> # Get order book history
        >>> history = client.hyperliquid.orderbook.history("BTC", start="2024-01-01", end="2024-01-02")
        >>>
        >>> # Lighter.xyz order book
        >>> lighter_ob = client.lighter.orderbook.get("BTC")
    """

    def __init__(self, http: HttpClient, base_path: str = "/v1"):
        self._http = http
        self._base_path = base_path

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
            f"{self._base_path}/orderbook/{coin.upper()}",
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
            f"{self._base_path}/orderbook/{coin.upper()}",
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
        granularity: Optional[LighterGranularity] = None,
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
            granularity: Data resolution for Lighter orderbook (Lighter.xyz only, ignored for Hyperliquid).
                Options: 'checkpoint' (1min, default), '30s', '10s', '1s', 'tick'.
                Tier restrictions apply. Credit multipliers: checkpoint=1x, 30s=2x, 10s=3x, 1s=10x, tick=20x.

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
            >>>
            >>> # Lighter.xyz with 10s granularity (Build+ tier)
            >>> result = client.lighter.orderbook.history(
            ...     "BTC", start=start, end=end, granularity="10s"
            ... )
        """
        data = self._http.get(
            f"{self._base_path}/orderbook/{coin.upper()}/history",
            params={
                "start": self._convert_timestamp(start),
                "end": self._convert_timestamp(end),
                "cursor": self._convert_timestamp(cursor),
                "limit": limit,
                "depth": depth,
                "granularity": granularity,
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
        granularity: Optional[LighterGranularity] = None,
    ) -> CursorResponse[list[OrderBook]]:
        """Async version of history(). start and end are required. See history() for granularity details."""
        data = await self._http.aget(
            f"{self._base_path}/orderbook/{coin.upper()}/history",
            params={
                "start": self._convert_timestamp(start),
                "end": self._convert_timestamp(end),
                "cursor": self._convert_timestamp(cursor),
                "limit": limit,
                "depth": depth,
                "granularity": granularity,
            },
        )
        return CursorResponse(
            data=[OrderBook.model_validate(item) for item in data["data"]],
            next_cursor=data.get("meta", {}).get("next_cursor"),
        )
