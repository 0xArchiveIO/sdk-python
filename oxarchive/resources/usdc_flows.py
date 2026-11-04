"""USDC flows API resource (Hyperliquid). Build and above."""

from __future__ import annotations

from typing import Any, AsyncIterator, Awaitable, Callable, Iterator, Optional, Union

from .._time import to_unix_ms
from ..http import HttpClient
from ..types import (
    CursorResponse,
    Timestamp,
    UsdcFlowEvent,
    UsdcFlowInterval,
    UsdcFlowKind,
    UsdcFlowVolumeBucket,
)
from ._paging import Params, afollow, fixed_end, follow, page_of

USDC_FLOW_KINDS = frozenset({"deposit", "withdraw", "evm_in", "evm_out"})
"""Values ``kind`` accepts on USDC flow events."""

USDC_FLOW_INTERVALS = frozenset({"1m", "5m", "15m", "30m", "1h", "4h", "1d"})
"""Bucket widths the API accepts on USDC flow volume."""

USDC_FLOWS_MAX_LIMIT = 1000
"""Largest page size the API accepts on both USDC flow routes."""

USDC_FLOWS_MAX_MIN_USD = 1e12
"""Largest ``min_usd`` the API accepts."""


def _limit(limit: Optional[int]) -> Optional[int]:
    if limit is not None and not 1 <= limit <= USDC_FLOWS_MAX_LIMIT:
        raise ValueError(f"limit must be between 1 and {USDC_FLOWS_MAX_LIMIT} for USDC flows")
    return limit


