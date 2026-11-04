"""Cursor iteration for the Build-and-above dataset resources.

An iterator follows ``next_cursor`` and stops only when a page has none. A
page can be short, or even empty, and still not be the last, so the page size
never ends the walk. Every other parameter is sent unchanged on every page.
"""

from __future__ import annotations

import time
from typing import Any, AsyncIterator, Awaitable, Callable, Iterator, Optional, TypeVar

from .._time import to_unix_ms
from ..types import CursorResponse, OxArchiveError, ResponseMeta, Timestamp

R = TypeVar("R")

Params = dict[str, Any]


def now_ms() -> int:
    """The current time in Unix milliseconds."""
    return int(time.time() * 1000)


def fixed_end(end: Optional[Timestamp]) -> int:
    """``end`` in Unix milliseconds, or now when it is omitted.

    An iterator fixes its window before the first request: the server's
    default ``end`` is the time of each request, so a walk over many pages
    would otherwise slide forward as it runs.
    """
    ms = to_unix_ms(end, "end")
    return now_ms() if ms is None else ms


def page_of(payload: dict[str, Any], model: Any) -> CursorResponse[list[Any]]:
    """One page of ``model`` records with its cursor and meta."""
    meta = ResponseMeta.of(payload)
    data = [model.model_validate(item) for item in payload.get("data") or []]
    return CursorResponse(data=data, next_cursor=meta.next_cursor, meta=meta)


def _repeated(cursor: str, page: CursorResponse[Any]) -> OxArchiveError:
    request_id = page.meta.request_id if page.meta is not None else None
    return OxArchiveError(
        f"The API answered with the cursor it was sent ({cursor!r}). Stopping instead of "
        "requesting the same page again; restart the walk, and quote the request_id if it repeats.",
        200,
        request_id,
        error_code="internal_error",
    )


def follow(fetch: Callable[[Params], CursorResponse[list[R]]], params: Params) -> Iterator[R]:
    """Yield every record of every page, following ``next_cursor``."""
    query = dict(params)
    while True:
        page = fetch(query)
        yield from page.data
        cursor = page.next_cursor
        if not cursor:
            return
        if cursor == query.get("cursor"):
            raise _repeated(cursor, page)
        query = {**query, "cursor": cursor}


async def afollow(
    fetch: Callable[[Params], Awaitable[CursorResponse[list[R]]]], params: Params
) -> AsyncIterator[R]:
    """Async version of :func:`follow`."""
    query = dict(params)
    while True:
        page = await fetch(query)
        for record in page.data:
            yield record
        cursor = page.next_cursor
        if not cursor:
            return
        if cursor == query.get("cursor"):
            raise _repeated(cursor, page)
        query = {**query, "cursor": cursor}
