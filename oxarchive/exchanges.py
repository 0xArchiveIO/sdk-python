"""Exchange-specific client classes."""

from __future__ import annotations

from .http import HttpClient
from .resources import (
    OrderBookResource,
    TradesResource,
    InstrumentsResource,
    LighterInstrumentsResource,
    FundingResource,
    OpenInterestResource,
)


class HyperliquidClient:
    """
    Hyperliquid exchange client.

    Access Hyperliquid market data through the 0xarchive API.

    Example:
        >>> client = oxarchive.Client(api_key="...")
        >>> orderbook = client.hyperliquid.orderbook.get("BTC")
        >>> trades = client.hyperliquid.trades.list("ETH", start=..., end=...)
    """

    def __init__(self, http: HttpClient):
        self._http = http
        base_path = "/v1/hyperliquid"

        self.orderbook = OrderBookResource(http, base_path)
        """Order book data (L2 snapshots from April 2023)"""

        self.trades = TradesResource(http, base_path)
        """Trade/fill history"""

        self.instruments = InstrumentsResource(http, base_path)
        """Trading instruments metadata"""

        self.funding = FundingResource(http, base_path)
        """Funding rates"""

        self.open_interest = OpenInterestResource(http, base_path)
        """Open interest"""


class LighterClient:
    """
    Lighter.xyz exchange client.

    Access Lighter.xyz market data through the 0xarchive API.

    Example:
        >>> client = oxarchive.Client(api_key="...")
        >>> orderbook = client.lighter.orderbook.get("BTC")
        >>> trades = client.lighter.trades.list("ETH", start=..., end=...)
        >>> instruments = client.lighter.instruments.list()
        >>> print(f"ETH taker fee: {instruments[0].taker_fee}")
    """

    def __init__(self, http: HttpClient):
        self._http = http
        base_path = "/v1/lighter"

        self.orderbook = OrderBookResource(http, base_path)
        """Order book data (L2 snapshots)"""

        self.trades = TradesResource(http, base_path)
        """Trade/fill history"""

        self.instruments = LighterInstrumentsResource(http, base_path)
        """Trading instruments metadata (returns LighterInstrument with fees, min amounts, etc.)"""

        self.funding = FundingResource(http, base_path)
        """Funding rates"""

        self.open_interest = OpenInterestResource(http, base_path)
        """Open interest"""