class UsdcFlowsResource:
    """USDC entering and leaving HyperCore, as events and as totals per bucket.

    ``deposit`` and ``withdraw`` are the Arbitrum bridge; ``evm_in`` and
    ``evm_out`` are USDC to and from HyperEVM (which also carries CCTP).
    Every event carries ``user``, the HyperCore account. Hyperliquid only:
    HIP-3 does not offer it. History starts 2025-09-27 09:33 UTC, the first
    flow; a window before then is empty with ``meta.coverage_from`` and
    ``meta.notice``.

    Included with the Build, Pro, Scale and Enterprise plans; a Free key
    raises :class:`~oxarchive.PlanRequiredError`.

    Events in the last 3 hours can still be added after you read them, when
    a gap in the live record is repaired: re-read that span and deduplicate
    on ``id``.

    Example:
        >>> page = client.hyperliquid.usdc_flows.history(
        ...     start="2026-11-02", end="2026-11-03", min_usd=1_000_000, kind="withdraw"
        ... )
        >>> totals = client.hyperliquid.usdc_flows.volume(
        ...     start="2026-11-02", end="2026-11-03", interval="1h"
        ... )
    """

    def __init__(self, http: HttpClient, base_path: str = "/v1/hyperliquid") -> None:
        self._http = http
        self._events_path = f"{base_path}/usdc-flows"
        self._volume_path = f"{base_path}/usdc-flows/volume"

    # ---- parameters ------------------------------------------------------

    @staticmethod
    def _events_params(
        start: Optional[Timestamp],
        end: Optional[Timestamp],
        cursor: Optional[str],
        limit: Optional[int],
        min_usd: Optional[Union[int, float]],
        kind: Optional[UsdcFlowKind],
    ) -> Params:
        if kind is not None and kind not in USDC_FLOW_KINDS:
            choices = ", ".join(sorted(USDC_FLOW_KINDS))
            raise ValueError(f"kind must be one of {choices} for USDC flows")
        if min_usd is not None and (
            isinstance(min_usd, bool) or not 0 <= min_usd <= USDC_FLOWS_MAX_MIN_USD
        ):
            raise ValueError("min_usd must be between 0 and 1e12 for USDC flows")
        return {
            "start": to_unix_ms(start, "start"),
            "end": to_unix_ms(end, "end"),
            "cursor": cursor,
            "limit": _limit(limit),
            "min_usd": min_usd,
            "kind": kind,
        }

    @staticmethod
    def _volume_params(
        start: Optional[Timestamp],
        end: Optional[Timestamp],
        interval: Optional[UsdcFlowInterval],
        cursor: Optional[str],
        limit: Optional[int],
    ) -> Params:
        if interval is not None and interval not in USDC_FLOW_INTERVALS:
            choices = ", ".join(sorted(USDC_FLOW_INTERVALS))
            raise ValueError(f"interval must be one of {choices} for USDC flow volume")
        return {
            "start": to_unix_ms(start, "start"),
            "end": to_unix_ms(end, "end"),
            "interval": interval,
            "cursor": cursor,
            "limit": _limit(limit),
        }

    # ---- transport -------------------------------------------------------

    def _fetch(self, path: str, model: Any) -> Callable[[Params], CursorResponse[list[Any]]]:
        return lambda params: page_of(self._http.get(path, params=params), model)

    def _afetch(
        self, path: str, model: Any
    ) -> Callable[[Params], Awaitable[CursorResponse[list[Any]]]]:
        async def fetch(params: Params) -> CursorResponse[list[Any]]:
            return page_of(await self._http.aget(path, params=params), model)

        return fetch

    # ---- events ----------------------------------------------------------

    def history(
        self,
        *,
        start: Optional[Timestamp] = None,
        end: Optional[Timestamp] = None,
        cursor: Optional[str] = None,
        limit: Optional[int] = None,
        min_usd: Optional[Union[int, float]] = None,
        kind: Optional[UsdcFlowKind] = None,
    ) -> CursorResponse[list[UsdcFlowEvent]]:
        """Get one page of USDC flow events, oldest first in execution order.

        While ``next_cursor`` is set, pass it back as ``cursor`` with the
        other arguments unchanged. A page reads at most 31 days, so with a
        sparse ``min_usd`` it can be empty and still have a cursor: stop on
        the cursor, not on a short or empty page. Join pages and deduplicate
        on ``id``.

        Args:
            start: Window start, inclusive (default: 24 hours before ``end``).
                A time without a time zone is UTC.
            end: Window end, inclusive (default: now).
            cursor: The previous page's ``next_cursor``, passed back unchanged.
            limit: Events per page, 1 to 1000 (default 100).
            min_usd: Only flows of at least this many USD (0 to 1e12).
            kind: Only one direction: ``deposit``, ``withdraw``, ``evm_in`` or
                ``evm_out``.

        Raises:
            PlanRequiredError: The key's plan does not include USDC flows.
        """
        params = self._events_params(start, end, cursor, limit, min_usd, kind)
        return self._fetch(self._events_path, UsdcFlowEvent)(params)

    async def ahistory(
        self,
        *,
        start: Optional[Timestamp] = None,
        end: Optional[Timestamp] = None,
        cursor: Optional[str] = None,
        limit: Optional[int] = None,
        min_usd: Optional[Union[int, float]] = None,
        kind: Optional[UsdcFlowKind] = None,
    ) -> CursorResponse[list[UsdcFlowEvent]]:
        """Async version of :meth:`history`."""
        params = self._events_params(start, end, cursor, limit, min_usd, kind)
        return await self._afetch(self._events_path, UsdcFlowEvent)(params)

    def iterate(
        self,
        *,
        start: Timestamp,
        end: Optional[Timestamp] = None,
        limit: Optional[int] = None,
        min_usd: Optional[Union[int, float]] = None,
        kind: Optional[UsdcFlowKind] = None,
    ) -> Iterator[UsdcFlowEvent]:
        """Yield every event in ``[start, end]``, following ``next_cursor``.

        It stops only when a page has no cursor, never on a short or empty
        page. When ``end`` is omitted it is fixed to the current time before
        the first request, and the same ``end`` is sent on every page.
        """
        params = self._events_params(start, fixed_end(end), None, limit, min_usd, kind)
        return follow(self._fetch(self._events_path, UsdcFlowEvent), params)

    def aiterate(
        self,
        *,
        start: Timestamp,
        end: Optional[Timestamp] = None,
        limit: Optional[int] = None,
        min_usd: Optional[Union[int, float]] = None,
        kind: Optional[UsdcFlowKind] = None,
    ) -> AsyncIterator[UsdcFlowEvent]:
        """Async version of :meth:`iterate`."""
        params = self._events_params(start, fixed_end(end), None, limit, min_usd, kind)
        return afollow(self._afetch(self._events_path, UsdcFlowEvent), params)

    # ---- volume ----------------------------------------------------------

    def volume(
        self,
        *,
        start: Optional[Timestamp] = None,
        end: Optional[Timestamp] = None,
        interval: Optional[UsdcFlowInterval] = None,
        cursor: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> CursorResponse[list[UsdcFlowVolumeBucket]]:
        """Get one page of USDC flow totals per bucket.

        One bucket per interval, zeros included, for the buckets whose open
        is in ``[start, end]``: never past the bucket still filling and never
        before the bucket of the first flow (a page holding that partial first
        bucket says so in ``meta.notice``). Totals count every flow, so this
        route takes no ``min_usd`` or ``kind``. While ``next_cursor`` is set,
        pass it back as ``cursor`` with the other arguments unchanged.

        Args:
            start: Window start (default: 24 hours before ``end``).
            end: Window end (default: now).
            interval: ``1m``, ``5m``, ``15m``, ``30m``, ``1h`` (default),
                ``4h`` or ``1d``, on UTC epoch boundaries.
            cursor: The previous page's ``next_cursor``, passed back unchanged.
            limit: Buckets per page, 1 to 1000 (default 100).

        Raises:
            PlanRequiredError: The key's plan does not include USDC flows.
        """
        params = self._volume_params(start, end, interval, cursor, limit)
        return self._fetch(self._volume_path, UsdcFlowVolumeBucket)(params)

    async def avolume(
        self,
        *,
        start: Optional[Timestamp] = None,
        end: Optional[Timestamp] = None,
        interval: Optional[UsdcFlowInterval] = None,
        cursor: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> CursorResponse[list[UsdcFlowVolumeBucket]]:
        """Async version of :meth:`volume`."""
        params = self._volume_params(start, end, interval, cursor, limit)
        return await self._afetch(self._volume_path, UsdcFlowVolumeBucket)(params)

    def iterate_volume(
        self,
        *,
        start: Timestamp,
        end: Optional[Timestamp] = None,
        interval: Optional[UsdcFlowInterval] = None,
        limit: Optional[int] = None,
    ) -> Iterator[UsdcFlowVolumeBucket]:
        """Yield every bucket in ``[start, end]``, following ``next_cursor``.

        When ``end`` is omitted it is fixed to the current time before the
        first request, and the same ``end`` is sent on every page.
        """
        params = self._volume_params(start, fixed_end(end), interval, None, limit)
        return follow(self._fetch(self._volume_path, UsdcFlowVolumeBucket), params)

    def aiterate_volume(
        self,
        *,
        start: Timestamp,
        end: Optional[Timestamp] = None,
        interval: Optional[UsdcFlowInterval] = None,
        limit: Optional[int] = None,
    ) -> AsyncIterator[UsdcFlowVolumeBucket]:
        """Async version of :meth:`iterate_volume`."""
        params = self._volume_params(start, fixed_end(end), interval, None, limit)
        return afollow(self._afetch(self._volume_path, UsdcFlowVolumeBucket), params)
