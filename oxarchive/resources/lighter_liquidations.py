"""Lighter liquidations API resource (Lighter mainnet and Robinhood Chain)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable, Optional

from ..http import HttpClient
from ..types import (
    CursorResponse,
    LighterLiquidation,
    LighterLiquidationVolume,
    ResponseMeta,
    Timestamp,
)


def _to_ms(ts: Optional[Timestamp]) -> Optional[int]:
    """Convert a timestamp (Unix ms, ISO string or datetime) to Unix milliseconds."""
    if ts is None:
        return None
    if isinstance(ts, int):
        return ts
    if isinstance(ts, datetime):
        return int(ts.timestamp() * 1000)
    try:
        return int(datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp() * 1000)
    except ValueError:
        return int(ts)


class LighterLiquidationsResource:
    """
    Liquidation events for a Lighter deployment.

    Available as ``client.lighter.liquidations`` (Lighter mainnet) and
    ``client.rh_lighter.liquidations`` (Lighter on Robinhood Chain). Lighter
    liquidations are the liquidation trades of the venue's trade stream, so a
    row keeps both sides' account fields; see :class:`LighterLiquidation`.

    Coverage: Robinhood Chain liquidations start 2026-08-22 18:43 UTC, later
    than its trades (2026-06-26 20:10:26 UTC); a request that starts earlier is
    refused with the API's coverage error. Any row backfilled from the venue's
    trade export has ``source == "bucket"`` and an empty ``raw_json``.

    Example:
        >>> page = client.lighter.liquidations.history("BTC", start="2026-09-01", end="2026-09-02")
        >>> for liq in page.data:
        ...     print(liq.timestamp, liq.price, liq.size, liq.usd_amount)
        >>>
        >>> volume = client.rh_lighter.liquidations.volume("BTC", interval="1d")
    """

    def __init__(
        self,
        http: HttpClient,
        base_path: str = "/v1/lighter",
        coin_transform: Callable[[str], str] = str.upper,
    ):
        self._http = http
        self._base_path = base_path
        self._coin_transform = coin_transform

    @staticmethod
    def _page(payload: dict[str, Any], model: Any) -> CursorResponse[Any]:
        meta = ResponseMeta.model_validate(payload.get("meta") or {})
        return CursorResponse(
            data=[model.model_validate(item) for item in payload["data"]],
            next_cursor=meta.next_cursor,
            meta=meta,
        )

    def _history_args(
        self,
        symbol: str,
        start: Timestamp,
        end: Timestamp,
        cursor: Optional[str],
        limit: Optional[int],
    ) -> tuple[str, dict[str, Any]]:
        return (
            f"{self._base_path}/liquidations/{self._coin_transform(symbol)}",
            {"start": _to_ms(start), "end": _to_ms(end), "cursor": cursor, "limit": limit},
        )

    def _volume_args(
        self,
        symbol: str,
        start: Optional[Timestamp],
        end: Optional[Timestamp],
        interval: Optional[str],
        cursor: Optional[str],
        limit: Optional[int],
    ) -> tuple[str, dict[str, Any]]:
        return (
            f"{self._base_path}/liquidations/{self._coin_transform(symbol)}/volume",
            {
                "start": _to_ms(start),
                "end": _to_ms(end),
                "interval": interval,
                "cursor": cursor,
                "limit": limit,
            },
        )

    def history(
        self,
        symbol: str,
        *,
        start: Timestamp,
        end: Timestamp,
        cursor: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> CursorResponse[list[LighterLiquidation]]:
        """
        Get liquidation events for a market with cursor-based pagination.

        Args:
            symbol: Market symbol (e.g. ``BTC``; case-insensitive)
            start: Start timestamp (required)
            end: End timestamp (required)
            cursor: ``next_cursor`` of the previous page (``"{timestamp_ms}_{trade_id}"``)
            limit: Maximum number of results (default: 100, max: 1000)

        Returns:
            CursorResponse with :class:`LighterLiquidation` rows and ``next_cursor``
        """
        path, params = self._history_args(symbol, start, end, cursor, limit)
        return self._page(self._http.get(path, params=params), LighterLiquidation)

    async def ahistory(
        self,
        symbol: str,
        *,
        start: Timestamp,
        end: Timestamp,
        cursor: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> CursorResponse[list[LighterLiquidation]]:
        """Async version of history(). start and end are required."""
        path, params = self._history_args(symbol, start, end, cursor, limit)
        return self._page(await self._http.aget(path, params=params), LighterLiquidation)

    def volume(
        self,
        symbol: str,
        *,
        start: Optional[Timestamp] = None,
        end: Optional[Timestamp] = None,
        interval: Optional[str] = None,
        cursor: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> CursorResponse[list[LighterLiquidationVolume]]:
        """
        Get aggregated liquidation volume for a market in time buckets.

        Each bucket carries ``total_usd`` and ``count`` (no long/short split).

        Args:
            symbol: Market symbol (e.g. ``BTC``; case-insensitive)
            start: Start timestamp (default: 24 hours before ``end``)
            end: End timestamp (default: now)
            interval: Bucket size: ``5m``, ``15m``, ``30m``, ``1h`` (default), ``4h`` or ``1d``
            cursor: ``next_cursor`` of the previous page
            limit: Maximum number of buckets (default: 100, max: 1000)

        Returns:
            CursorResponse with :class:`LighterLiquidationVolume` buckets and ``next_cursor``
        """
        path, params = self._volume_args(symbol, start, end, interval, cursor, limit)
        return self._page(self._http.get(path, params=params), LighterLiquidationVolume)

    async def avolume(
        self,
        symbol: str,
        *,
        start: Optional[Timestamp] = None,
        end: Optional[Timestamp] = None,
        interval: Optional[str] = None,
        cursor: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> CursorResponse[list[LighterLiquidationVolume]]:
        """Async version of volume()."""
        path, params = self._volume_args(symbol, start, end, interval, cursor, limit)
        return self._page(await self._http.aget(path, params=params), LighterLiquidationVolume)
