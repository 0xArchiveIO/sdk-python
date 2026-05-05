"""HIP-4 outcome markets API resource."""

from __future__ import annotations

from typing import Optional

from ..http import HttpClient
from ..types import CursorResponse, Hip4OutcomeAggregate


class Hip4OutcomesResource:
    """
    HIP-4 outcomes resource (per-outcome aggregated metadata).

    The list endpoint omits ``aggregated_oi``; the detail endpoint includes it.

    Example:
        >>> outcomes = client.hyperliquid.hip4.outcomes.list()
        >>> outcome = client.hyperliquid.hip4.outcomes.get(0)
        >>> print(outcome.aggregated_oi.outcome_display_open_interest_contracts)
    """

    def __init__(self, http: HttpClient, base_path: str = "/v1/hyperliquid/hip4"):
        self._http = http
        self._base_path = base_path

    def list(
        self,
        *,
        is_settled: Optional[bool] = None,
        slug: Optional[str] = None,
        cursor: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> CursorResponse[list[Hip4OutcomeAggregate]]:
        """List outcome markets with optional filters.

        Args:
            is_settled: Filter by settlement state. None returns all.
            slug: Filter by per-outcome OR per-side slug. When matched, the
                response is a list of one (compose with ``is_settled``).
            cursor: Pagination cursor from a prior response's ``next_cursor``.
            limit: Page size.
        """
        data = self._http.get(
            f"{self._base_path}/outcomes",
            params={
                "is_settled": is_settled,
                "slug": slug,
                "cursor": cursor,
                "limit": limit,
            },
        )
        return CursorResponse(
            data=[Hip4OutcomeAggregate.model_validate(item) for item in data["data"]],
            next_cursor=data.get("meta", {}).get("next_cursor"),
        )

    async def alist(
        self,
        *,
        is_settled: Optional[bool] = None,
        slug: Optional[str] = None,
        cursor: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> CursorResponse[list[Hip4OutcomeAggregate]]:
        """Async version of list()."""
        data = await self._http.aget(
            f"{self._base_path}/outcomes",
            params={
                "is_settled": is_settled,
                "slug": slug,
                "cursor": cursor,
                "limit": limit,
            },
        )
        return CursorResponse(
            data=[Hip4OutcomeAggregate.model_validate(item) for item in data["data"]],
            next_cursor=data.get("meta", {}).get("next_cursor"),
        )

    def get(self, outcome_id: int) -> Hip4OutcomeAggregate:
        """Get a single outcome market by id. Includes ``aggregated_oi``."""
        data = self._http.get(f"{self._base_path}/outcomes/{int(outcome_id)}")
        return Hip4OutcomeAggregate.model_validate(data["data"])

    async def aget(self, outcome_id: int) -> Hip4OutcomeAggregate:
        """Async version of get()."""
        data = await self._http.aget(f"{self._base_path}/outcomes/{int(outcome_id)}")
        return Hip4OutcomeAggregate.model_validate(data["data"])

    def get_by_slug(self, slug: str) -> Hip4OutcomeAggregate:
        """Look up an outcome by its synthesized slug.

        Accepts the per-outcome slug (``btc-above-78213-may-04-0600``) or a
        per-side slug (``btc-above-78213-yes-may-04-0600``). Returns
        :class:`Hip4OutcomeAggregate` with ``aggregated_oi`` populated, like
        :py:meth:`get`.
        """
        data = self._http.get(f"{self._base_path}/outcomes/by-slug/{slug}")
        return Hip4OutcomeAggregate.model_validate(data["data"])

    async def aget_by_slug(self, slug: str) -> Hip4OutcomeAggregate:
        """Async version of get_by_slug()."""
        data = await self._http.aget(f"{self._base_path}/outcomes/by-slug/{slug}")
        return Hip4OutcomeAggregate.model_validate(data["data"])
