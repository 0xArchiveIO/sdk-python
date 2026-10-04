"""L2 full-depth order book API resource (derived from L4 data)."""

from __future__ import annotations

from typing import Optional

from .._time import to_unix_ms
from ..http import HttpClient
from ..types import CursorResponse, ResponseMeta, Timestamp


class L2OrderBookResource:
    """
    L2 full-depth order book resource (aggregated price levels from L4 data).

    Example:
        >>> # Get current full-depth L2 orderbook
        >>> snapshot = client.hyperliquid.l2_orderbook.get("BTC")
        >>>
        >>> # Get L2 orderbook an hour ago (served from 2026-03-11 01:03 UTC)
        >>> now = datetime.now(timezone.utc)
        >>> hour_ago = now - timedelta(hours=1)
        >>> snapshot = client.hyperliquid.l2_orderbook.get("BTC", timestamp=hour_ago)
        >>>
        >>> # Get L2 orderbook history
        >>> history = client.hyperliquid.l2_orderbook.history("BTC", start=hour_ago, end=now)
    """

    def __init__(self, http: HttpClient, base_path: str = "/v1", coin_transform=str.upper):
        self._http = http
        self._base_path = base_path
        self._coin_transform = coin_transform

    _convert_timestamp = staticmethod(to_unix_ms)

    def get(
        self,
        symbol: str,
        *,
        timestamp: Optional[Timestamp] = None,
        depth: Optional[int] = None,
        **kwargs,
    ) -> dict:
        """
        Get full-depth L2 order book snapshot.

        Args:
            symbol: The symbol (e.g., 'BTC', 'ETH')
            timestamp: Optional timestamp for historical state (omit for current)
            depth: Number of price levels per side (omit for full depth)

        Returns:
            L2 order book with aggregated price levels (px, sz, n per level)
        """
        symbol = self._resolve_symbol(symbol, kwargs)
        data = self._http.get(
            f"{self._base_path}/orderbook/{self._coin_transform(symbol)}/l2",
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
            f"{self._base_path}/orderbook/{self._coin_transform(symbol)}/l2",
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
        Get L2 full-depth order book history.

        Args:
            symbol: The symbol (e.g., 'BTC', 'ETH')
            start: Start timestamp (required)
            end: End timestamp (required)
            cursor: Cursor from previous response's next_cursor
            limit: Maximum number of results
            depth: Price levels per side in each snapshot (omit for every
                level the plan allows)

        Returns:
            CursorResponse with L2 orderbook checkpoints and next_cursor for pagination
        """
        symbol = self._resolve_symbol(symbol, kwargs)
        data = self._http.get(
            f"{self._base_path}/orderbook/{self._coin_transform(symbol)}/l2/history",
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
            meta=ResponseMeta.of(data),
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
            f"{self._base_path}/orderbook/{self._coin_transform(symbol)}/l2/history",
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
            meta=ResponseMeta.of(data),
        )

    def diffs(
        self,
        symbol: str,
        *,
        start: Timestamp,
        end: Timestamp,
        cursor: Optional[str] = None,
        limit: Optional[int] = None,
        **kwargs,
    ) -> CursorResponse:
        """
        Get L2 tick-level order book diffs.

        Args:
            symbol: The symbol (e.g., 'BTC', 'ETH')
            start: Start timestamp (required)
            end: End timestamp (required)
            cursor: Cursor from previous response's next_cursor
            limit: Maximum number of results

        Returns:
            CursorResponse with L2 orderbook deltas and next_cursor for pagination
        """
        symbol = self._resolve_symbol(symbol, kwargs)
        data = self._http.get(
            f"{self._base_path}/orderbook/{self._coin_transform(symbol)}/l2/diffs",
            params={
                "start": self._convert_timestamp(start),
                "end": self._convert_timestamp(end),
                "cursor": cursor,
                "limit": limit,
            },
        )
        return CursorResponse(
            data=data["data"],
            next_cursor=data.get("meta", {}).get("next_cursor"),
            meta=ResponseMeta.of(data),
        )

    async def adiffs(
        self,
        symbol: str,
        *,
        start: Timestamp,
        end: Timestamp,
        cursor: Optional[str] = None,
        limit: Optional[int] = None,
        **kwargs,
    ) -> CursorResponse:
        """Async version of diffs()."""
        symbol = self._resolve_symbol(symbol, kwargs)
        data = await self._http.aget(
            f"{self._base_path}/orderbook/{self._coin_transform(symbol)}/l2/diffs",
            params={
                "start": self._convert_timestamp(start),
                "end": self._convert_timestamp(end),
                "cursor": cursor,
                "limit": limit,
            },
        )
        return CursorResponse(
            data=data["data"],
            next_cursor=data.get("meta", {}).get("next_cursor"),
            meta=ResponseMeta.of(data),
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
