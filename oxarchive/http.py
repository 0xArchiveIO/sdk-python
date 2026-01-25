"""HTTP client for the 0xarchive API."""

from __future__ import annotations

from typing import Any, Optional, TypeVar, Type
import httpx
from pydantic import BaseModel

from .types import OxArchiveError

T = TypeVar("T", bound=BaseModel)


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

        Note: This closes the sync client immediately. For the async client,
        use aclose() instead, or call this from a sync context where you
        don't need to await the async cleanup.
        """
        if self._client is not None:
            self._client.close()
            self._client = None
        if self._async_client is not None:
            # Close async client synchronously (will log warning but works)
            # For proper cleanup, use aclose() in async contexts
            try:
                import asyncio
                loop = asyncio.get_running_loop()
                loop.create_task(self._async_client.aclose())
            except RuntimeError:
                # No running loop, close synchronously (httpx supports this)
                self._async_client.close()
            self._async_client = None

    async def aclose(self) -> None:
        """Close the async HTTP client."""
        if self._async_client is not None:
            await self._async_client.aclose()
            self._async_client = None

    def _handle_response(self, response: httpx.Response) -> dict[str, Any]:
        """Handle the API response and raise errors if needed."""
        try:
            data = response.json()
        except Exception:
            raise OxArchiveError(
                f"Invalid JSON response: {response.text[:200]}",
                response.status_code,
            )

        if not response.is_success:
            error_msg = data.get("error", f"Request failed with status {response.status_code}")
            request_id = data.get("request_id")
            raise OxArchiveError(error_msg, response.status_code, request_id)

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

        response = self.client.get(path, params=params)
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

        response = await self.async_client.get(path, params=params)
        return self._handle_response(response)
