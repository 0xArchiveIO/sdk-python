"""
oxarchive - Official Python SDK for 0xarchive

Hyperliquid Historical Data API.

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
"""

from .client import Client
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

__version__ = "0.3.11"

__all__ = [
    # Client
    "Client",
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
