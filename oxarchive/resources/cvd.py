"""Cumulative volume delta API resource (Hyperliquid core and HIP-3)."""

from __future__ import annotations

from typing import Any, AsyncIterator, Callable, Iterator, Optional

from .._time import to_unix_ms
from ..http import HttpClient
from ..types import CursorResponse, CvdBucket, CvdInterval, ResponseMeta, Timestamp

CVD_INTERVALS = frozenset({"1m", "5m", "15m", "30m", "1h", "4h", "1d", "1w"})
"""Bucket widths the API accepts on cumulative volume delta."""

CVD_MAX_LIMIT = 10_000
"""Largest page size the API accepts on cumulative volume delta."""


def _page(payload: dict[str, Any]) -> CursorResponse[list[CvdBucket]]:
    meta = ResponseMeta.model_validate(payload.get("meta") or {})
    return CursorResponse(
        data=[CvdBucket.model_validate(item) for item in payload["data"]],
        next_cursor=meta.next_cursor,
        meta=meta,
    )


class CvdResource:
    """
    Cumulative volume delta: taker buy and sell notional per bucket.

    Buckets are labelled by their open time in UTC and omitted when they hold
    no trades. Intervals of ``1h`` and longer roll up hourly totals; ``1m``,
    ``5m``, ``15m`` and ``30m`` are summed from taker fills. ``4h``, ``1d`` and
    ``1w`` buckets open on UTC epoch boundaries (so ``1w`` buckets open on
    Thursdays), and at those widths the first and last bucket of a window can
    be partial.

    ``cumulative_delta`` restarts on every page. To join pages, rebuild the
    running total from ``delta``; a response that is one page of several says
    so in ``meta.notice``.

    Example:
        >>> page = client.hyperliquid.cvd.history(
        ...     "BTC", start="2026-09-01", end="2026-09-02", interval="1m"
        ... )
        >>> for bucket in client.hyperliquid.cvd.iterate(
        ...     "BTC", start="2026-09-01", end="2026-09-02", interval="1m"
        ... ):
        ...     print(bucket.timestamp, bucket.delta)
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

    @staticmethod
    def _params(
        start: Optional[Timestamp],
        end: Optional[Timestamp],
        interval: Optional[CvdInterval],
        cursor: Optional[str],
        limit: Optional[int],
    ) -> dict[str, Any]:
        if interval is not None and interval not in CVD_INTERVALS:
            choices = ", ".join(sorted(CVD_INTERVALS))
            raise ValueError(f"interval must be one of {choices} for cumulative volume delta")
        if limit is not None and not 1 <= limit <= CVD_MAX_LIMIT:
            raise ValueError(
                f"limit must be between 1 and {CVD_MAX_LIMIT} for cumulative volume delta"
            )
        return {
            "start": to_unix_ms(start, "start"),
            "end": to_unix_ms(end, "end"),
            "interval": interval,
            "cursor": cursor,
            "limit": limit,
        }

    def _path(self, symbol: str) -> str:
        return f"{self._base_path}/cvd/{self._coin_transform(symbol)}"

    def history(
        self,
        symbol: str,
        *,
        start: Optional[Timestamp] = None,
        end: Optional[Timestamp] = None,
        interval: Optional[CvdInterval] = None,
        cursor: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> CursorResponse[list[CvdBucket]]:
        """
        Get one page of cumulative volume delta buckets.

        While ``next_cursor`` is set, more buckets may follow inside
        ``[start, end]``: pass it back as ``cursor`` with ``start``, ``end``
        and ``interval`` unchanged, and stop when it is None. Below ``1h`` a
        page can hold fewer than ``limit`` buckets and still carry a cursor,
        so stop on the cursor, not on a short page. Without ``start`` or
        ``cursor``, the response is the newest ``limit`` buckets of the 24
        hours before ``end`` (or now), with no cursor.

        Args:
            symbol: Symbol (for example ``BTC``; HIP-3 symbols keep their
                builder prefix and case, for example ``km:US500``).
            start: Window start. A time without a time zone is UTC.
            end: Window end (default: now).
            interval: Bucket width: ``1m``, ``5m``, ``15m``, ``30m``, ``1h``
                (default), ``4h``, ``1d`` or ``1w``.
            cursor: The previous page's ``next_cursor``, passed back unchanged.
            limit: Buckets per page, 1 to 10000 (default 500).

        Returns:
            CursorResponse with the buckets, ``next_cursor`` and ``meta``.
        """
        payload = self._http.get(
            self._path(symbol), params=self._params(start, end, interval, cursor, limit)
        )
        return _page(payload)

    async def ahistory(
        self,
        symbol: str,
        *,
        start: Optional[Timestamp] = None,
        end: Optional[Timestamp] = None,
        interval: Optional[CvdInterval] = None,
        cursor: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> CursorResponse[list[CvdBucket]]:
        """Async version of :meth:`history`."""
        payload = await self._http.aget(
            self._path(symbol), params=self._params(start, end, interval, cursor, limit)
        )
        return _page(payload)

    def iterate(
        self,
        symbol: str,
        *,
        start: Timestamp,
        end: Optional[Timestamp] = None,
        interval: Optional[CvdInterval] = None,
        limit: Optional[int] = None,
    ) -> Iterator[CvdBucket]:
        """
        Yield every bucket in ``[start, end]``, following ``next_cursor``.

        Each page is requested with the same ``start``, ``end`` and
        ``interval``. ``cumulative_delta`` on the yielded buckets restarts at
        each page boundary; sum ``delta`` for a running total over the window.
        """
        params = self._params(start, end, interval, None, limit)
        path = self._path(symbol)
        while True:
            page = _page(self._http.get(path, params=params))
            yield from page.data
            if not page.next_cursor:
                return
            params = {**params, "cursor": page.next_cursor}

    async def aiterate(
        self,
        symbol: str,
        *,
        start: Timestamp,
        end: Optional[Timestamp] = None,
        interval: Optional[CvdInterval] = None,
        limit: Optional[int] = None,
    ) -> AsyncIterator[CvdBucket]:
        """Async version of :meth:`iterate`."""
        params = self._params(start, end, interval, None, limit)
        path = self._path(symbol)
        while True:
            page = _page(await self._http.aget(path, params=params))
            for bucket in page.data:
                yield bucket
            if not page.next_cursor:
                return
            params = {**params, "cursor": page.next_cursor}
