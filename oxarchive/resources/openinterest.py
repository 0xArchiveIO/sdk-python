"""Open interest API resource."""

from __future__ import annotations

from datetime import datetime
from typing import Generic, Optional, TypeVar

from pydantic import BaseModel

from ..http import HttpClient
from ..types import CursorResponse, Hip4OpenInterestRecord, OpenInterest, Timestamp

RecordT = TypeVar("RecordT", bound=BaseModel)


class _OpenInterestResourceBase(Generic[RecordT]):
    """
    Open interest API resource.

    Example:
        >>> # Get current open interest
        >>> current = client.open_interest.current("BTC")
        >>>
        >>> # Get open interest history
        >>> history = client.open_interest.history("ETH", start="2024-01-01", end="2024-01-07")
    """

    def __init__(
        self,
        http: HttpClient,
        base_path: str,
        record_model: type[RecordT],
        coin_transform=str.upper,
    ):
        self._http = http
        self._base_path = base_path
        self._coin_transform = coin_transform
        self._record_model = record_model

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
        interval: Optional[str] = None,
        **kwargs,
    ) -> CursorResponse[list[RecordT]]:
        """
        Get open interest history for a symbol with cursor-based pagination.

        Args:
            symbol: The symbol (e.g., 'BTC', 'ETH')
            start: Start timestamp (required)
            end: End timestamp (required)
            cursor: Numeric timestamp string returned as the previous response's
                next_cursor; pass it back unchanged
            limit: Maximum number of results (default: 100, max: 1000)
            interval: Aggregation interval (e.g., '5m', '15m', '30m', '1h', '4h', '1d').
                Raw cadence is route-specific. HIP-3, HIP-4 outcome-side OI,
                and Lighter are roughly 10 seconds.

        Returns:
            CursorResponse with open interest records and next_cursor for pagination

        Example:
            >>> result = client.open_interest.history("BTC", start=start, end=end, limit=1000)
            >>> records = result.data
            >>> while result.next_cursor:
            ...     result = client.open_interest.history(
            ...         "BTC", start=start, end=end, cursor=result.next_cursor, limit=1000
            ...     )
            ...     records.extend(result.data)
        """
        symbol = self._resolve_symbol(symbol, kwargs)
        params = {
            "start": self._convert_timestamp(start),
            "end": self._convert_timestamp(end),
            "cursor": cursor,
            "limit": limit,
        }
        if interval:
            params["interval"] = interval
        data = self._http.get(
            f"{self._base_path}/openinterest/{self._coin_transform(symbol)}",
            params=params,
        )
        return CursorResponse(
            data=[self._record_model.model_validate(item) for item in data["data"]],
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
        interval: Optional[str] = None,
        **kwargs,
    ) -> CursorResponse[list[RecordT]]:
        """Async version of history(). start and end are required."""
        symbol = self._resolve_symbol(symbol, kwargs)
        params = {
            "start": self._convert_timestamp(start),
            "end": self._convert_timestamp(end),
            "cursor": cursor,
            "limit": limit,
        }
        if interval:
            params["interval"] = interval
        data = await self._http.aget(
            f"{self._base_path}/openinterest/{self._coin_transform(symbol)}",
            params=params,
        )
        return CursorResponse(
            data=[self._record_model.model_validate(item) for item in data["data"]],
            next_cursor=data.get("meta", {}).get("next_cursor"),
        )

    def current(self, symbol: str, **kwargs) -> RecordT:
        """
        Get current open interest for a symbol.

        Args:
            symbol: The symbol (e.g., 'BTC', 'ETH')

        Returns:
            Current open interest
        """
        symbol = self._resolve_symbol(symbol, kwargs)
        data = self._http.get(
            f"{self._base_path}/openinterest/{self._coin_transform(symbol)}/current"
        )
        return self._record_model.model_validate(data["data"])

    async def acurrent(self, symbol: str, **kwargs) -> RecordT:
        """Async version of current()."""
        symbol = self._resolve_symbol(symbol, kwargs)
        data = await self._http.aget(
            f"{self._base_path}/openinterest/{self._coin_transform(symbol)}/current"
        )
        return self._record_model.model_validate(data["data"])

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


class OpenInterestResource(_OpenInterestResourceBase[OpenInterest]):
    """Generic open-interest resource for perpetual venues."""

    def __init__(self, http: HttpClient, base_path: str = "/v1", coin_transform=str.upper):
        super().__init__(http, base_path, OpenInterest, coin_transform)


class Hip4OpenInterestResource(_OpenInterestResourceBase[Hip4OpenInterestRecord]):
    """HIP-4 per-side open-interest resource.

    HIP-4 OI records include the per-side ``symbol``, ``outcome_id``, and
    ``side`` fields. They use a family-specific model so generic perpetual OI
    validation cannot silently discard those fields.
    """

    def __init__(
        self,
        http: HttpClient,
        base_path: str = "/v1/hyperliquid/hip4",
        coin_transform=str.upper,
    ):
        super().__init__(http, base_path, Hip4OpenInterestRecord, coin_transform)
