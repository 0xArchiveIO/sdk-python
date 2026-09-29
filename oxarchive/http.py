"""HTTP client for the 0xarchive API."""

from __future__ import annotations

from typing import Any, Optional

import httpx

from .types import OxArchiveError, _code_for_status

API_VERSION = "2026-10-01"
"""The API version this SDK is written against. Every REST request sends it in
the ``0xArchive-Version`` header, and the WebSocket client sends it as the
``version`` connection parameter. It selects the response shapes the SDK
parses: the standard ``{success, data, meta}`` envelope on every route, RFC
3339 times with integer ``*_ms`` companions, and the live message shapes on
Lighter replay."""

API_VERSION_HEADER = "0xArchive-Version"
"""Request header that selects the API version (echoed on the response)."""


class HttpClient:
    """Internal HTTP client for making API requests."""

    def __init__(self, base_url: str, api_key: str, timeout: float):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self._client: Optional[httpx.Client] = None
        self._async_client: Optional[httpx.AsyncClient] = None

    def _get_headers(self) -> dict[str, str]:
        return {
            "X-API-Key": self.api_key,
            "Content-Type": "application/json",
            API_VERSION_HEADER: API_VERSION,
        }

    @property
    def client(self) -> httpx.Client:
        """Get or create the sync HTTP client."""
        if self._client is None:
            self._client = httpx.Client(
                base_url=self.base_url,
                headers=self._get_headers(),
                timeout=self.timeout,
            )
        return self._client

    @property
    def async_client(self) -> httpx.AsyncClient:
        """Get or create the async HTTP client."""
        if self._async_client is None:
            self._async_client = httpx.AsyncClient(
                base_url=self.base_url,
                headers=self._get_headers(),
                timeout=self.timeout,
            )
        return self._async_client

    def close(self) -> None:
        """Close the HTTP clients.

        Closes the sync client immediately. For proper async client cleanup
        prefer :meth:`aclose`. ``httpx.AsyncClient`` exposes only ``aclose()``,
        so when no event loop is running we drain it on a private loop rather
        than leaking the connection pool.
        """
        if self._client is not None:
            self._client.close()
            self._client = None
        if self._async_client is not None:
            async_client = self._async_client
            self._async_client = None
            import asyncio

            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop is not None:
                # In an async context, schedule the aclose without awaiting.
                loop.create_task(async_client.aclose())
            else:
                # No running loop. Drain on a one-shot loop so the underlying
                # connection pool is released cleanly.
                new_loop = asyncio.new_event_loop()
                try:
                    new_loop.run_until_complete(async_client.aclose())
                finally:
                    new_loop.close()

    async def aclose(self) -> None:
        """Close the async HTTP client."""
        if self._async_client is not None:
            await self._async_client.aclose()
            self._async_client = None

    def _handle_response(self, response: httpx.Response) -> dict[str, Any]:
        """Handle the API response and raise errors if needed.

        A non-2xx response raises :class:`OxArchiveError` carrying the status,
        ``error_code``, ``request_id``, ``param`` and ``valid_values`` from the
        error body, and the whole body as ``details``.
        """
        try:
            data = response.json()
        except Exception:
            if not response.is_success:
                snippet = response.text[:200].strip()
                message = f"Request failed with status {response.status_code}"
                raise OxArchiveError(
                    f"{message}: {snippet}" if snippet else message,
                    response.status_code,
                    error_code=_code_for_status(response.status_code),
                ) from None
            raise OxArchiveError(
                f"Invalid JSON response: {response.text[:200]}",
                response.status_code,
            ) from None

        if not response.is_success:
            raise OxArchiveError.from_response(response.status_code, data)

        if not isinstance(data, dict):
            raise OxArchiveError(
                f"Unexpected response: expected a JSON object, got {type(data).__name__}",
                response.status_code,
            )
        return data

    def get(
        self,
        path: str,
        params: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Make a synchronous GET request."""
        # Filter out None values from params
        if params:
            params = {k: v for k, v in params.items() if v is not None}

        try:
            response = self.client.get(path, params=params)
        except httpx.HTTPError as e:
            raise OxArchiveError(f"Network error: {e}", 0) from e
        return self._handle_response(response)

    async def aget(
        self,
        path: str,
        params: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Make an asynchronous GET request."""
        # Filter out None values from params
        if params:
            params = {k: v for k, v in params.items() if v is not None}

        try:
            response = await self.async_client.get(path, params=params)
        except httpx.HTTPError as e:
            raise OxArchiveError(f"Network error: {e}", 0) from e
        return self._handle_response(response)

    def post(
        self,
        path: str,
        json: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Make a synchronous POST request."""
        try:
            response = self.client.post(path, json=json)
        except httpx.HTTPError as e:
            raise OxArchiveError(f"Network error: {e}", 0) from e
        return self._handle_response(response)

    async def apost(
        self,
        path: str,
        json: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Make an asynchronous POST request."""
        try:
            response = await self.async_client.post(path, json=json)
        except httpx.HTTPError as e:
            raise OxArchiveError(f"Network error: {e}", 0) from e
        return self._handle_response(response)

    def patch(
        self,
        path: str,
        json: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Make a synchronous PATCH request."""
        try:
            response = self.client.patch(path, json=json)
        except httpx.HTTPError as e:
            raise OxArchiveError(f"Network error: {e}", 0) from e
        return self._handle_response(response)

    async def apatch(
        self,
        path: str,
        json: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Make an asynchronous PATCH request."""
        try:
            response = await self.async_client.patch(path, json=json)
        except httpx.HTTPError as e:
            raise OxArchiveError(f"Network error: {e}", 0) from e
        return self._handle_response(response)

    def delete(
        self,
        path: str,
        params: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Make a synchronous DELETE request.

        No 0xarchive DELETE route takes a request body, so none is sent.
        """
        if params:
            params = {k: v for k, v in params.items() if v is not None}

        try:
            response = self.client.delete(path, params=params)
        except httpx.HTTPError as e:
            raise OxArchiveError(f"Network error: {e}", 0) from e
        return self._handle_response(response)

    async def adelete(
        self,
        path: str,
        params: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Make an asynchronous DELETE request."""
        if params:
            params = {k: v for k, v in params.items() if v is not None}

        try:
            response = await self.async_client.delete(path, params=params)
        except httpx.HTTPError as e:
            raise OxArchiveError(f"Network error: {e}", 0) from e
        return self._handle_response(response)
