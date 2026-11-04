"""Breadth above the n-day moving average (Hyperliquid core and HIP-3). Build and above."""

from __future__ import annotations

from typing import Any, AsyncIterator, Awaitable, Callable, Iterator, Optional

from .._time import to_unix_ms
from ..http import HttpClient
from ..types import (
    BreadthMaInterval,
    BreadthMaLength,
    BreadthMaReading,
    CursorResponse,
    Timestamp,
    _record,
)
from ._paging import Params, afollow, fixed_end, follow, page_of

BREADTH_MA_LENGTHS = (5, 20, 50, 200)
"""The moving-average lengths the API accepts, in days."""

BREADTH_MA_INTERVALS = frozenset({"1m", "5m", "15m", "30m", "1h", "4h", "1d"})
"""Bucket widths the API accepts on moving-average breadth."""

BREADTH_MA_MAX_LIMIT = 1000
"""Largest page size the API accepts on moving-average breadth."""


def _n(n: Any) -> int:
    if isinstance(n, bool) or n not in BREADTH_MA_LENGTHS:
        raise ValueError("n is required for moving-average breadth: 5, 20, 50 or 200")
    return int(n)


class BreadthMaResource:
    """The share of perps above their n-day moving average, and how far above
    or below (quartiles).

    Served for Hyperliquid core (``client.hyperliquid.breadth_ma``) and HIP-3
    (``client.hyperliquid.hip3.breadth_ma``). Included with the Build, Pro,
    Scale and Enterprise plans; a Free key raises
    :class:`~oxarchive.PlanRequiredError`.

    ``n`` is required (5, 20, 50 or 200) and each length starts on its own
    date (UTC): on Hyperliquid n = 5 from 2025-03-27, 20 from 2025-04-11, 50
    from 2025-05-11 and 200 from 2025-10-08; on HIP-3 n = 5 from 2025-12-27,
    20 from 2026-01-11, 50 from 2026-02-10 and 200 from 2026-07-10. A window
    before its length's start is empty with ``meta.coverage_from`` and
    ``meta.notice``.

    Method (``ma-breadth/1``): candidates are every perp the venue ever
    listed, from its first 1-minute bar. A delisted perp stays a candidate,
    counted in ``excluded_stale_price`` from 24 hours after its last trade,
    and a perp younger than n days counts in ``excluded_short_history``, so
    ``coverage_ratio`` depends on n, is not a data-quality ratio and is not
    comparable with above-VWAP breadth's. A market's price is its last
    1-minute close before the reading; its average is the mean of its daily
    closes over the n UTC days before the reading's day. ``distance`` holds
    the quartiles of price / average - 1 over the eligible markets.
    ``value_pct`` and ``distance`` are ``None`` when nothing is eligible.

    A bucket carries its last reading, as of its end (``calculated_at``); the
    bucket still forming is as of about 4 minutes before now, on the minute.
    Never average percentages across buckets. The cursor is opaque and is not
    the above-VWAP breadth cursor. A 503 ``upstream_unavailable`` right after
    a server restart is retryable.

    Example:
        >>> latest = client.hyperliquid.breadth_ma.current(200)
        >>> page = client.hyperliquid.hip3.breadth_ma.history(
        ...     50, start="2026-11-01", end="2026-11-02", interval="1h"
        ... )
    """

    def __init__(self, http: HttpClient, base_path: str = "/v1/hyperliquid") -> None:
        self._http = http
        self._history_path = f"{base_path}/breadth/above-ma"
        self._current_path = f"{base_path}/breadth/above-ma/current"

    @staticmethod
    def _params(
        n: Any,
        start: Optional[Timestamp],
        end: Optional[Timestamp],
        interval: Optional[BreadthMaInterval],
        cursor: Optional[str],
        limit: Optional[int],
    ) -> Params:
        length = _n(n)
        if interval is not None and interval not in BREADTH_MA_INTERVALS:
            choices = ", ".join(sorted(BREADTH_MA_INTERVALS))
            raise ValueError(f"interval must be one of {choices} for moving-average breadth")
        if limit is not None and not 1 <= limit <= BREADTH_MA_MAX_LIMIT:
            raise ValueError(
                f"limit must be between 1 and {BREADTH_MA_MAX_LIMIT} for moving-average breadth"
            )
        return {
            "n": length,
            "start": to_unix_ms(start, "start"),
            "end": to_unix_ms(end, "end"),
            "interval": interval,
            "cursor": cursor,
            "limit": limit,
        }

    def _fetch(self) -> Callable[[Params], CursorResponse[list[BreadthMaReading]]]:
        return lambda params: page_of(
            self._http.get(self._history_path, params=params), BreadthMaReading
        )

    def _afetch(self) -> Callable[[Params], Awaitable[CursorResponse[list[BreadthMaReading]]]]:
        async def fetch(params: Params) -> CursorResponse[list[BreadthMaReading]]:
            payload = await self._http.aget(self._history_path, params=params)
            return page_of(payload, BreadthMaReading)

        return fetch

    def current(self, n: BreadthMaLength) -> BreadthMaReading:
        """Get the newest 1-minute reading of length ``n``.

        Args:
            n: The moving average's length in days: 5, 20, 50 or 200.

        Raises:
            PlanRequiredError: The key's plan does not include moving-average
                breadth.
        """
        payload = self._http.get(self._current_path, params={"n": _n(n)})
        return _record(BreadthMaReading, payload)

    async def acurrent(self, n: BreadthMaLength) -> BreadthMaReading:
        """Async version of :meth:`current`."""
        payload = await self._http.aget(self._current_path, params={"n": _n(n)})
        return _record(BreadthMaReading, payload)

    def history(
        self,
        n: BreadthMaLength,
        *,
        start: Optional[Timestamp] = None,
        end: Optional[Timestamp] = None,
        interval: Optional[BreadthMaInterval] = None,
        cursor: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> CursorResponse[list[BreadthMaReading]]:
        """Get one page of readings of length ``n``, oldest first.

        A page holds the buckets whose open is in ``[start, end]``. While
        ``next_cursor`` is set, pass it back as ``cursor`` with ``n``,
        ``start``, ``end`` and ``interval`` unchanged, and stop when it is
        ``None``, not on a short page. Set ``start`` and ``end`` when paging:
        without them each request takes the 24 hours before its own time.

        Args:
            n: The moving average's length in days: 5, 20, 50 or 200.
            start: Window start (default: 24 hours before ``end``). A time
                without a time zone is UTC.
            end: Window end (default: now).
            interval: ``1m`` (default), ``5m``, ``15m``, ``30m``, ``1h``,
                ``4h`` or ``1d``, on UTC epoch boundaries.
            cursor: The previous page's ``next_cursor``, passed back unchanged.
            limit: Buckets per page, 1 to 1000 (default 100).

        Raises:
            PlanRequiredError: The key's plan does not include moving-average
                breadth.
        """
        return self._fetch()(self._params(n, start, end, interval, cursor, limit))

    async def ahistory(
        self,
        n: BreadthMaLength,
        *,
        start: Optional[Timestamp] = None,
        end: Optional[Timestamp] = None,
        interval: Optional[BreadthMaInterval] = None,
        cursor: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> CursorResponse[list[BreadthMaReading]]:
        """Async version of :meth:`history`."""
        return await self._afetch()(self._params(n, start, end, interval, cursor, limit))

    def iterate(
        self,
        n: BreadthMaLength,
        *,
        start: Timestamp,
        end: Optional[Timestamp] = None,
        interval: Optional[BreadthMaInterval] = None,
        limit: Optional[int] = None,
    ) -> Iterator[BreadthMaReading]:
        """Yield every reading in ``[start, end]``, following ``next_cursor``.

        It stops only when a page has no cursor, never on a short or empty
        page. When ``end`` is omitted it is fixed to the current time before
        the first request, and the same ``end`` is sent on every page.
        """
        params = self._params(n, start, fixed_end(end), interval, None, limit)
        return follow(self._fetch(), params)

    def aiterate(
        self,
        n: BreadthMaLength,
        *,
        start: Timestamp,
        end: Optional[Timestamp] = None,
        interval: Optional[BreadthMaInterval] = None,
        limit: Optional[int] = None,
    ) -> AsyncIterator[BreadthMaReading]:
        """Async version of :meth:`iterate`."""
        params = self._params(n, start, fixed_end(end), interval, None, limit)
        return afollow(self._afetch(), params)
