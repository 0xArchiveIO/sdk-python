"""HIP-4 outcome markets API resource."""

from __future__ import annotations

from typing import Any, List, Optional

from ..http import HttpClient
from ..types import CursorResponse, Hip4OutcomeAggregate, Hip4Question, ResponseMeta


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
    ) -> CursorResponse[List[Hip4OutcomeAggregate]]:
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


def _questions_page(payload: dict[str, Any]) -> CursorResponse[list[Hip4Question]]:
    meta = ResponseMeta.model_validate(payload.get("meta") or {})
    return CursorResponse(
        data=[Hip4Question.model_validate(item) for item in payload["data"]],
        next_cursor=meta.next_cursor,
        meta=meta,
    )


class Hip4QuestionsResource:
    """
    HIP-4 questions: multi-choice resolvers that group binary outcome markets.

    A question has one named outcome per choice plus a fallback outcome that
    resolves Yes when no named choice does. Look the outcomes up with
    ``client.hyperliquid.hip4.outcomes.get(outcome_id)``.

    Example:
        >>> page = client.hyperliquid.hip4.questions.list(limit=100)
        >>> question = client.hyperliquid.hip4.questions.get(0)
        >>> print(question.named_outcome_ids, question.fallback_outcome_id)
    """

    def __init__(self, http: HttpClient, base_path: str = "/v1/hyperliquid/hip4"):
        self._http = http
        self._base_path = base_path

    def list(
        self,
        *,
        cursor: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> CursorResponse[list[Hip4Question]]:
        """List questions in ascending question ID order.

        Args:
            cursor: The previous page's ``next_cursor`` (a question ID),
                passed back unchanged.
            limit: Page size (default 100, max 1000).

        Returns:
            CursorResponse with the questions and ``next_cursor``; ``None`` on
            the last page.
        """
        data = self._http.get(
            f"{self._base_path}/questions",
            params={"cursor": cursor, "limit": limit},
        )
        return _questions_page(data)

    async def alist(
        self,
        *,
        cursor: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> CursorResponse[List[Hip4Question]]:
        """Async version of list()."""
        data = await self._http.aget(
            f"{self._base_path}/questions",
            params={"cursor": cursor, "limit": limit},
        )
        return _questions_page(data)

    def get(self, question_id: int) -> Hip4Question:
        """Get a single question by its numeric ID."""
        data = self._http.get(f"{self._base_path}/questions/{int(question_id)}")
        return Hip4Question.model_validate(data["data"])

    async def aget(self, question_id: int) -> Hip4Question:
        """Async version of get()."""
        data = await self._http.aget(f"{self._base_path}/questions/{int(question_id)}")
        return Hip4Question.model_validate(data["data"])
