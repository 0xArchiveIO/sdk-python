"""
oxarchive - Official Python SDK for 0xarchive

Historical Market Data API for multiple exchanges:
- Hyperliquid (perpetuals data from April 2023)
- Lighter.xyz (perpetuals data)

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
"""

from .client import Client
from .exchanges import HyperliquidClient, LighterClient
from .types import (
    OrderBook,
    Trade,
    Instrument,
    FundingRate,
    OpenInterest,
    OxArchiveError,
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

__version__ = "0.4.1"

__all__ = [
    # Client
    "Client",
    # Exchange Clients
    "HyperliquidClient",
    "LighterClient",
    # WebSocket Client
    "OxArchiveWs",
    "WsOptions",
    # Types
    "OrderBook",
    "Trade",
    "Instrument",
    "FundingRate",
    "OpenInterest",
    "OxArchiveError",
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
    # Stream Types (Option D)
    "WsStreamStarted",
    "WsStreamProgress",
    "WsHistoricalBatch",
    "WsStreamCompleted",
    "WsStreamStopped",
    "TimestampedRecord",
]
