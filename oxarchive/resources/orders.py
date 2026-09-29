"""Orders API resource (L4 order-level data)."""

from __future__ import annotations

from typing import Any, Optional

from .._params import reject_unsupported
from .._time import to_unix_ms
from ..http import HttpClient
from ..types import (
    CursorResponse,
    ResponseMeta,
    Timestamp,
    TriggerLevels,
    TriggerLevelsHistoryItem,
    _record,
)


class _OrdersBase:
    """Shared construction and symbol handling for the order resources."""

    def __init__(self, http: HttpClient, base_path: str = "/v1", coin_transform=str.upper):
        self._http = http
        self._base_path = base_path
        self._coin_transform = coin_transform

    _convert_timestamp = staticmethod(to_unix_ms)

    @staticmethod
    def _resolve_symbol(symbol: str, kwargs: dict[str, Any]) -> str:
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


class _OrderFlowResource(_OrdersBase):
    """Order history, flow and TP/SL: the routes Hyperliquid core, HIP-3 and HIP-4 share."""

    def history(
        self,
        symbol: str,
        *,
        start: Timestamp,
        end: Timestamp,
        user: Optional[str] = None,
        status: Optional[str] = None,
        order_type: Optional[str] = None,
        triggered: Optional[bool] = None,
        cursor: Optional[str] = None,
        limit: Optional[int] = None,
        **kwargs,
    ) -> CursorResponse:
        """
        Get order history.

        Args:
            symbol: The symbol (e.g., 'BTC', 'ETH')
            start: Start timestamp (required)
            end: End timestamp (required)
            user: Filter by user address
            status: Filter by order status
            order_type: Filter by order type
            triggered: ``True`` keeps only orders whose trigger fired
                (``status == "triggered"``); ``False`` excludes them. The
                API filters before paging.
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
                "triggered": triggered,
                "cursor": cursor,
                "limit": limit,
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
        user: Optional[str] = None,
        status: Optional[str] = None,
        order_type: Optional[str] = None,
        triggered: Optional[bool] = None,
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
                "triggered": triggered,
                "cursor": cursor,
                "limit": limit,
            },
        )
        return CursorResponse(
            data=data["data"],
            next_cursor=data.get("meta", {}).get("next_cursor"),
            meta=ResponseMeta.of(data),
        )

    def flow(
        self,
        symbol: str,
        *,
        start: Timestamp,
        end: Timestamp,
        interval: Optional[str] = None,
        cursor: Optional[str] = None,
        limit: Optional[int] = None,
        **kwargs,
    ) -> CursorResponse:
        """
        Get order flow aggregation, one page of time buckets.

        Buckets are labelled by their open time in UTC, and buckets with no
        events are omitted. A page holds the oldest ``limit`` buckets of the
        window. While ``has_more`` is true, pass ``next_cursor`` back as
        ``cursor`` with the same ``start``, ``end`` and ``interval``; stop
        when ``has_more`` is false.

        Args:
            symbol: The symbol (e.g., 'BTC', 'ETH')
            start: Start timestamp, inclusive (required)
            end: End timestamp, exclusive (required)
            interval: Bucket width: '1m' (default), '5m', '15m' or '1h'
            cursor: The previous response's next_cursor (a numeric
                millisecond timestamp string); pass it back unchanged
            limit: Buckets per page (default: 1000, max: 10000)

        Returns:
            CursorResponse with order flow buckets and next_cursor for pagination
        """
        symbol = self._resolve_symbol(symbol, kwargs)
        data = self._http.get(
            f"{self._base_path}/orders/{self._coin_transform(symbol)}/flow",
            params={
                "start": self._convert_timestamp(start),
                "end": self._convert_timestamp(end),
                "interval": interval,
                "cursor": cursor,
                "limit": limit,
            },
        )
        return CursorResponse(
            data=data["data"],
            next_cursor=data.get("meta", {}).get("next_cursor"),
            meta=ResponseMeta.of(data),
        )

    async def aflow(
        self,
        symbol: str,
        *,
        start: Timestamp,
        end: Timestamp,
        interval: Optional[str] = None,
        cursor: Optional[str] = None,
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
                "cursor": cursor,
                "limit": limit,
            },
        )
        return CursorResponse(
            data=data["data"],
            next_cursor=data.get("meta", {}).get("next_cursor"),
            meta=ResponseMeta.of(data),
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
        Get TP/SL history.

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
            meta=ResponseMeta.of(data),
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
            meta=ResponseMeta.of(data),
        )


class OrdersResource(_OrderFlowResource):
    """
    L4 order history, flow, TP/SL and trigger levels (Hyperliquid core and HIP-3).

    Example:
        >>> # Get order history
        >>> result = client.hyperliquid.orders.history("BTC", start="2024-01-01", end="2024-01-02")
        >>> orders = result.data
        >>>
        >>> # Get order flow aggregation
        >>> flow = client.hyperliquid.orders.flow("BTC", start="2024-01-01", end="2024-01-02")
        >>>
        >>> # Get TP/SL history
        >>> tpsl = client.hyperliquid.orders.tpsl("BTC", start="2024-01-01", end="2024-01-02")
    """

    def trigger_levels(
        self,
        symbol: str,
        *,
        range_pct: Optional[float] = None,
        buckets: Optional[int] = None,
        side: Optional[str] = None,
        **kwargs,
    ) -> TriggerLevels:
        """
        Get the pending trigger-order map for a symbol.

        Currently pending stop-loss and take-profit trigger orders grouped
        into price buckets near the current mid/mark price. Voluntary trigger
        orders, not projected forced liquidations (see
        ``liquidations.levels`` for those). The response's ``as_of`` is the
        server read time.

        Args:
            symbol: The symbol (e.g., 'BTC', or 'xyz:TSLA' on HIP-3)
            range_pct: Percentage range around the mid price (1-50, default 10)
            buckets: Number of price buckets (10-200, default 50)
            side: Side filter ('bid'/'buy'/'B' keeps bids, 'ask'/'sell'/'A' keeps asks)
        """
        symbol = self._resolve_symbol(symbol, kwargs)
        data = self._http.get(
            f"{self._base_path}/orders/{self._coin_transform(symbol)}/trigger-levels",
            params={"range_pct": range_pct, "buckets": buckets, "side": side},
        )
        return _record(TriggerLevels, data)

    async def atrigger_levels(
        self,
        symbol: str,
        *,
        range_pct: Optional[float] = None,
        buckets: Optional[int] = None,
        side: Optional[str] = None,
        **kwargs,
    ) -> TriggerLevels:
        """Async version of trigger_levels()."""
        symbol = self._resolve_symbol(symbol, kwargs)
        data = await self._http.aget(
            f"{self._base_path}/orders/{self._coin_transform(symbol)}/trigger-levels",
            params={"range_pct": range_pct, "buckets": buckets, "side": side},
        )
        return _record(TriggerLevels, data)

    def trigger_levels_history(
        self,
        symbol: str,
        *,
        start: Optional[Timestamp] = None,
        end: Optional[Timestamp] = None,
        cursor: Optional[str] = None,
        limit: Optional[int] = None,
        summary: Optional[bool] = None,
        range_pct: Optional[float] = None,
        buckets: Optional[int] = None,
        side: Optional[str] = None,
        **kwargs,
    ) -> CursorResponse[list[TriggerLevelsHistoryItem]]:
        """
        Get historical trigger-levels snapshots with cursor pagination.

        Ascending by snapshot time (15-minute cadence, retained from
        2026-07-27). Pass ``summary=True`` to list snapshots without
        histograms. Follow ``next_cursor`` as ``cursor`` for the next page.
        """
        symbol = self._resolve_symbol(symbol, kwargs)
        data = self._http.get(
            f"{self._base_path}/orders/{self._coin_transform(symbol)}/trigger-levels/history",
            params={
                "start": self._convert_timestamp(start),
                "end": self._convert_timestamp(end),
                "cursor": cursor,
                "limit": limit,
                "summary": summary,
                "range_pct": range_pct,
                "buckets": buckets,
                "side": side,
            },
        )
        return CursorResponse(
            data=[TriggerLevelsHistoryItem.model_validate(item) for item in data["data"]],
            next_cursor=data.get("meta", {}).get("next_cursor"),
            meta=ResponseMeta.of(data),
        )

    async def atrigger_levels_history(
        self,
        symbol: str,
        *,
        start: Optional[Timestamp] = None,
        end: Optional[Timestamp] = None,
        cursor: Optional[str] = None,
        limit: Optional[int] = None,
        summary: Optional[bool] = None,
        range_pct: Optional[float] = None,
        buckets: Optional[int] = None,
        side: Optional[str] = None,
        **kwargs,
    ) -> CursorResponse[list[TriggerLevelsHistoryItem]]:
        """Async version of trigger_levels_history()."""
        symbol = self._resolve_symbol(symbol, kwargs)
        data = await self._http.aget(
            f"{self._base_path}/orders/{self._coin_transform(symbol)}/trigger-levels/history",
            params={
                "start": self._convert_timestamp(start),
                "end": self._convert_timestamp(end),
                "cursor": cursor,
                "limit": limit,
                "summary": summary,
                "range_pct": range_pct,
                "buckets": buckets,
                "side": side,
            },
        )
        return CursorResponse(
            data=[TriggerLevelsHistoryItem.model_validate(item) for item in data["data"]],
            next_cursor=data.get("meta", {}).get("next_cursor"),
            meta=ResponseMeta.of(data),
        )


class Hip4OrdersResource(_OrderFlowResource):
    """
    HIP-4 L4 order history, flow and TP/SL.

    HIP-4 has no trigger-level map, so this resource has no ``trigger_levels``.

    Example:
        >>> result = client.hyperliquid.hip4.orders.history("0", start=..., end=...)
        >>> flow = client.hyperliquid.hip4.orders.flow("0", start=..., end=...)
    """


_UNSUPPORTED_SPOT_HISTORY = {
    name: "the spot order history route does not filter by it. Filter the returned rows instead."
    for name in ("user", "status", "order_type", "triggered")
}


class SpotOrdersResource(_OrdersBase):
    """
    Hyperliquid spot L4 order lifecycle history (live from 2026-05-05).

    Spot serves order history only: there is no flow, TP/SL or trigger-level
    route, and the history route takes no user, status, order-type or
    triggered filter.

    Example:
        >>> result = client.spot.orders.history("HYPE-USDC", start=..., end=...)
        >>> while result.has_more:
        ...     result = client.spot.orders.history(
        ...         "HYPE-USDC", start=..., end=..., cursor=result.next_cursor
        ...     )
    """

    def history(
        self,
        symbol: str,
        *,
        start: Timestamp,
        end: Timestamp,
        cursor: Optional[str] = None,
        limit: Optional[int] = None,
        **kwargs: Any,
    ) -> CursorResponse[list[dict[str, Any]]]:
        """
        Get spot order lifecycle history.

        Args:
            symbol: Pair symbol in dashed canonical form (e.g., 'HYPE-USDC')
            start: Start timestamp (required)
            end: End timestamp (required)
            cursor: Cursor from previous response's next_cursor
            limit: Maximum number of results

        Returns:
            CursorResponse with order data and next_cursor for pagination
        """
        symbol = self._resolve_symbol(symbol, kwargs)
        reject_unsupported("history", kwargs, _UNSUPPORTED_SPOT_HISTORY)
        data = self._http.get(
            f"{self._base_path}/orders/{self._coin_transform(symbol)}/history",
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

    async def ahistory(
        self,
        symbol: str,
        *,
        start: Timestamp,
        end: Timestamp,
        cursor: Optional[str] = None,
        limit: Optional[int] = None,
        **kwargs: Any,
    ) -> CursorResponse[list[dict[str, Any]]]:
        """Async version of history()."""
        symbol = self._resolve_symbol(symbol, kwargs)
        reject_unsupported("ahistory", kwargs, _UNSUPPORTED_SPOT_HISTORY)
        data = await self._http.aget(
            f"{self._base_path}/orders/{self._coin_transform(symbol)}/history",
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
