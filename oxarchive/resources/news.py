"""News API resource (Hyperliquid, HIP-3 and Lighter). Build and above."""

from __future__ import annotations

from typing import (
    Any,
    AsyncIterator,
    Awaitable,
    Callable,
    Iterator,
    List,
    Optional,
    Sequence,
    Union,
)

from .._time import to_unix_ms
from ..http import HttpClient
from ..types import CursorResponse, NewsStory, Timestamp
from ._paging import Params, afollow, fixed_end, follow, page_of

NEWS_MAX_LIMIT = 500
"""Largest page size the API accepts on the news routes."""

NEWS_MAX_SYMBOLS = 20
"""Most markets ``symbols`` takes."""


def _limit(limit: Optional[int]) -> Optional[int]:
    if limit is not None and (isinstance(limit, bool) or not 1 <= limit <= NEWS_MAX_LIMIT):
        raise ValueError(f"limit must be between 1 and {NEWS_MAX_LIMIT} for news")
    return limit


def _min_weight(min_weight: Optional[int]) -> Optional[int]:
    if min_weight is not None and (isinstance(min_weight, bool) or min_weight not in (1, 2, 3)):
        raise ValueError("min_weight must be 1, 2 or 3 for news")
    return min_weight


def _symbols(symbols: Union[str, Sequence[str], None]) -> Optional[str]:
    if symbols is None:
        return None
    items = [symbols] if isinstance(symbols, str) else list(symbols)
    items = [s.strip() for part in items for s in part.split(",") if s.strip()]
    if len(items) > NEWS_MAX_SYMBOLS:
        raise ValueError(f"symbols takes at most {NEWS_MAX_SYMBOLS} markets for news")
    return ",".join(items) or None


class NewsResource:
    """Headlines and our own market events as stories, with what the first
    market named did in the minutes after.

    Each story carries the reports that joined it (``reports``), the markets
    it names (``markets``) and, when a market was matched, ``reaction``: the 1
    and 5 minute windows after we first saw it, with ``move_pct``, ``move_z``
    and ``move_level``, liquidations, open interest and depth. A reaction is a
    measurement, not a cause. Story moves are mostly noise: treat a move as
    typical unless ``move_level`` is ``unusual`` or ``large``.

    One resource per venue: ``client.hyperliquid.news`` (perps),
    ``client.hyperliquid.hip3.news`` and ``client.lighter.news`` return the
    stories whose lead report names a market on that venue. Public-display
    stories only: sources the API is not licensed to redistribute do not
    appear.

    Included with the Build, Pro, Scale and Enterprise plans; a Free key
    raises :class:`~oxarchive.PlanRequiredError`.

    Example:
        >>> page = client.hyperliquid.news.list(symbols="BTC", min_weight=2, limit=20)
        >>> for story in page.data:
        ...     print(story.first_seen_at, story.headline, story.source)
        >>> for story in client.lighter.news.iterate(start="2026-11-04"):
        ...     ...
    """

    def __init__(self, http: HttpClient, base_path: str = "/v1/hyperliquid") -> None:
        self._http = http
        self._path = f"{base_path}/news"

    @staticmethod
    def _params(
        symbols: Union[str, Sequence[str], None],
        topic: Optional[str],
        min_weight: Optional[int],
        start: Optional[Timestamp],
        end: Optional[Timestamp],
        as_of: Optional[Timestamp],
        cursor: Optional[str],
        limit: Optional[int],
    ) -> Params:
        return {
            "symbols": _symbols(symbols),
            "topic": topic,
            "min_weight": _min_weight(min_weight),
            "start": to_unix_ms(start, "start"),
            "end": to_unix_ms(end, "end"),
            "as_of": to_unix_ms(as_of, "as_of"),
            "cursor": cursor,
            "limit": _limit(limit),
        }

    def _fetch(self) -> Callable[[Params], CursorResponse[List[Any]]]:
        return lambda params: page_of(self._http.get(self._path, params=params), NewsStory)

    def _afetch(self) -> Callable[[Params], Awaitable[CursorResponse[List[Any]]]]:
        async def fetch(params: Params) -> CursorResponse[List[Any]]:
            return page_of(await self._http.aget(self._path, params=params), NewsStory)

        return fetch

    def list(
        self,
        *,
        symbols: Union[str, Sequence[str], None] = None,
        topic: Optional[str] = None,
        min_weight: Optional[int] = None,
        start: Optional[Timestamp] = None,
        end: Optional[Timestamp] = None,
        as_of: Optional[Timestamp] = None,
        cursor: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> CursorResponse[List[NewsStory]]:
        """Get one page of stories, newest first by ``first_seen_at``.

        While ``next_cursor`` is set, pass it back as ``cursor`` with the
        other arguments unchanged.

        Args:
            symbols: Only stories whose lead report names one of these markets
                on this venue: a string (comma separated allowed) or a list,
                at most 20. Case does not matter.
            topic: Only one topic (see :data:`~oxarchive.NewsTopic`).
            min_weight: Only stories of at least this weight, 1 to 3 (default 1).
            start: Earliest ``first_seen_at``, inclusive (default: 24 hours
                before ``end``). A time without a time zone is UTC.
            end: Latest ``first_seen_at``, inclusive (default: now).
            as_of: The feed as we knew it at this time, with the reactions and
                reports recorded by then (default: now). A time in the future
                is now.
            cursor: The previous page's ``next_cursor``, passed back unchanged.
            limit: Stories per page, 1 to 500 (default 100).

        Raises:
            PlanRequiredError: The key's plan does not include news.
        """
        params = self._params(symbols, topic, min_weight, start, end, as_of, cursor, limit)
        return self._fetch()(params)

    async def alist(
        self,
        *,
        symbols: Union[str, Sequence[str], None] = None,
        topic: Optional[str] = None,
        min_weight: Optional[int] = None,
        start: Optional[Timestamp] = None,
        end: Optional[Timestamp] = None,
        as_of: Optional[Timestamp] = None,
        cursor: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> CursorResponse[List[NewsStory]]:
        """Async version of :meth:`list`."""
        params = self._params(symbols, topic, min_weight, start, end, as_of, cursor, limit)
        return await self._afetch()(params)

    def iterate(
        self,
        *,
        symbols: Union[str, Sequence[str], None] = None,
        topic: Optional[str] = None,
        min_weight: Optional[int] = None,
        start: Optional[Timestamp] = None,
        end: Optional[Timestamp] = None,
        as_of: Optional[Timestamp] = None,
        limit: Optional[int] = None,
    ) -> Iterator[NewsStory]:
        """Yield every story in ``[start, end]``, newest first, following ``next_cursor``.

        It stops only when a page has no cursor. When ``end`` is omitted it is
        fixed to the current time before the first request, and the same
        ``end`` is sent on every page. Pass ``as_of`` to read the whole walk
        against one version of the feed.
        """
        params = self._params(symbols, topic, min_weight, start, fixed_end(end), as_of, None, limit)
        return follow(self._fetch(), params)

    def aiterate(
        self,
        *,
        symbols: Union[str, Sequence[str], None] = None,
        topic: Optional[str] = None,
        min_weight: Optional[int] = None,
        start: Optional[Timestamp] = None,
        end: Optional[Timestamp] = None,
        as_of: Optional[Timestamp] = None,
        limit: Optional[int] = None,
    ) -> AsyncIterator[NewsStory]:
        """Async version of :meth:`iterate`."""
        params = self._params(symbols, topic, min_weight, start, fixed_end(end), as_of, None, limit)
        return afollow(self._afetch(), params)
