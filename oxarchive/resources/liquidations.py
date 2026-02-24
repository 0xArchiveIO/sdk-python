"""Liquidations API resource."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from ..http import HttpClient
from ..types import CursorResponse, Liquidation, LiquidationVolume, Timestamp


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
            try:
                dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                return int(dt.timestamp() * 1000)
            except ValueError:
                return int(ts)
        return None

    def history(
        self,
        coin: str,
        *,
        start: Timestamp,
        end: Timestamp,
        cursor: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> CursorResponse[list[Liquidation]]:
        """
        Get liquidation history for a coin with cursor-based pagination.

        Args:
            coin: The coin symbol (e.g., 'BTC', 'ETH')
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
        data = self._http.get(
            f"{self._base_path}/liquidations/{coin.upper()}",
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
        coin: str,
        *,
        start: Timestamp,
        end: Timestamp,
        cursor: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> CursorResponse[list[Liquidation]]:
        """Async version of history(). start and end are required."""
        data = await self._http.aget(
            f"{self._base_path}/liquidations/{coin.upper()}",
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
        coin: Optional[str] = None,
        cursor: Optional[str] = None,
        limit: Optional[int] = None,
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
            coin: Optional coin filter (e.g., 'BTC', 'ETH')
            cursor: Cursor from previous response's next_cursor
            limit: Maximum number of results (default: 100, max: 1000)

        Returns:
            CursorResponse with liquidation records and next_cursor for pagination
        """
        params = {
            "start": self._convert_timestamp(start),
            "end": self._convert_timestamp(end),
            "cursor": cursor,
            "limit": limit,
        }
        if coin:
            params["coin"] = coin.upper()

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
        coin: Optional[str] = None,
        cursor: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> CursorResponse[list[Liquidation]]:
        """Async version of by_user()."""
        params = {
            "start": self._convert_timestamp(start),
            "end": self._convert_timestamp(end),
            "cursor": cursor,
            "limit": limit,
        }
        if coin:
            params["coin"] = coin.upper()

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
        coin: str,
        *,
        start: Optional[Timestamp] = None,
        end: Optional[Timestamp] = None,
        interval: Optional[str] = None,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
    ) -> CursorResponse[list[LiquidationVolume]]:
        """
        Get pre-aggregated liquidation volume for a coin.

        Args:
            coin: The coin symbol (e.g., 'BTC', 'ETH')
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
        data = self._http.get(
            f"{self._base_path}/liquidations/{coin.upper()}/volume",
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
        coin: str,
        *,
        start: Optional[Timestamp] = None,
        end: Optional[Timestamp] = None,
        interval: Optional[str] = None,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
    ) -> CursorResponse[list[LiquidationVolume]]:
        """Async version of volume()."""
        data = await self._http.aget(
            f"{self._base_path}/liquidations/{coin.upper()}/volume",
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
