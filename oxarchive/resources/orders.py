"""Orders API resource (L4 order-level data)."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from ..http import HttpClient
from ..types import CursorResponse, Timestamp


class OrdersResource:
    """
    L4 order history, flow, and TP/SL endpoints.

    Example:
        >>> # Get order history
        >>> result = client.hyperliquid.orders.history("BTC", start="2024-01-01", end="2024-01-02")
        >>> orders = result.data
        >>>
        >>> # Get order flow aggregation
        >>> flow = client.hyperliquid.orders.flow("BTC", start="2024-01-01", end="2024-01-02")
        >>>
        >>> # Get TP/SL history (Pro+ tier)
        >>> tpsl = client.hyperliquid.orders.tpsl("BTC", start="2024-01-01", end="2024-01-02")
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

    def history(
        self,
        symbol: str,
        *,
        start: Timestamp,
        end: Timestamp,
        user: Optional[str] = None,
        status: Optional[str] = None,
        order_type: Optional[str] = None,
        cursor: Optional[str] = None,
        limit: Optional[int] = None,
        **kwargs,
    ) -> CursorResponse:
        """
        Get order history (Build+ tier).

        Args:
            symbol: The symbol (e.g., 'BTC', 'ETH')
            start: Start timestamp (required)
            end: End timestamp (required)
            user: Filter by user address
            status: Filter by order status
            order_type: Filter by order type
            cursor: Cursor from previous response's next_cursor
            limit: Maximum number of results

        Returns:
            CursorResponse with order data and next_cursor for pagination
        """
        symbol = self._resolve_symbol(symbol, kwargs)
        data = self._http.get(
            f"{self._base_path}/orders/{self._coin_transform(symbol)}/history",
            params={
                "start": self._convert_timestamp(start),
                "end": self._convert_timestamp(end),
                "user": user,
                "status": status,
                "order_type": order_type,
                "cursor": cursor,
                "limit": limit,
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
        user: Optional[str] = None,
        status: Optional[str] = None,
        order_type: Optional[str] = None,
        cursor: Optional[str] = None,
        limit: Optional[int] = None,
        **kwargs,
    ) -> CursorResponse:
        """Async version of history()."""
        symbol = self._resolve_symbol(symbol, kwargs)
        data = await self._http.aget(
            f"{self._base_path}/orders/{self._coin_transform(symbol)}/history",
            params={
                "start": self._convert_timestamp(start),
                "end": self._convert_timestamp(end),
                "user": user,
                "status": status,
                "order_type": order_type,
                "cursor": cursor,
                "limit": limit,
            },
        )
        return CursorResponse(
            data=data["data"],
            next_cursor=data.get("meta", {}).get("next_cursor"),
        )

    def flow(
        self,
        symbol: str,
        *,
        start: Timestamp,
        end: Timestamp,
        interval: Optional[str] = None,
        limit: Optional[int] = None,
        **kwargs,
    ) -> CursorResponse:
        """
        Get order flow aggregation (Build+ tier).

        Args:
            symbol: The symbol (e.g., 'BTC', 'ETH')
            start: Start timestamp (required)
            end: End timestamp (required)
            interval: Aggregation interval (e.g., '1h', '4h', '1d')
            limit: Maximum number of results

        Returns:
            CursorResponse with order flow data and next_cursor for pagination
        """
        symbol = self._resolve_symbol(symbol, kwargs)
        data = self._http.get(
            f"{self._base_path}/orders/{self._coin_transform(symbol)}/flow",
            params={
                "start": self._convert_timestamp(start),
                "end": self._convert_timestamp(end),
                "interval": interval,
                "limit": limit,
            },
        )
        return CursorResponse(
            data=data["data"],
            next_cursor=data.get("meta", {}).get("next_cursor"),
        )

    async def aflow(
        self,
        symbol: str,
        *,
        start: Timestamp,
        end: Timestamp,
        interval: Optional[str] = None,
        limit: Optional[int] = None,
        **kwargs,
    ) -> CursorResponse:
        """Async version of flow()."""
        symbol = self._resolve_symbol(symbol, kwargs)
        data = await self._http.aget(
            f"{self._base_path}/orders/{self._coin_transform(symbol)}/flow",
            params={
                "start": self._convert_timestamp(start),
                "end": self._convert_timestamp(end),
                "interval": interval,
                "limit": limit,
            },
        )
        return CursorResponse(
            data=data["data"],
            next_cursor=data.get("meta", {}).get("next_cursor"),
        )

    def tpsl(
        self,
        symbol: str,
        *,
        start: Timestamp,
        end: Timestamp,
        user: Optional[str] = None,
        triggered: Optional[bool] = None,
        cursor: Optional[str] = None,
        limit: Optional[int] = None,
        **kwargs,
    ) -> CursorResponse:
        """
        Get TP/SL history (Pro+ tier).

        Args:
            symbol: The symbol (e.g., 'BTC', 'ETH')
            start: Start timestamp (required)
            end: End timestamp (required)
            user: Filter by user address
            triggered: Filter by triggered status
            cursor: Cursor from previous response's next_cursor
            limit: Maximum number of results

        Returns:
            CursorResponse with TP/SL data and next_cursor for pagination
        """
        symbol = self._resolve_symbol(symbol, kwargs)
        data = self._http.get(
            f"{self._base_path}/orders/{self._coin_transform(symbol)}/tpsl",
            params={
                "start": self._convert_timestamp(start),
                "end": self._convert_timestamp(end),
                "user": user,
                "triggered": triggered,
                "cursor": cursor,
                "limit": limit,
            },
        )
        return CursorResponse(
            data=data["data"],
            next_cursor=data.get("meta", {}).get("next_cursor"),
        )

    async def atpsl(
        self,
        symbol: str,
        *,
        start: Timestamp,
        end: Timestamp,
        user: Optional[str] = None,
        triggered: Optional[bool] = None,
        cursor: Optional[str] = None,
        limit: Optional[int] = None,
        **kwargs,
    ) -> CursorResponse:
        """Async version of tpsl()."""
        symbol = self._resolve_symbol(symbol, kwargs)
        data = await self._http.aget(
            f"{self._base_path}/orders/{self._coin_transform(symbol)}/tpsl",
            params={
                "start": self._convert_timestamp(start),
                "end": self._convert_timestamp(end),
                "user": user,
                "triggered": triggered,
                "cursor": cursor,
                "limit": limit,
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
