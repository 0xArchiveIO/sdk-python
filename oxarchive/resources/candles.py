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
        ...     print(
        ...         f"{candle.timestamp}: O={candle.open} H={candle.high} "
        ...         f"L={candle.low} C={candle.close}"
        ...     )
        >>>
        >>> # Paginate through large datasets
        >>> all_candles = result.data
        >>> while result.next_cursor:
        ...     result = client.candles.history(
        ...         "BTC", start=start, end=end, cursor=result.next_cursor
        ...     )
        ...     all_candles.extend(result.data)
    """

    def __init__(self, http: HttpClient, base_path: str = "/v1", coin_transform=str.upper):
        self._http = http
        self._base_path = base_path
        self._coin_transform = coin_transform
        self._max_limit = 10000
        self._limit_label = "candles"

    def _validate_limit(self, limit: Optional[int]) -> None:
        """Validate the route-specific candle page limit."""
        if limit is not None and not 1 <= limit <= self._max_limit:
            raise ValueError(
                f"limit must be between 1 and {self._max_limit} for {self._limit_label}"
            )

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
        interval: Optional[CandleInterval] = None,
        cursor: Optional[str] = None,
        limit: Optional[int] = None,
        **kwargs,
    ) -> CursorResponse[list[Candle]]:
        """
        Get historical OHLCV candle data with cursor-based pagination.

        Args:
            symbol: The symbol (e.g., 'BTC', 'ETH')
            start: Start timestamp (required)
            end: End timestamp (required)
            interval: Candle interval (1m, 5m, 15m, 30m, 1h, 4h, 1d, 1w). Default: 1h
            cursor: Opaque cursor string from the previous response's next_cursor
            limit: Maximum number of results (default: 100, max: 10000 for
                Hyperliquid core and Lighter candles; HIP-4 and Spot have a max
                of 1000)

        Returns:
            CursorResponse with candle records and next_cursor for pagination

        Example:
            >>> result = client.candles.history(
            ...     "BTC", start=start, end=end, interval="1h", limit=10000
            ... )
            >>> candles = result.data
            >>> while result.next_cursor:
            ...     result = client.candles.history(
            ...         "BTC", start=start, end=end, interval="1h",
            ...         cursor=result.next_cursor, limit=10000
            ...     )
            ...     candles.extend(result.data)
        """
        symbol = self._resolve_symbol(symbol, kwargs)
        self._validate_limit(limit)
        data = self._http.get(
            f"{self._base_path}/candles/{self._coin_transform(symbol)}",
            params={
                "start": self._convert_timestamp(start),
                "end": self._convert_timestamp(end),
                "interval": interval,
                "cursor": cursor,
                "limit": limit,
            },
        )
        return CursorResponse(
            data=[Candle.model_validate(item) for item in data["data"]],
            next_cursor=data.get("meta", {}).get("next_cursor"),
        )

    async def ahistory(
        self,
        symbol: str,
        *,
        start: Timestamp,
        end: Timestamp,
        interval: Optional[CandleInterval] = None,
        cursor: Optional[str] = None,
        limit: Optional[int] = None,
        **kwargs,
    ) -> CursorResponse[list[Candle]]:
        """Async version of history(). start and end are required."""
        symbol = self._resolve_symbol(symbol, kwargs)
        self._validate_limit(limit)
        data = await self._http.aget(
            f"{self._base_path}/candles/{self._coin_transform(symbol)}",
            params={
                "start": self._convert_timestamp(start),
                "end": self._convert_timestamp(end),
                "interval": interval,
                "cursor": cursor,
                "limit": limit,
            },
        )
        return CursorResponse(
            data=[Candle.model_validate(item) for item in data["data"]],
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


class Hip4CandlesResource(CandlesResource):
    """HIP-4 implied-probability candles with a 1,000-row page cap."""

    def __init__(
        self,
        http: HttpClient,
        base_path: str = "/v1/hyperliquid/hip4",
        coin_transform=str.upper,
    ):
        super().__init__(http, base_path, coin_transform)
        self._max_limit = 1000
        self._limit_label = "HIP-4 candles"


class SpotCandlesResource(CandlesResource):
    """Hyperliquid Spot OHLCV candles with a 1,000-row page cap.

    Spot candle coverage starts at ``2025-03-22T10:50:22Z``. Supported intervals
    are ``1m``, ``5m``, ``15m``, ``30m``, ``1h``, ``4h``, ``1d``, and ``1w``.
    """

    def __init__(
        self,
        http: HttpClient,
        base_path: str = "/v1/hyperliquid/spot",
        coin_transform=str.upper,
    ) -> None:
        super().__init__(http, base_path, coin_transform)
        self._max_limit = 1000
        self._limit_label = "Hyperliquid Spot candles"
