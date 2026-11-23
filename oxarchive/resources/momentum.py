"""The momentum factor (Hyperliquid core perps). Build and above."""

from __future__ import annotations

from typing import Any, AsyncIterator, Awaitable, Callable, Iterator, Optional

from .._time import to_unix_ms
from ..http import HttpClient
from ..types import (
    CursorResponse,
    MomentumInterval,
    MomentumLookback,
    MomentumReturn,
    MomentumScore,
    MomentumUniverse,
    Timestamp,
)
from ._paging import Params, afollow, fixed_end, follow, page_of

MOMENTUM_LOOKBACKS = ("7d", "14d")
"""The lookbacks the API accepts on the momentum factor."""

MOMENTUM_UNIVERSES = ("top25", "top50")
"""The universes the momentum factor's returns are built on."""

MOMENTUM_INTERVALS = frozenset({"1h", "1d"})
"""Bucket widths the API accepts on the momentum factor's returns."""

MOMENTUM_MAX_LIMIT = 1000
"""Largest page size the API accepts on the momentum factor's returns."""


def _lookback(lookback: Any) -> str:
    if lookback not in MOMENTUM_LOOKBACKS:
        raise ValueError("lookback is required for the momentum factor: 7d or 14d")
    return str(lookback)


def _holdings(holdings: Optional[bool]) -> Optional[str]:
    if holdings is None:
        return None
    if not isinstance(holdings, bool):
        raise ValueError("holdings must be True or False for the momentum factor")
    return "true" if holdings else "false"


