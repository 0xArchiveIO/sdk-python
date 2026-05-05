"""Trades API resource."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from ..http import HttpClient
from ..types import CursorResponse, OxArchiveError, Trade, Timestamp


class TradesResource:
    """
    Trades API resource.

    Example:
        >>> # Get trade history with cursor-based pagination (recommended)
        >>> result = client.hyperliquid.trades.list("BTC", start="2024-01-01", end="2024-01-02")
        >>> trades = result.data
        >>>
        >>> # Get all pages
        >>> while result.next_cursor:
        ...     result = client.hyperliquid.trades.list("BTC", start="2024-01-01", end="2024-01-02", cursor=result.next_cursor)
        ...     trades.extend(result.data)
        >>>
        >>> # Get recent trades (Lighter only - has real-time data)
        >>> recent = client.lighter.trades.recent("BTC")
    """

    def __init__(
        self,
        http: HttpClient,
        base_path: str = "/v1",
        coin_transform=str.upper,
        *,
        allow_recent: bool = True,
    ):
        self._http = http
        self._base_path = base_path
        self._coin_transform = coin_transform
        # Hyperliquid has hourly fills backfill, not real-time, so the backend
        # does not expose ``/trades/{symbol}/recent`` for the bare Hyperliquid
        # namespace. Setting ``allow_recent=False`` makes the SDK fail fast
        # with a clear pointer instead of letting the user 404 against the API.
        self._allow_recent = allow_recent

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
        symbol: str,
        *,
        start: Timestamp,
        end: Timestamp,
        cursor: Optional[Timestamp] = None,
        limit: Optional[int] = None,
        side: Optional[Literal["buy", "sell"]] = None,
        **kwargs,
    ) -> CursorResponse[list[Trade]]:
        """
        Get trade history for a symbol using cursor-based pagination.

        Uses cursor-based pagination by default, which is more efficient for large datasets.
        Use the next_cursor from the response as the cursor parameter to get the next page.

        Args:
            symbol: The symbol (e.g., 'BTC', 'ETH')
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
        symbol = self._resolve_symbol(symbol, kwargs)
        data = self._http.get(
            f"{self._base_path}/trades/{self._coin_transform(symbol)}",
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
        symbol: str,
        *,
        start: Timestamp,
        end: Timestamp,
        cursor: Optional[Timestamp] = None,
        limit: Optional[int] = None,
        side: Optional[Literal["buy", "sell"]] = None,
        **kwargs,
    ) -> CursorResponse[list[Trade]]:
        """
        Async version of list().

        Uses cursor-based pagination by default.
        """
        symbol = self._resolve_symbol(symbol, kwargs)
        data = await self._http.aget(
            f"{self._base_path}/trades/{self._coin_transform(symbol)}",
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

    def recent(self, symbol: str, limit: Optional[int] = None, **kwargs) -> list[Trade]:
        """
        Get most recent trades for a symbol.

        Note: This method is available for Lighter (``client.lighter.trades.recent()``),
        HIP-3 (``client.hyperliquid.hip3.trades.recent()``), and HIP-4
        (``client.hyperliquid.hip4.trades.recent()``), all of which have
        real-time data ingestion. Hyperliquid uses hourly S3 backfill so this
        endpoint is not exposed for the bare Hyperliquid namespace; calling
        ``client.hyperliquid.trades.recent()`` raises :class:`OxArchiveError`.

        Args:
            symbol: The symbol (e.g., 'BTC', 'ETH')
            limit: Number of trades to return (default: 100)

        Returns:
            List of recent trades
        """
        if not self._allow_recent:
            raise OxArchiveError(
                "trades.recent() is not available for Hyperliquid (hourly S3 "
                "backfill). Use client.hyperliquid.trades.list(symbol, "
                "start=..., end=...) for trade history, or "
                "client.lighter.trades.recent() / "
                "client.hyperliquid.hip3.trades.recent() / "
                "client.hyperliquid.hip4.trades.recent() for venues with "
                "real-time data.",
                404,
            )
        symbol = self._resolve_symbol(symbol, kwargs)
        data = self._http.get(
            f"{self._base_path}/trades/{self._coin_transform(symbol)}/recent",
            params={"limit": limit},
        )
        return [Trade.model_validate(item) for item in data["data"]]

    async def arecent(self, symbol: str, limit: Optional[int] = None, **kwargs) -> list[Trade]:
        """Async version of recent()."""
        if not self._allow_recent:
            raise OxArchiveError(
                "trades.recent() is not available for Hyperliquid (hourly S3 "
                "backfill). Use client.hyperliquid.trades.alist(symbol, "
                "start=..., end=...) for trade history, or "
                "client.lighter.trades.arecent() / "
                "client.hyperliquid.hip3.trades.arecent() / "
                "client.hyperliquid.hip4.trades.arecent() for venues with "
                "real-time data.",
                404,
            )
        symbol = self._resolve_symbol(symbol, kwargs)
        data = await self._http.aget(
            f"{self._base_path}/trades/{self._coin_transform(symbol)}/recent",
            params={"limit": limit},
        )
        return [Trade.model_validate(item) for item in data["data"]]

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
