"""Liquidations API resource."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from ..http import HttpClient
from ..types import (
    CursorResponse,
    Liquidation,
    LiquidationLevels,
    LiquidationLevelsHistoryItem,
    LiquidationVolume,
    Timestamp,
)


class LiquidationsResource:
    """
    Liquidations API resource.

    Retrieve historical liquidation events from Hyperliquid.

    Note: Liquidation data is available from May 25, 2025 onwards.

    Example:
        >>> # Get recent liquidations
        >>> liquidations = client.hyperliquid.liquidations.history(
        ...     "BTC",
        ...     start="2025-06-01",
        ...     end="2025-06-02"
        ... )
        >>>
        >>> # Get liquidations for a specific user
        >>> user_liquidations = client.hyperliquid.liquidations.by_user(
        ...     "0x1234...",
        ...     start="2025-06-01",
        ...     end="2025-06-02"
        ... )
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
        cursor: Optional[str] = None,
        limit: Optional[int] = None,
        **kwargs,
    ) -> CursorResponse[list[Liquidation]]:
        """
        Get liquidation history for a symbol with cursor-based pagination.

        Args:
            symbol: The symbol (e.g., 'BTC', 'ETH')
            start: Start timestamp (required)
            end: End timestamp (required)
            cursor: Cursor from previous response's next_cursor
            limit: Maximum number of results (default: 100, max: 1000)

        Returns:
            CursorResponse with liquidation records and next_cursor for pagination

        Example:
            >>> result = client.hyperliquid.liquidations.history("BTC", start=start, end=end, limit=1000)
            >>> liquidations = result.data
            >>> while result.next_cursor:
            ...     result = client.hyperliquid.liquidations.history(
            ...         "BTC", start=start, end=end, cursor=result.next_cursor, limit=1000
            ...     )
            ...     liquidations.extend(result.data)
        """
        symbol = self._resolve_symbol(symbol, kwargs)
        data = self._http.get(
            f"{self._base_path}/liquidations/{self._coin_transform(symbol)}",
            params={
                "start": self._convert_timestamp(start),
                "end": self._convert_timestamp(end),
                "cursor": cursor,
                "limit": limit,
            },
        )
        return CursorResponse(
            data=[Liquidation.model_validate(item) for item in data["data"]],
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
        **kwargs,
    ) -> CursorResponse[list[Liquidation]]:
        """Async version of history(). start and end are required."""
        symbol = self._resolve_symbol(symbol, kwargs)
        data = await self._http.aget(
            f"{self._base_path}/liquidations/{self._coin_transform(symbol)}",
            params={
                "start": self._convert_timestamp(start),
                "end": self._convert_timestamp(end),
                "cursor": cursor,
                "limit": limit,
            },
        )
        return CursorResponse(
            data=[Liquidation.model_validate(item) for item in data["data"]],
            next_cursor=data.get("meta", {}).get("next_cursor"),
        )

    def by_user(
        self,
        user_address: str,
        *,
        start: Timestamp,
        end: Timestamp,
        symbol: Optional[str] = None,
        cursor: Optional[str] = None,
        limit: Optional[int] = None,
        **kwargs,
    ) -> CursorResponse[list[Liquidation]]:
        """
        Get liquidation history for a specific user.

        This returns liquidations where the user was either:
        - The liquidated party (their position was liquidated)
        - The liquidator (they executed the liquidation)

        Args:
            user_address: User's wallet address (e.g., '0x1234...')
            start: Start timestamp (required)
            end: End timestamp (required)
            symbol: Optional symbol filter (e.g., 'BTC', 'ETH')
            cursor: Cursor from previous response's next_cursor
            limit: Maximum number of results (default: 100, max: 1000)

        Returns:
            CursorResponse with liquidation records and next_cursor for pagination
        """
        # Handle deprecated 'coin' kwarg for the symbol filter
        if "coin" in kwargs:
            import warnings

            warnings.warn(
                "'coin' is deprecated, use 'symbol' instead",
                DeprecationWarning,
                stacklevel=2,
            )
            if symbol is None:
                symbol = kwargs.pop("coin")
            else:
                kwargs.pop("coin")

        params = {
            "start": self._convert_timestamp(start),
            "end": self._convert_timestamp(end),
            "cursor": cursor,
            "limit": limit,
        }
        if symbol:
            params["coin"] = symbol.upper()

        data = self._http.get(
            f"{self._base_path}/liquidations/user/{user_address}",
            params=params,
        )
        return CursorResponse(
            data=[Liquidation.model_validate(item) for item in data["data"]],
            next_cursor=data.get("meta", {}).get("next_cursor"),
        )

    async def aby_user(
        self,
        user_address: str,
        *,
        start: Timestamp,
        end: Timestamp,
        symbol: Optional[str] = None,
        cursor: Optional[str] = None,
        limit: Optional[int] = None,
        **kwargs,
    ) -> CursorResponse[list[Liquidation]]:
        """Async version of by_user()."""
        # Handle deprecated 'coin' kwarg for the symbol filter
        if "coin" in kwargs:
            import warnings

            warnings.warn(
                "'coin' is deprecated, use 'symbol' instead",
                DeprecationWarning,
                stacklevel=2,
            )
            if symbol is None:
                symbol = kwargs.pop("coin")
            else:
                kwargs.pop("coin")

        params = {
            "start": self._convert_timestamp(start),
            "end": self._convert_timestamp(end),
            "cursor": cursor,
            "limit": limit,
        }
        if symbol:
            params["coin"] = symbol.upper()

        data = await self._http.aget(
            f"{self._base_path}/liquidations/user/{user_address}",
            params=params,
        )
        return CursorResponse(
            data=[Liquidation.model_validate(item) for item in data["data"]],
            next_cursor=data.get("meta", {}).get("next_cursor"),
        )

    def volume(
        self,
        symbol: str,
        *,
        start: Optional[Timestamp] = None,
        end: Optional[Timestamp] = None,
        interval: Optional[str] = None,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
        **kwargs,
    ) -> CursorResponse[list[LiquidationVolume]]:
        """
        Get pre-aggregated liquidation volume for a symbol.

        Args:
            symbol: The symbol (e.g., 'BTC', 'ETH')
            start: Start timestamp
            end: End timestamp
            interval: Aggregation interval (e.g., '1h', '1d')
            limit: Maximum number of results (default: 100, max: 1000)
            cursor: Cursor from previous response's next_cursor

        Returns:
            CursorResponse with liquidation volume buckets and next_cursor for pagination

        Example:
            >>> result = client.hyperliquid.liquidations.volume("BTC", start="2025-06-01", end="2025-06-02")
            >>> for bucket in result.data:
            ...     print(f"{bucket.timestamp}: ${bucket.total_usd:.0f} ({bucket.count} liquidations)")
        """
        symbol = self._resolve_symbol(symbol, kwargs)
        data = self._http.get(
            f"{self._base_path}/liquidations/{self._coin_transform(symbol)}/volume",
            params={
                "start": self._convert_timestamp(start),
                "end": self._convert_timestamp(end),
                "interval": interval,
                "limit": limit,
                "cursor": cursor,
            },
        )
        return CursorResponse(
            data=[LiquidationVolume.model_validate(item) for item in data["data"]],
            next_cursor=data.get("meta", {}).get("next_cursor"),
        )

    async def avolume(
        self,
        symbol: str,
        *,
        start: Optional[Timestamp] = None,
        end: Optional[Timestamp] = None,
        interval: Optional[str] = None,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
        **kwargs,
    ) -> CursorResponse[list[LiquidationVolume]]:
        """Async version of volume()."""
        symbol = self._resolve_symbol(symbol, kwargs)
        data = await self._http.aget(
            f"{self._base_path}/liquidations/{self._coin_transform(symbol)}/volume",
            params={
                "start": self._convert_timestamp(start),
                "end": self._convert_timestamp(end),
                "interval": interval,
                "limit": limit,
                "cursor": cursor,
            },
        )
        return CursorResponse(
            data=[LiquidationVolume.model_validate(item) for item in data["data"]],
            next_cursor=data.get("meta", {}).get("next_cursor"),
        )


    def levels(
        self,
        symbol: str,
        *,
        range_pct: Optional[float] = None,
        buckets: Optional[int] = None,
        side: Optional[str] = None,
        at: Optional[int] = None,
        **kwargs,
    ) -> LiquidationLevels:
        """
        Get projected forced-liquidation levels for a symbol.

        Computed from clearinghouse positions and margin state, bucketed
        around the snapshot mark price. Snapshots refresh approximately every
        five minutes; pass ``at`` (epoch ms) for a point-in-time read. History
        begins 2026-07-27.

        These are projected forced liquidations, not the pending
        trigger-order map (see ``orders.trigger_levels`` for that).

        Args:
            symbol: The symbol (e.g., 'BTC', or 'xyz:TSLA' on HIP-3)
            range_pct: Percentage range around the mark price (1-50, default 10)
            buckets: Number of price buckets (10-200, default 50)
            side: Side filter ('bid'/'buy'/'B' keeps longs, 'ask'/'sell'/'A' keeps shorts)
            at: Point-in-time read, epoch ms (newest snapshot at or before)
        """
        symbol = self._resolve_symbol(symbol, kwargs)
        data = self._http.get(
            f"{self._base_path}/liquidations/{self._coin_transform(symbol)}/levels",
            params={"range_pct": range_pct, "buckets": buckets, "side": side, "at": at},
        )
        return LiquidationLevels.model_validate(data["data"])

    async def alevels(
        self,
        symbol: str,
        *,
        range_pct: Optional[float] = None,
        buckets: Optional[int] = None,
        side: Optional[str] = None,
        at: Optional[int] = None,
        **kwargs,
    ) -> LiquidationLevels:
        """Async version of levels()."""
        symbol = self._resolve_symbol(symbol, kwargs)
        data = await self._http.aget(
            f"{self._base_path}/liquidations/{self._coin_transform(symbol)}/levels",
            params={"range_pct": range_pct, "buckets": buckets, "side": side, "at": at},
        )
        return LiquidationLevels.model_validate(data["data"])

    def levels_history(
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
    ) -> CursorResponse[list[LiquidationLevelsHistoryItem]]:
        """
        Get historical liquidation-levels snapshots with cursor pagination.

        Ascending by snapshot time (approximately every five minutes, retained from
        2026-07-27). Pass ``summary=True`` to list snapshots without
        histograms. Follow ``next_cursor`` as ``cursor`` for the next page.

        Args:
            symbol: The symbol (e.g., 'BTC', or 'xyz:TSLA' on HIP-3)
            start: Range start (default: 24h before end)
            end: Range end (default: now)
            cursor: Cursor from the previous page's next_cursor (exclusive)
            limit: Snapshots per page (1-100, default 24)
            summary: When True, items omit the levels array
            range_pct: Percentage range around each snapshot's mid
            buckets: Number of price buckets
            side: Side filter; the other side is zeroed
        """
        symbol = self._resolve_symbol(symbol, kwargs)
        data = self._http.get(
            f"{self._base_path}/liquidations/{self._coin_transform(symbol)}/levels/history",
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
            data=[LiquidationLevelsHistoryItem.model_validate(item) for item in data["data"]],
            next_cursor=data.get("meta", {}).get("next_cursor"),
        )

    async def alevels_history(
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
    ) -> CursorResponse[list[LiquidationLevelsHistoryItem]]:
        """Async version of levels_history()."""
        symbol = self._resolve_symbol(symbol, kwargs)
        data = await self._http.aget(
            f"{self._base_path}/liquidations/{self._coin_transform(symbol)}/levels/history",
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
            data=[LiquidationLevelsHistoryItem.model_validate(item) for item in data["data"]],
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
