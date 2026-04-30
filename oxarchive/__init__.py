"""
oxarchive - Official Python SDK for 0xarchive

Historical Market Data API for two top-level venue APIs:
- Hyperliquid (perpetuals data from April 2023)
- Hyperliquid HIP-3 builder perps under the Hyperliquid namespace at /v1/hyperliquid/hip3 and client.hyperliquid.hip3
- Lighter.xyz (perpetuals data)

Example:
    >>> from oxarchive import Client
    >>>
    >>> client = Client(api_key="0xa_your_api_key")
    >>>
    >>> # Hyperliquid data
    >>> hl_orderbook = client.hyperliquid.orderbook.get("BTC")
    >>> print(f"BTC mid price: {hl_orderbook.mid_price}")
    >>>
    >>> # Lighter.xyz data
    >>> lighter_orderbook = client.lighter.orderbook.get("BTC")
    >>>
    >>> # Hyperliquid HIP-3 data
    >>> hip3_orderbook = client.hyperliquid.hip3.orderbook.get("km:US500")
    >>>
    >>> # Get historical snapshots
    >>> history = client.hyperliquid.orderbook.history("ETH", start="2024-01-01", end="2024-01-02")
"""

from .client import Client
from .exchanges import HyperliquidClient, Hip3Client, LighterClient
from .resources.orderbook import LighterGranularity
from .orderbook_reconstructor import (
    OrderBookReconstructor,
    OrderbookDelta,
    TickData,
    ReconstructedOrderBook,
    ReconstructOptions,
    reconstruct_orderbook,
    reconstruct_final,
)
from .l4_reconstructor import L4OrderBookReconstructor, L4Order, L2Level
from .types import (
    OrderBook,
    Trade,
    Instrument,
    LighterInstrument,
    Hip3Instrument,
    FundingRate,
    OpenInterest,
    Liquidation,
    LiquidationVolume,
    DataTypeFreshness,
    CoinFreshness,
    CoinSummary,
    PriceSnapshot,
    Candle,
    CandleInterval,
    OxArchiveError,
    # Web3 Auth types
    SiweChallenge,
    Web3SignupResult,
    Web3ApiKey,
    Web3KeysList,
    Web3RevokeResult,
    Web3PaymentRequired,
    Web3SubscribeResult,
    # WebSocket types
    WsChannel,
    WsConnectionState,
    WsSubscribed,
    WsUnsubscribed,
    WsPong,
    WsError,
    WsData,
    # Replay types (Option B)
    WsReplayStarted,
    WsReplayPaused,
    WsReplayResumed,
    WsReplayCompleted,
    WsReplayStopped,
    WsHistoricalData,
    WsReplaySnapshot,
    # Stream types (Option D)
    WsStreamStarted,
    WsStreamProgress,
    WsHistoricalBatch,
    WsStreamCompleted,
    WsStreamStopped,
    TimestampedRecord,
)

# WebSocket client (optional import - requires websockets package)
try:
    from .websocket import OxArchiveWs, WsOptions
    _HAS_WEBSOCKET = True
except ImportError:
    _HAS_WEBSOCKET = False
    OxArchiveWs = None  # type: ignore
    WsOptions = None  # type: ignore

__version__ = "1.4.0"

__all__ = [
    # Client
    "Client",
    # Exchange Clients
    "HyperliquidClient",
    "Hip3Client",
    "LighterClient",
    # WebSocket Client
    "OxArchiveWs",
    "WsOptions",
    # Orderbook Reconstructor (Enterprise tier — Lighter)
    "OrderBookReconstructor",
    "OrderbookDelta",
    "TickData",
    "ReconstructedOrderBook",
    "ReconstructOptions",
    "reconstruct_orderbook",
    "reconstruct_final",
    # L4 Orderbook Reconstructor (Pro+ — Hyperliquid / HIP-3)
    "L4OrderBookReconstructor",
    "L4Order",
    "L2Level",
    # Types
    "OrderBook",
    "Trade",
    "Instrument",
    "LighterInstrument",
    "Hip3Instrument",
    "LighterGranularity",
    "FundingRate",
    "OpenInterest",
    "Liquidation",
    "LiquidationVolume",
    "DataTypeFreshness",
    "CoinFreshness",
    "CoinSummary",
    "PriceSnapshot",
    "Candle",
    "CandleInterval",
    "OxArchiveError",
    # Web3 Auth Types
    "SiweChallenge",
    "Web3SignupResult",
    "Web3ApiKey",
    "Web3KeysList",
    "Web3RevokeResult",
    "Web3PaymentRequired",
    "Web3SubscribeResult",
    # WebSocket Types
    "WsChannel",
    "WsConnectionState",
    "WsSubscribed",
    "WsUnsubscribed",
    "WsPong",
    "WsError",
    "WsData",
    # Replay Types (Option B)
    "WsReplayStarted",
    "WsReplayPaused",
    "WsReplayResumed",
    "WsReplayCompleted",
    "WsReplayStopped",
    "WsHistoricalData",
    "WsReplaySnapshot",
    # Stream Types (Option D)
    "WsStreamStarted",
    "WsStreamProgress",
    "WsHistoricalBatch",
    "WsStreamCompleted",
    "WsStreamStopped",
    "TimestampedRecord",
]
