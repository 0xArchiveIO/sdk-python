"""Candles (OHLCV) API resource."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from ..http import HttpClient
from ..types import Candle, CandleInterval, CursorResponse, Timestamp


class CandlesResource:
    """
    Candles (OHLCV) API resource.

    Example:
        >>> # Get candle history
        >>> result = client.candles.history("BTC", start=start, end=end, interval="1h")
        >>> for candle in result.data:
        ...     print(f"{candle.timestamp}: O={candle.open} H={candle.high} L={candle.low} C={candle.close}")
        >>>
        >>> # Paginate through large datasets
        >>> all_candles = result.data
        >>> while result.next_cursor:
        ...     result = client.candles.history("BTC", start=start, end=end, cursor=result.next_cursor)
        ...     all_candles.extend(result.data)
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
        coin: str,
        *,
        start: Timestamp,
        end: Timestamp,
        interval: Optional[CandleInterval] = None,
        cursor: Optional[Timestamp] = None,
        limit: Optional[int] = None,
    ) -> CursorResponse[list[Candle]]:
        """
        Get historical OHLCV candle data with cursor-based pagination.

        Args:
            coin: The coin symbol (e.g., 'BTC', 'ETH')
            start: Start timestamp (required)
            end: End timestamp (required)
            interval: Candle interval (1m, 5m, 15m, 30m, 1h, 4h, 1d, 1w). Default: 1h
            cursor: Cursor from previous response's next_cursor
            limit: Maximum number of results (default: 100, max: 10000 for candles)

        Returns:
            CursorResponse with candle records and next_cursor for pagination

        Example:
            >>> result = client.candles.history("BTC", start=start, end=end, interval="1h", limit=10000)
            >>> candles = result.data
            >>> while result.next_cursor:
            ...     result = client.candles.history(
            ...         "BTC", start=start, end=end, interval="1h", cursor=result.next_cursor, limit=10000
            ...     )
            ...     candles.extend(result.data)
        """
        data = self._http.get(
            f"{self._base_path}/candles/{self._coin_transform(coin)}",
            params={
                "start": self._convert_timestamp(start),
                "end": self._convert_timestamp(end),
                "interval": interval,
                "cursor": self._convert_timestamp(cursor),
                "limit": limit,
            },
        )
        return CursorResponse(
            data=[Candle.model_validate(item) for item in data["data"]],
            next_cursor=data.get("meta", {}).get("next_cursor"),
        )

    async def ahistory(
        self,
        coin: str,
        *,
        start: Timestamp,
        end: Timestamp,
        interval: Optional[CandleInterval] = None,
        cursor: Optional[Timestamp] = None,
        limit: Optional[int] = None,
    ) -> CursorResponse[list[Candle]]:
        """Async version of history(). start and end are required."""
        data = await self._http.aget(
            f"{self._base_path}/candles/{self._coin_transform(coin)}",
            params={
                "start": self._convert_timestamp(start),
                "end": self._convert_timestamp(end),
                "interval": interval,
                "cursor": self._convert_timestamp(cursor),
                "limit": limit,
            },
        )
        return CursorResponse(
            data=[Candle.model_validate(item) for item in data["data"]],
            next_cursor=data.get("meta", {}).get("next_cursor"),
        )
