"""0xarchive API client."""

from __future__ import annotations

from typing import Optional

from .http import HttpClient
from .exchanges import HyperliquidClient, LighterClient
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

    Supports multiple exchanges:
    - `client.hyperliquid` - Hyperliquid perpetuals (April 2023+)
    - `client.lighter` - Lighter.xyz perpetuals

    Example:
        >>> from oxarchive import Client
        >>>
        >>> client = Client(api_key="ox_your_api_key")
        >>>
        >>> # Hyperliquid data
        >>> hl_orderbook = client.hyperliquid.orderbook.get("BTC")
        >>> print(f"BTC mid price: {hl_orderbook.mid_price}")
        >>>
        >>> # Lighter.xyz data
        >>> lighter_orderbook = client.lighter.orderbook.get("BTC")
        >>>
        >>> # Get historical snapshots
        >>> history = client.hyperliquid.orderbook.history("ETH", start="2024-01-01", end="2024-01-02")
        >>>
        >>> # List all instruments
        >>> instruments = client.hyperliquid.instruments.list()

    Async example:
        >>> import asyncio
        >>> from oxarchive import Client
        >>>
        >>> async def main():
        ...     client = Client(api_key="ox_your_api_key")
        ...     orderbook = await client.hyperliquid.orderbook.aget("BTC")
        ...     print(f"BTC mid price: {orderbook.mid_price}")
        ...     await client.aclose()
        >>>
        >>> asyncio.run(main())

    Legacy usage (deprecated, will be removed in v2.0):
        >>> # These still work but use client.hyperliquid.* instead
        >>> orderbook = client.orderbook.get("BTC")  # deprecated
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

        # Exchange-specific clients (recommended)
        self.hyperliquid = HyperliquidClient(self._http)
        """Hyperliquid exchange data (orderbook, trades, funding, OI from April 2023)"""

        self.lighter = LighterClient(self._http)
        """Lighter.xyz exchange data (orderbook reconstructed from checkpoints + deltas)"""

        # Legacy resource namespaces (deprecated - use client.hyperliquid.* instead)
        # These will be removed in v2.0
        # Note: Using /v1/hyperliquid base path for backward compatibility
        legacy_base = "/v1/hyperliquid"
        self.orderbook = OrderBookResource(self._http, legacy_base)
        """[DEPRECATED] Use client.hyperliquid.orderbook instead"""

        self.trades = TradesResource(self._http, legacy_base)
        """[DEPRECATED] Use client.hyperliquid.trades instead"""

        self.instruments = InstrumentsResource(self._http, legacy_base)
        """[DEPRECATED] Use client.hyperliquid.instruments instead"""

        self.funding = FundingResource(self._http, legacy_base)
        """[DEPRECATED] Use client.hyperliquid.funding instead"""

        self.open_interest = OpenInterestResource(self._http, legacy_base)
        """[DEPRECATED] Use client.hyperliquid.open_interest instead"""

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
