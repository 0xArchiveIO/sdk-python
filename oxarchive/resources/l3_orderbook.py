"""L3 order book API resource (Lighter only)."""

from __future__ import annotations

from typing import Optional

from .._params import reject_unsupported
from .._time import to_unix_ms
from ..http import HttpClient
from ..types import CursorResponse, Timestamp
from .orderbook import LighterGranularity

_UNSUPPORTED_HISTORY = {
    "depth": (
        "history returns every resting order of each snapshot, up to 250 per side. "
        "depth applies to get() only."
    ),
}


class L3OrderBookResource:
    """
    L3 order book resource (Lighter.xyz only).

    Provides individual order-level orderbook data.

    Example:
        >>> # Get current L3 orderbook snapshot
        >>> snapshot = client.lighter.l3_orderbook.get("BTC")
        >>>
        >>> # Get L3 orderbook history
        >>> history = client.lighter.l3_orderbook.history(
        ...     "BTC", start="2026-03-05", end="2026-03-06"
        ... )
    """

    def __init__(self, http: HttpClient, base_path: str = "/v1", coin_transform=str.upper):
        self._http = http
        self._base_path = base_path
        self._coin_transform = coin_transform

    _convert_timestamp = staticmethod(to_unix_ms)

    @staticmethod
    def _validate_depth(depth: Optional[int]) -> None:
        """Validate the Lighter L3 individual-order cap per side."""
        if depth is not None and not 1 <= depth <= 250:
            raise ValueError("depth must be between 1 and 250 orders per side")

    def get(
        self,
        symbol: str,
        *,
        timestamp: Optional[Timestamp] = None,
        depth: Optional[int] = None,
        account: Optional[int] = None,
        **kwargs,
    ) -> dict:
        """
        Get L3 order book snapshot (Lighter only).

        Args:
            symbol: The symbol (e.g., 'BTC', 'ETH')
            timestamp: Optional timestamp to get historical snapshot
            depth: Maximum individual resting orders per side (1 to 250)
            account: Only the orders of this Lighter account index

        Returns:
            L3 order book snapshot (dict)
        """
        symbol = self._resolve_symbol(symbol, kwargs)
        self._validate_depth(depth)
        data = self._http.get(
            f"{self._base_path}/l3orderbook/{self._coin_transform(symbol)}",
            params={
                "timestamp": self._convert_timestamp(timestamp),
                "depth": depth,
                "account": account,
            },
        )
        return data["data"]

    async def aget(
        self,
        symbol: str,
        *,
        timestamp: Optional[Timestamp] = None,
        depth: Optional[int] = None,
        account: Optional[int] = None,
        **kwargs,
    ) -> dict:
        """Async version of get()."""
        symbol = self._resolve_symbol(symbol, kwargs)
        self._validate_depth(depth)
        data = await self._http.aget(
            f"{self._base_path}/l3orderbook/{self._coin_transform(symbol)}",
            params={
                "timestamp": self._convert_timestamp(timestamp),
                "depth": depth,
                "account": account,
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
        granularity: Optional[LighterGranularity] = None,
        account: Optional[int] = None,
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
            granularity: History resolution: 'checkpoint' (default), '30s',
                '10s', '1s' or 'tick'
            account: Only the orders of this Lighter account index

        Returns:
            CursorResponse with L3 orderbook snapshots and next_cursor for pagination
        """
        symbol = self._resolve_symbol(symbol, kwargs)
        reject_unsupported("history", kwargs, _UNSUPPORTED_HISTORY)
        data = self._http.get(
            f"{self._base_path}/l3orderbook/{self._coin_transform(symbol)}/history",
            params={
                "start": self._convert_timestamp(start),
                "end": self._convert_timestamp(end),
                "cursor": cursor,
                "limit": limit,
                "granularity": granularity,
                "account": account,
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
        granularity: Optional[LighterGranularity] = None,
        account: Optional[int] = None,
        **kwargs,
    ) -> CursorResponse:
        """Async version of history()."""
        symbol = self._resolve_symbol(symbol, kwargs)
        reject_unsupported("ahistory", kwargs, _UNSUPPORTED_HISTORY)
        data = await self._http.aget(
            f"{self._base_path}/l3orderbook/{self._coin_transform(symbol)}/history",
            params={
                "start": self._convert_timestamp(start),
                "end": self._convert_timestamp(end),
                "cursor": cursor,
                "limit": limit,
                "granularity": granularity,
                "account": account,
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