class MomentumResource:
    """Every Hyperliquid perp's momentum score at an hour, and the returns of
    the long-short momentum factor built from those scores (method
    ``momentum/1``).

    Served for Hyperliquid core perps at
    ``client.hyperliquid.factors.momentum``. Included with the Build, Pro,
    Scale and Enterprise plans; a Free key raises
    :class:`~oxarchive.PlanRequiredError`.

    ``lookback`` is required on every call: ``7d`` or ``14d``. A perp's score
    is its close-to-close return over the lookback divided by the standard
    deviation of its last 30 days of hourly returns.

    The factor: the universe is the top 25 (``top25``, the default) or top 50
    (``top50``) perps by 30-day dollar volume, re-picked every 30 days, with
    delisted perps included while they traded. Every 168 hours (Saturdays
    00:00 UTC, earning from 01:00) it goes long the top fifth of the universe
    on the score and short the bottom fifth, each leg weighted by inverse
    volatility and summing to 1. A bucket's ``ret`` is the sum of the
    factor's hourly returns over the hours it holds (simple, not compounded),
    gross of fees and funding.

    Coverage starts 2025-05-24 01:00 UTC for both scores and returns. A
    request that ends before it is empty, with ``meta.coverage_from`` and
    ``meta.notice``. ``is_final`` is ``True`` once every candle a record is
    made from is final. A 503 ``upstream_unavailable`` ("still being
    prepared") on the first request after a server restart is retryable.

    Example:
        >>> scores = client.hyperliquid.factors.momentum.current("7d")
        >>> strongest = scores.data[0]
        >>> page = client.hyperliquid.factors.momentum.returns(
        ...     "14d", universe="top50", start="2026-10-01", end="2026-11-01"
        ... )
    """

    def __init__(self, http: HttpClient, base_path: str = "/v1/hyperliquid") -> None:
        self._http = http
        self._scores_path = f"{base_path}/factors/momentum"
        self._current_path = f"{base_path}/factors/momentum/current"
        self._returns_path = f"{base_path}/factors/momentum/returns"

    @staticmethod
    def _scores_params(lookback: Any, at: Optional[Timestamp]) -> Params:
        return {"lookback": _lookback(lookback), "at": to_unix_ms(at, "at")}

    @staticmethod
    def _returns_params(
        lookback: Any,
        universe: Optional[MomentumUniverse],
        start: Optional[Timestamp],
        end: Optional[Timestamp],
        interval: Optional[MomentumInterval],
        holdings: Optional[bool],
        cursor: Optional[str],
        limit: Optional[int],
    ) -> Params:
        name = _lookback(lookback)
        if universe is not None and universe not in MOMENTUM_UNIVERSES:
            raise ValueError("universe must be top25 or top50 for the momentum factor")
        if interval is not None and interval not in MOMENTUM_INTERVALS:
            raise ValueError("interval must be 1h or 1d for the momentum factor")
        if limit is not None and (isinstance(limit, bool) or not 1 <= limit <= MOMENTUM_MAX_LIMIT):
            raise ValueError(
                f"limit must be between 1 and {MOMENTUM_MAX_LIMIT} for the momentum factor"
            )
        return {
            "lookback": name,
            "universe": universe,
            "start": to_unix_ms(start, "start"),
            "end": to_unix_ms(end, "end"),
            "interval": interval,
            "holdings": _holdings(holdings),
            "cursor": cursor,
            "limit": limit,
        }

    def _fetch(self) -> Callable[[Params], CursorResponse[list[MomentumReturn]]]:
        return lambda params: page_of(
            self._http.get(self._returns_path, params=params), MomentumReturn
        )

    def _afetch(self) -> Callable[[Params], Awaitable[CursorResponse[list[MomentumReturn]]]]:
        async def fetch(params: Params) -> CursorResponse[list[MomentumReturn]]:
            payload = await self._http.aget(self._returns_path, params=params)
            return page_of(payload, MomentumReturn)

        return fetch

    def get(
        self, lookback: MomentumLookback, *, at: Optional[Timestamp] = None
    ) -> CursorResponse[list[MomentumScore]]:
        """Get every eligible perp's reading as of the close of one hour,
        strongest first.

        Args:
            lookback: ``7d`` or ``14d``.
            at: The reading is as of the close of the hour at or before this
                time (default: now). A time later than the newest settled
                hour gets the newest reading. A time without a time zone is
                UTC.

        Returns:
            One reading per eligible perp. The response is never paged:
            ``next_cursor`` is ``None``. Before coverage it is empty, with
            ``meta.coverage_from`` and ``meta.notice``.

        Raises:
            PlanRequiredError: The key's plan does not include the momentum
                factor.
        """
        payload = self._http.get(self._scores_path, params=self._scores_params(lookback, at))
        return page_of(payload, MomentumScore)

    async def aget(
        self, lookback: MomentumLookback, *, at: Optional[Timestamp] = None
    ) -> CursorResponse[list[MomentumScore]]:
        """Async version of :meth:`get`."""
        params = self._scores_params(lookback, at)
        payload = await self._http.aget(self._scores_path, params=params)
        return page_of(payload, MomentumScore)

    def current(self, lookback: MomentumLookback) -> CursorResponse[list[MomentumScore]]:
        """Get the newest reading: every eligible perp, strongest first.

        Args:
            lookback: ``7d`` or ``14d``.

        Raises:
            PlanRequiredError: The key's plan does not include the momentum
                factor.
        """
        payload = self._http.get(self._current_path, params={"lookback": _lookback(lookback)})
        return page_of(payload, MomentumScore)

    async def acurrent(self, lookback: MomentumLookback) -> CursorResponse[list[MomentumScore]]:
        """Async version of :meth:`current`."""
        params = {"lookback": _lookback(lookback)}
        payload = await self._http.aget(self._current_path, params=params)
        return page_of(payload, MomentumScore)

    def returns(
        self,
        lookback: MomentumLookback,
        *,
        universe: Optional[MomentumUniverse] = None,
        start: Optional[Timestamp] = None,
        end: Optional[Timestamp] = None,
        interval: Optional[MomentumInterval] = None,
        holdings: Optional[bool] = None,
        cursor: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> CursorResponse[list[MomentumReturn]]:
        """Get one page of the factor's returns, oldest first.

        A page holds the buckets whose open is in ``[start, end]``. While
        ``next_cursor`` is set, pass it back as ``cursor`` with every other
        argument unchanged, and stop when it is ``None``, not on a short
        page. Set ``end`` when paging: without it each request ends at its
        own time.

        Args:
            lookback: ``7d`` or ``14d``.
            universe: ``top25`` (default) or ``top50``.
            start: Window start (default: 30 days before ``end``). A time
                without a time zone is UTC.
            end: Window end (default: now).
            interval: ``1d`` (default) or ``1h``, on UTC boundaries.
            holdings: ``True`` adds each bucket's ``holdings``: the weights
                of the rebalance in force at its last hour.
            cursor: The previous page's ``next_cursor``, passed back unchanged.
            limit: Buckets per page, 1 to 1000 (default 100).

        Raises:
            PlanRequiredError: The key's plan does not include the momentum
                factor.
        """
        params = self._returns_params(
            lookback, universe, start, end, interval, holdings, cursor, limit
        )
        return self._fetch()(params)

    async def areturns(
        self,
        lookback: MomentumLookback,
        *,
        universe: Optional[MomentumUniverse] = None,
        start: Optional[Timestamp] = None,
        end: Optional[Timestamp] = None,
        interval: Optional[MomentumInterval] = None,
        holdings: Optional[bool] = None,
        cursor: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> CursorResponse[list[MomentumReturn]]:
        """Async version of :meth:`returns`."""
        params = self._returns_params(
            lookback, universe, start, end, interval, holdings, cursor, limit
        )
        return await self._afetch()(params)

    def iterate_returns(
        self,
        lookback: MomentumLookback,
        *,
        start: Timestamp,
        end: Optional[Timestamp] = None,
        universe: Optional[MomentumUniverse] = None,
        interval: Optional[MomentumInterval] = None,
        holdings: Optional[bool] = None,
        limit: Optional[int] = None,
    ) -> Iterator[MomentumReturn]:
        """Yield every bucket in ``[start, end]``, following ``next_cursor``.

        It stops only when a page has no cursor, never on a short or empty
        page. When ``end`` is omitted it is fixed to the current time before
        the first request, and the same ``end`` is sent on every page.
        """
        params = self._returns_params(
            lookback, universe, start, fixed_end(end), interval, holdings, None, limit
        )
        return follow(self._fetch(), params)

    def aiterate_returns(
        self,
        lookback: MomentumLookback,
        *,
        start: Timestamp,
        end: Optional[Timestamp] = None,
        universe: Optional[MomentumUniverse] = None,
        interval: Optional[MomentumInterval] = None,
        holdings: Optional[bool] = None,
        limit: Optional[int] = None,
    ) -> AsyncIterator[MomentumReturn]:
        """Async version of :meth:`iterate_returns`."""
        params = self._returns_params(
            lookback, universe, start, fixed_end(end), interval, holdings, None, limit
        )
        return afollow(self._afetch(), params)


class FactorsResource:
    """Factors on Hyperliquid core perps (``client.hyperliquid.factors``).
    Build and above."""

    def __init__(self, http: HttpClient, base_path: str = "/v1/hyperliquid") -> None:
        self.momentum = MomentumResource(http, base_path)
        """The momentum factor: every perp's score at an hour, and the
        long-short factor's returns (from 2025-05-24 01:00 UTC)."""
