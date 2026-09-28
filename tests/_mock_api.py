"""A mocked HTTP API for unit tests.

Requests go through the real ``Client`` and ``HttpClient`` into an
``httpx.MockTransport``, so the tests see the exact path and query string the
SDK sends.
"""

from __future__ import annotations

from typing import Any, Callable, Optional, Union

import httpx

from oxarchive import Client

Responder = Callable[[str, dict[str, str]], Union[dict[str, Any], httpx.Response]]


class MockApi:
    """Records every request and answers from a responder function."""

    def __init__(self, responder: Responder) -> None:
        self.responder = responder
        self.requests: list[httpx.Request] = []

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        answer = self.responder(request.url.path, dict(request.url.params))
        if isinstance(answer, httpx.Response):
            return answer
        return httpx.Response(200, json=answer)

    @property
    def calls(self) -> list[tuple[str, dict[str, str]]]:
        """``(path, query)`` of every request, in order."""
        return [(r.url.path, dict(r.url.params)) for r in self.requests]

    @property
    def raw_paths(self) -> list[str]:
        """Paths exactly as sent (percent-encoding preserved)."""
        return [r.url.raw_path.decode().split("?", 1)[0] for r in self.requests]


def mock_client(responder: Responder) -> tuple[Client, MockApi]:
    api = MockApi(responder)
    client = Client(api_key="0xa_test", base_url="https://api.example.test")
    transport = httpx.MockTransport(api.handle)
    http = client._http
    http._client = httpx.Client(
        base_url=http.base_url, headers=http._get_headers(), transport=transport
    )
    http._async_client = httpx.AsyncClient(
        base_url=http.base_url, headers=http._get_headers(), transport=transport
    )
    return client, api


def envelope(
    data: Any,
    *,
    next_cursor: Optional[str] = None,
    **meta: Any,
) -> dict[str, Any]:
    """An API response: ``{"success", "data", "meta"}`` like the server sends."""
    body: dict[str, Any] = {"count": len(data) if isinstance(data, list) else 1}
    if next_cursor is not None:
        body["next_cursor"] = next_cursor
    body["request_id"] = "req-test"
    body.update(meta)
    return {"success": True, "data": data, "meta": body}
