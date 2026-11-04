"""Trade intent API resource (Hyperliquid core and HIP-3). Build and above."""

from __future__ import annotations

from typing import AsyncIterator, Awaitable, Callable, Iterator, Optional
from urllib.parse import quote

from .._time import to_unix_ms
from ..http import HttpClient
from ..types import CursorResponse, Timestamp, TradeIntentBucket, TradeIntentInterval
from ._paging import Params, afollow, fixed_end, follow, page_of

TRADE_INTENT_INTERVALS = frozenset({"1s", "5s", "15s", "1m", "5m", "15m", "1h", "4h", "1d"})
"""Bucket widths the API accepts on trade intent."""

TRADE_INTENT_MAX_LIMIT = 2000
"""Largest page size the API accepts on trade intent."""


class TradeIntentResource:
    """Trade intent: why one market traded, bucket by bucket, in USD.

    Each bucket splits the market's volume by intent: new longs and shorts
    (``open_long``, ``open_short``), profit taken (``tp_long``,
    ``tp_short``), stopped out (``stop_long``, ``stop_short``: closes at a
    loss, liquidations and auto-deleveraging) and flips through zero
    (``flip_ls``, ``flip_sl``). Both sides of every trade count; market
    makers' legs are in ``mm_usd`` only. The market's trailing-72h winners and
    losers are given as aggregates (net and gross position, count and flow);
    no wallet is named.

    Included with the Build, Pro, Scale and Enterprise plans; a Free key
    raises :class:`~oxarchive.PlanRequiredError`.

    Coverage (UTC): hourly intervals (``1h``, ``4h``, ``1d``) from 2025-05-25
    15:00 on Hyperliquid and 2025-10-13 12:00 on HIP-3; minute intervals from
    2026-07-14 00:00; second intervals for the last 3 days. A window before
    coverage is empty with ``meta.coverage_from`` and ``meta.notice``.

    A market idle for more than 7 days has no buckets there: a gap, not zero.
    A second without a record had no trades, as far as ``meta.built_through``
    reaches; after it, nothing is known yet. Buckets of the hour still in
    progress are ``preliminary`` and are replaced as final data lands.

    Example:
        >>> page = client.hyperliquid.trade_intent.history(
        ...     "BTC", start="2026-11-02", end="2026-11-03", interval="1h"
        ... )
        >>> for bucket in client.hyperliquid.hip3.trade_intent.iterate(
        ...     "xyz:XYZ100", start="2026-11-02", end="2026-11-03", interval="1h"
        ... ):
        ...     print(bucket.timestamp, bucket.open_long, bucket.stop_long)
    """

    def __init__(
        self,
        http: HttpClient,
        base_path: str = "/v1/hyperliquid",
        coin_transform: Callable[[str], str] = str.upper,
    ) -> None:
        self._http = http
        self._base_path = base_path
        self._coin_transform = coin_transform

    def _path(self, symbol: str) -> str:
        if not symbol:
            raise ValueError("symbol is required for trade intent")
        return f"{self._base_path}/trade-intent/{quote(self._coin_transform(symbol), safe=':')}"

    @staticmethod
    def _params(
        start: Optional[Timestamp],
        end: Optional[Timestamp],
        interval: Optional[TradeIntentInterval],
        cursor: Optional[str],
        limit: Optional[int],
    ) -> Params:
        if interval is not None and interval not in TRADE_INTENT_INTERVALS:
            choices = ", ".join(sorted(TRADE_INTENT_INTERVALS))
            raise ValueError(f"interval must be one of {choices} for trade intent")
        if limit is not None and not 1 <= limit <= TRADE_INTENT_MAX_LIMIT:
            raise ValueError(
                f"limit must be between 1 and {TRADE_INTENT_MAX_LIMIT} for trade intent"
            )
        return {
            "start": to_unix_ms(start, "start"),
            "end": to_unix_ms(end, "end"),
            "interval": interval,
            "cursor": cursor,
            "limit": limit,
        }

    def _fetch(self, path: str) -> Callable[[Params], CursorResponse[list[TradeIntentBucket]]]:
        return lambda params: page_of(self._http.get(path, params=params), TradeIntentBucket)

    def _afetch(
        self, path: str
    ) -> Callable[[Params], Awaitable[CursorResponse[list[TradeIntentBucket]]]]:
        async def fetch(params: Params) -> CursorResponse[list[TradeIntentBucket]]:
            return page_of(await self._http.aget(path, params=params), TradeIntentBucket)

        return fetch

    def history(
        self,
        symbol: str,
        *,
        start: Optional[Timestamp] = None,
        end: Optional[Timestamp] = None,
        interval: Optional[TradeIntentInterval] = None,
        cursor: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> CursorResponse[list[TradeIntentBucket]]:
        """Get one page of trade intent buckets, oldest first.

        A page holds the buckets whose open is in ``[start, end]``, never past
        the bucket holding now; pages never split a bucket. While
        ``next_cursor`` is set, pass it back as ``cursor`` with ``start``,
        ``end`` and ``interval`` unchanged. A page can hold fewer than
        ``limit`` buckets, or none, and still have a cursor, so stop on the
        cursor, not on a short page. Set ``start`` and ``end`` when paging:
        without them each request takes the 24 hours before its own time.

        Args:
            symbol: The market, for example ``BTC`` (HIP-3 symbols keep their
                builder prefix and case, for example ``xyz:XYZ100``).
            start: Window start (default: 24 hours before ``end``). A time
                without a time zone is UTC.
            end: Window end (default: now).
            interval: ``1s``, ``5s``, ``15s``, ``1m``, ``5m``, ``15m``, ``1h``
                (default), ``4h`` or ``1d``, on UTC epoch boundaries.
            cursor: The previous page's ``next_cursor``, passed back unchanged.
            limit: Buckets per page, 1 to 2000 (default 500).

        Returns:
            The buckets, ``next_cursor`` and ``meta`` (``symbol``, ``venue``,
            ``built_through``, and ``preliminary_row_count`` when the page holds
            preliminary buckets).

        Raises:
            PlanRequiredError: The key's plan does not include trade intent.
        """
        return self._fetch(self._path(symbol))(self._params(start, end, interval, cursor, limit))

    async def ahistory(
        self,
        symbol: str,
        *,
        start: Optional[Timestamp] = None,
        end: Optional[Timestamp] = None,
        interval: Optional[TradeIntentInterval] = None,
        cursor: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> CursorResponse[list[TradeIntentBucket]]:
        """Async version of :meth:`history`."""
        fetch = self._afetch(self._path(symbol))
        return await fetch(self._params(start, end, interval, cursor, limit))

    def iterate(
        self,
        symbol: str,
        *,
        start: Timestamp,
        end: Optional[Timestamp] = None,
        interval: Optional[TradeIntentInterval] = None,
        limit: Optional[int] = None,
    ) -> Iterator[TradeIntentBucket]:
        """Yield every bucket in ``[start, end]``, following ``next_cursor``.

        It stops only when a page has no cursor, never on a short or empty
        page. When ``end`` is omitted it is fixed to the current time before
        the first request, and the same ``end`` is sent on every page.
        """
        path = self._path(symbol)
        params = self._params(start, fixed_end(end), interval, None, limit)
        return follow(self._fetch(path), params)

    def aiterate(
        self,
        symbol: str,
        *,
        start: Timestamp,
        end: Optional[Timestamp] = None,
        interval: Optional[TradeIntentInterval] = None,
        limit: Optional[int] = None,
    ) -> AsyncIterator[TradeIntentBucket]:
        """Async version of :meth:`iterate`."""
        path = self._path(symbol)
        params = self._params(start, fixed_end(end), interval, None, limit)
        return afollow(self._afetch(path), params)
