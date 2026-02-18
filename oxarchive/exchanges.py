"""Exchange-specific client classes."""

from __future__ import annotations

from .http import HttpClient
from .resources import (
    OrderBookResource,
    TradesResource,
    InstrumentsResource,
    LighterInstrumentsResource,
    Hip3InstrumentsResource,
    FundingResource,
    OpenInterestResource,
    CandlesResource,
    LiquidationsResource,
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

        self.candles = CandlesResource(http, base_path)
        """OHLCV candle data"""

        self.liquidations = LiquidationsResource(http, base_path)
        """Liquidation events (May 2025+)"""

        self.hip3 = Hip3Client(http)
        """HIP-3 builder-deployed perpetuals (Pro+ only, February 2026+)"""


class Hip3Client:
    """
    HIP-3 builder-deployed perpetuals client.

    Access Hyperliquid HIP-3 builder perps data through the 0xarchive API.
    Requires Pro tier or higher.

    Example:
        >>> client = oxarchive.Client(api_key="...")
        >>> orderbook = client.hyperliquid.hip3.orderbook.get("xyz:XYZ100")
        >>> trades = client.hyperliquid.hip3.trades.recent("xyz:XYZ100")
    """

    def __init__(self, http: HttpClient):
        self._http = http
        base_path = "/v1/hyperliquid/hip3"
        coin_transform = lambda c: c  # noqa: E731 — HIP-3 coins are case-sensitive (e.g. "xyz:XYZ100")

        self.instruments = Hip3InstrumentsResource(http, base_path, coin_transform=coin_transform)
        """HIP-3 instruments with latest market data"""

        self.orderbook = OrderBookResource(http, base_path, coin_transform=coin_transform)
        """Order book snapshots (February 2026+)"""

        self.trades = TradesResource(http, base_path, coin_transform=coin_transform)
        """Trade/fill history"""

        self.funding = FundingResource(http, base_path, coin_transform=coin_transform)
        """Funding rates"""

        self.open_interest = OpenInterestResource(http, base_path, coin_transform=coin_transform)
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

        self.candles = CandlesResource(http, base_path)
        """OHLCV candle data"""
