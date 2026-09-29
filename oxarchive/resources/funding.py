"""Funding rates API resource."""

from __future__ import annotations

from typing import Optional

from .._time import to_unix_ms
from ..http import HttpClient
from ..types import CursorResponse, FundingRate, ResponseMeta, Timestamp, _record


class FundingResource:
    """
    Funding rates API resource.

    Example:
        >>> # Get current funding rate
        >>> current = client.funding.current("BTC")
        >>>
        >>> # Get funding rate history
        >>> history = client.funding.history("ETH", start="2024-01-01", end="2024-01-07")
    """

    def __init__(self, http: HttpClient, base_path: str = "/v1", coin_transform=str.upper):
        self._http = http
        self._base_path = base_path
        self._coin_transform = coin_transform

    _convert_timestamp = staticmethod(to_unix_ms)

    def history(
        self,
        symbol: str,
        *,
        start: Timestamp,
        end: Timestamp,
        cursor: Optional[Timestamp] = None,
        limit: Optional[int] = None,
        interval: Optional[str] = None,
        **kwargs,
    ) -> CursorResponse[list[FundingRate]]:
        """
        Get funding rate history for a symbol with cursor-based pagination.

        Args:
            symbol: The symbol (e.g., 'BTC', 'ETH')
            start: Start timestamp (required)
            end: End timestamp (required)
            cursor: Cursor from previous response's next_cursor (timestamp)
            limit: Maximum number of results (default: 100, max: 1000)
            interval: Aggregation interval (e.g., '1m', '5m', '15m', '30m', '1h', '4h', '1d').
                Raw cadence is route-specific: Hyperliquid core is roughly one
                minute; HIP-3 and Lighter are roughly 10 seconds. HIP-4 has no funding.

        Returns:
            CursorResponse with funding rate records and next_cursor for pagination

        Example:
            >>> result = client.funding.history("BTC", start=start, end=end, limit=1000)
            >>> rates = result.data
            >>> while result.has_more:
            ...     result = client.funding.history(
            ...         "BTC", start=start, end=end, cursor=result.next_cursor, limit=1000
            ...     )
            ...     rates.extend(result.data)
        """
        symbol = self._resolve_symbol(symbol, kwargs)
        params = {
            "start": self._convert_timestamp(start),
            "end": self._convert_timestamp(end),
            "cursor": self._convert_timestamp(cursor),
            "limit": limit,
        }
        if interval:
            params["interval"] = interval
        data = self._http.get(
            f"{self._base_path}/funding/{self._coin_transform(symbol)}",
            params=params,
        )
        return CursorResponse(
            data=[FundingRate.model_validate(item) for item in data["data"]],
            next_cursor=data.get("meta", {}).get("next_cursor"),
            meta=ResponseMeta.of(data),
        )

    async def ahistory(
        self,
        symbol: str,
        *,
        start: Timestamp,
        end: Timestamp,
        cursor: Optional[Timestamp] = None,
        limit: Optional[int] = None,
        interval: Optional[str] = None,
        **kwargs,
    ) -> CursorResponse[list[FundingRate]]:
        """Async version of history(). start and end are required."""
        symbol = self._resolve_symbol(symbol, kwargs)
        params = {
            "start": self._convert_timestamp(start),
            "end": self._convert_timestamp(end),
            "cursor": self._convert_timestamp(cursor),
            "limit": limit,
        }
        if interval:
            params["interval"] = interval
        data = await self._http.aget(
            f"{self._base_path}/funding/{self._coin_transform(symbol)}",
            params=params,
        )
        return CursorResponse(
            data=[FundingRate.model_validate(item) for item in data["data"]],
            next_cursor=data.get("meta", {}).get("next_cursor"),
            meta=ResponseMeta.of(data),
        )

    def current(self, symbol: str, **kwargs) -> FundingRate:
        """
        Get current funding rate for a symbol.

        Args:
            symbol: The symbol (e.g., 'BTC', 'ETH')

        Returns:
            Current funding rate
        """
        symbol = self._resolve_symbol(symbol, kwargs)
        data = self._http.get(f"{self._base_path}/funding/{self._coin_transform(symbol)}/current")
        return _record(FundingRate, data)

    async def acurrent(self, symbol: str, **kwargs) -> FundingRate:
        """Async version of current()."""
        symbol = self._resolve_symbol(symbol, kwargs)
        data = await self._http.aget(
            f"{self._base_path}/funding/{self._coin_transform(symbol)}/current"
        )
        return _record(FundingRate, data)

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
