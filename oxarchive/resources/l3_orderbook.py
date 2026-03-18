"""L3 order book API resource (Lighter only)."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from ..http import HttpClient
from ..types import CursorResponse, Timestamp


class L3OrderBookResource:
    """
    L3 order book resource (Lighter.xyz only).

    Provides individual order-level orderbook data.

    Example:
        >>> # Get current L3 orderbook snapshot
        >>> snapshot = client.lighter.l3_orderbook.get("BTC")
        >>>
        >>> # Get L3 orderbook history
        >>> history = client.lighter.l3_orderbook.history("BTC", start="2024-01-01", end="2024-01-02")
    """

    def __init__(self, http: HttpClient, base_path: str = "/v1", coin_transform=str.upper):
        self._http = http
        self._base_path = base_path
        self._coin_transform = coin_transform

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

    def get(
        self,
        symbol: str,
        *,
        timestamp: Optional[Timestamp] = None,
        depth: Optional[int] = None,
        **kwargs,
    ) -> dict:
        """
        Get L3 order book snapshot (Lighter only).

        Args:
            symbol: The symbol (e.g., 'BTC', 'ETH')
            timestamp: Optional timestamp to get historical snapshot
            depth: Number of price levels to return per side

        Returns:
            L3 order book snapshot (dict)
        """
        symbol = self._resolve_symbol(symbol, kwargs)
        data = self._http.get(
            f"{self._base_path}/l3orderbook/{self._coin_transform(symbol)}",
            params={
                "timestamp": self._convert_timestamp(timestamp),
                "depth": depth,
            },
        )
        return data["data"]

    async def aget(
        self,
        symbol: str,
        *,
        timestamp: Optional[Timestamp] = None,
        depth: Optional[int] = None,
        **kwargs,
    ) -> dict:
        """Async version of get()."""
        symbol = self._resolve_symbol(symbol, kwargs)
        data = await self._http.aget(
            f"{self._base_path}/l3orderbook/{self._coin_transform(symbol)}",
            params={
                "timestamp": self._convert_timestamp(timestamp),
                "depth": depth,
            },
        )
        return data["data"]

    def history(
        self,
        symbol: str,
        *,
        start: Timestamp,
        end: Timestamp,
        cursor: Optional[str] = None,
        limit: Optional[int] = None,
        depth: Optional[int] = None,
        **kwargs,
    ) -> CursorResponse:
        """
        Get L3 order book history (Lighter only).

        Args:
            symbol: The symbol (e.g., 'BTC', 'ETH')
            start: Start timestamp (required)
            end: End timestamp (required)
            cursor: Cursor from previous response's next_cursor
            limit: Maximum number of results
            depth: Number of price levels per side

        Returns:
            CursorResponse with L3 orderbook snapshots and next_cursor for pagination
        """
        symbol = self._resolve_symbol(symbol, kwargs)
        data = self._http.get(
            f"{self._base_path}/l3orderbook/{self._coin_transform(symbol)}/history",
            params={
                "start": self._convert_timestamp(start),
                "end": self._convert_timestamp(end),
                "cursor": cursor,
                "limit": limit,
                "depth": depth,
            },
        )
        return CursorResponse(
            data=data["data"],
            next_cursor=data.get("meta", {}).get("next_cursor"),
        )

    async def ahistory(
        self,
        symbol: str,
        *,
        start: Timestamp,
        end: Timestamp,
        cursor: Optional[str] = None,
        limit: Optional[int] = None,
        depth: Optional[int] = None,
        **kwargs,
    ) -> CursorResponse:
        """Async version of history()."""
        symbol = self._resolve_symbol(symbol, kwargs)
        data = await self._http.aget(
            f"{self._base_path}/l3orderbook/{self._coin_transform(symbol)}/history",
            params={
                "start": self._convert_timestamp(start),
                "end": self._convert_timestamp(end),
                "cursor": cursor,
                "limit": limit,
                "depth": depth,
            },
        )
        return CursorResponse(
            data=data["data"],
            next_cursor=data.get("meta", {}).get("next_cursor"),
        )

    @staticmethod
    def _resolve_symbol(symbol, kwargs):
        import warnings

        if "coin" in kwargs:
            warnings.warn(
                "'coin' is deprecated, use 'symbol' instead",
                DeprecationWarning,
                stacklevel=3,
            )
            if symbol is None:
                symbol = kwargs.pop("coin")
            else:
                kwargs.pop("coin")
        return symbol
