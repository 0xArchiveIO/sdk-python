"""
oxarchive - Official Python SDK for 0xarchive

Historical Market Data API for two venues, Hyperliquid and Lighter. Lighter has
two deployments: mainnet and Robinhood Chain.
- Hyperliquid (perpetuals data from April 2023)
- Hyperliquid HIP-3 builder perps under the Hyperliquid namespace at /v1/hyperliquid/hip3 and client.hyperliquid.hip3
- Hyperliquid HIP-4 outcome markets under the Hyperliquid namespace at /v1/hyperliquid/hip4 and client.hyperliquid.hip4
- Hyperliquid spot pairs under /v1/hyperliquid/spot and client.spot (trades and candles
  from 2025-03-22, candle floor 2025-03-22T10:50:22Z, rest live from 2026-05-05)
- Lighter mainnet at /v1/lighter and client.lighter
- Lighter on Robinhood Chain at /v1/rh-lighter and client.rh_lighter (USDG-quoted;
  trades from 2026-06-26; order book, open interest, funding and liquidations
  from 2026-08-22)
- Account positions on client.hyperliquid.positions, client.hyperliquid.hip3.positions,
  client.lighter.positions and client.rh_lighter.positions

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
    >>> # Lighter on Robinhood Chain
    >>> rh_orderbook = client.rh_lighter.orderbook.get("AAPL-USDG")
    >>>
    >>> # Hyperliquid HIP-3 data
    >>> hip3_orderbook = client.hyperliquid.hip3.orderbook.get("km:US500")
    >>>
    >>> # Hyperliquid spot data (dashed canonical symbols)
    >>> spot_orderbook = client.spot.orderbook.get("HYPE-USDC")
    >>>
    >>> # Get historical snapshots
    >>> history = client.hyperliquid.orderbook.history("ETH", start="2024-01-01", end="2024-01-02")
"""

from .client import Client
from .exchanges import (
    HyperliquidClient,
    Hip3Client,
    Hip4Client,
    LighterClient,
    RhLighterClient,
    SpotClient,
)
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
    Hip4Outcome,
    Hip4OutcomeAggregate,
    Hip4SideSpec,
    Hip4AggregatedOi,
    Hip4OpenInterestRecord,
    SpotPair,
    SpotTwapStatus,
    SpotTableFreshness,
    BreadthNamespaceCounts,
    BreadthCounts,
    BreadthSnapshot,
    FundingRate,
    OpenInterest,
    Liquidation,
    LiquidationVolume,
    LighterLiquidation,
    LighterLiquidationVolume,
    LiquidationLevelBucket,
    LiquidationLevels,
    LiquidationLevelsHistoryItem,
    TriggerLevelBucket,
    TriggerLevels,
    TriggerLevelsHistoryItem,
    DataTypeFreshness,
    CoinFreshness,
    CoinSummary,
    PriceSnapshot,
    Candle,
    CandleInterval,
    OxArchiveError,
    CursorResponse,
    ResponseMeta,
    # Account positions types
    Position,
    PositionLeverage,
    PositionCumFunding,
    PositionChange,
    MarketPosition,
    MarketPositionsSummary,
    AccountSummary,
    WalletPositions,
    LighterL1Account,
    LighterL1Accounts,
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
    WsL4Snapshot,
    WsL4Batch,
    # Live Lighter payload types
    LighterLiveTrade,
    LighterMarketContext,
    LighterMarketContextUpdate,
    # Replay types (Option B)
    WsReplayStarted,
    WsReplayPaused,
    WsReplayResumed,
    WsReplayCompleted,
    WsReplayStopped,
    WsHistoricalData,
    WsReplaySnapshot,
    # Bulk stream types (deprecated: the server has discontinued bulk streaming)
    WsStreamStarted,
    WsStreamProgress,
    WsHistoricalBatch,
    WsStreamCompleted,
    WsStreamStopped,
    TimestampedRecord,
    # HIP-4 settlement event
    WsOutcomeSettled,
)

# WebSocket client (optional import - requires websockets package)
try:
    from .websocket import OxArchiveWs, WsOptions
    _HAS_WEBSOCKET = True
except ImportError:
    _HAS_WEBSOCKET = False
    OxArchiveWs = None  # type: ignore
    WsOptions = None  # type: ignore

__version__ = "1.12.0"

__all__ = [
    # Client
    "Client",
    # Exchange Clients
    "HyperliquidClient",
    "Hip3Client",
    "Hip4Client",
    "LighterClient",
    "RhLighterClient",
    "SpotClient",
    # WebSocket Client
    "OxArchiveWs",
    "WsOptions",
    # Orderbook Reconstructor (Lighter)
    "OrderBookReconstructor",
    "OrderbookDelta",
    "TickData",
    "ReconstructedOrderBook",
    "ReconstructOptions",
    "reconstruct_orderbook",
    "reconstruct_final",
    # L4 Orderbook Reconstructor (Hyperliquid / HIP-3)
    "L4OrderBookReconstructor",
    "L4Order",
    "L2Level",
    # Types
    "OrderBook",
    "Trade",
    "Instrument",
    "LighterInstrument",
    "Hip3Instrument",
    "Hip4Outcome",
    "Hip4OutcomeAggregate",
    "Hip4SideSpec",
    "Hip4AggregatedOi",
    "Hip4OpenInterestRecord",
    "SpotPair",
    "SpotTwapStatus",
    "SpotTableFreshness",
    "BreadthNamespaceCounts",
    "BreadthCounts",
    "BreadthSnapshot",
    "LighterGranularity",
    "FundingRate",
    "OpenInterest",
    "Liquidation",
    "LiquidationVolume",
    "LighterLiquidation",
    "LighterLiquidationVolume",
    "LiquidationLevelBucket",
    "LiquidationLevels",
    "LiquidationLevelsHistoryItem",
    "TriggerLevelBucket",
    "TriggerLevels",
    "TriggerLevelsHistoryItem",
    "DataTypeFreshness",
    "CoinFreshness",
    "CoinSummary",
    "PriceSnapshot",
    "Candle",
    "CandleInterval",
    "OxArchiveError",
    "CursorResponse",
    "ResponseMeta",
    # Account Positions Types
    "Position",
    "PositionLeverage",
    "PositionCumFunding",
    "PositionChange",
    "MarketPosition",
    "MarketPositionsSummary",
    "AccountSummary",
    "WalletPositions",
    "LighterL1Account",
    "LighterL1Accounts",
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
    "WsL4Snapshot",
    "WsL4Batch",
    # Live Lighter Payload Types
    "LighterLiveTrade",
    "LighterMarketContext",
    "LighterMarketContextUpdate",
    # Replay Types (Option B)
    "WsReplayStarted",
    "WsReplayPaused",
    "WsReplayResumed",
    "WsReplayCompleted",
    "WsReplayStopped",
    "WsHistoricalData",
    "WsReplaySnapshot",
    # Bulk stream types (deprecated: the server has discontinued bulk streaming)
    "WsStreamStarted",
    "WsStreamProgress",
    "WsHistoricalBatch",
    "WsStreamCompleted",
    "WsStreamStopped",
    "TimestampedRecord",
    # HIP-4 Settlement Event
    "WsOutcomeSettled",
]
