"""0xarchive API client."""

from __future__ import annotations

from typing import Optional

from .http import HttpClient
from .resources import (
    OrderBookResource,
    TradesResource,
    InstrumentsResource,
    FundingResource,
    OpenInterestResource,
)

DEFAULT_BASE_URL = "https://api.0xarchive.io"
DEFAULT_TIMEOUT = 30.0


class Client:
    """
    0xarchive API client.

    Example:
        >>> from oxarchive import Client
        >>>
        >>> client = Client(api_key="ox_your_api_key")
        >>>
        >>> # Get current order book
        >>> orderbook = client.orderbook.get("BTC")
        >>> print(f"BTC mid price: {orderbook.mid_price}")
        >>>
        >>> # Get historical snapshots
        >>> history = client.orderbook.history("ETH", start="2024-01-01", end="2024-01-02")
        >>>
        >>> # List all instruments
        >>> instruments = client.instruments.list()

    Async example:
        >>> import asyncio
        >>> from oxarchive import Client
        >>>
        >>> async def main():
        ...     client = Client(api_key="ox_your_api_key")
        ...     orderbook = await client.orderbook.aget("BTC")
        ...     print(f"BTC mid price: {orderbook.mid_price}")
        ...     await client.aclose()
        >>>
        >>> asyncio.run(main())
    """

    def __init__(
        self,
        api_key: str,
        *,
        base_url: Optional[str] = None,
        timeout: Optional[float] = None,
    ):
        """
        Create a new 0xarchive client.

        Args:
            api_key: Your 0xarchive API key
            base_url: Base URL for the API (defaults to https://api.0xarchive.io)
            timeout: Request timeout in seconds (defaults to 30.0)
        """
        if not api_key:
            raise ValueError("API key is required. Get one at https://0xarchive.io/signup")

        self._http = HttpClient(
            base_url=base_url or DEFAULT_BASE_URL,
            api_key=api_key,
            timeout=timeout or DEFAULT_TIMEOUT,
        )

        # Initialize resource namespaces
        self.orderbook = OrderBookResource(self._http)
        """Order book data (L2 snapshots from April 2023)"""

        self.trades = TradesResource(self._http)
        """Trade/fill history"""

        self.instruments = InstrumentsResource(self._http)
        """Trading instruments metadata"""

        self.funding = FundingResource(self._http)
        """Funding rates"""

        self.open_interest = OpenInterestResource(self._http)
        """Open interest"""

    def close(self) -> None:
        """Close the HTTP client and release resources."""
        self._http.close()

    async def aclose(self) -> None:
        """Close the async HTTP client and release resources."""
        await self._http.aclose()

    def __enter__(self) -> "Client":
        return self

    def __exit__(self, *args) -> None:
        self.close()

    async def __aenter__(self) -> "Client":
        return self

    async def __aexit__(self, *args) -> None:
        await self.aclose()
