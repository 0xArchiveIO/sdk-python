"""Type definitions for the 0xarchive SDK."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Generic, Literal, Optional, TypeVar, Union

from pydantic import BaseModel, Field


# =============================================================================
# Base Types
# =============================================================================

T = TypeVar("T")


class ApiMeta(BaseModel):
    """Response metadata."""

    count: int
    next_cursor: Optional[str] = None
    request_id: str


class ApiResponse(BaseModel, Generic[T]):
    """Standard API response wrapper."""

    success: bool
    data: T
    meta: ApiMeta


# =============================================================================
# Order Book Types
# =============================================================================


class PriceLevel(BaseModel):
    """Single price level in the order book."""

    px: str
    """Price at this level."""

    sz: str
    """Total size at this price level."""

    n: int
    """Number of orders at this level."""


class OrderBook(BaseModel):
    """L2 order book snapshot."""

    coin: str
    """Trading pair symbol (e.g., BTC, ETH)."""

    timestamp: datetime
    """Snapshot timestamp (UTC)."""

    bids: list[PriceLevel]
    """Bid price levels (best bid first)."""

    asks: list[PriceLevel]
    """Ask price levels (best ask first)."""

    mid_price: Optional[str] = None
    """Mid price (best bid + best ask) / 2."""

    spread: Optional[str] = None
    """Spread in absolute terms (best ask - best bid)."""

    spread_bps: Optional[str] = None
    """Spread in basis points."""


# =============================================================================
# Trade/Fill Types
# =============================================================================


class Trade(BaseModel):
    """Trade/fill record with full execution details."""

    coin: str
    """Trading pair symbol."""

    side: Literal["A", "B"]
    """Trade side: 'B' (buy) or 'A' (sell/ask)."""

    price: str
    """Execution price."""

    size: str
    """Trade size."""

    timestamp: datetime
    """Execution timestamp (UTC)."""

    tx_hash: Optional[str] = None
    """Blockchain transaction hash."""

    trade_id: Optional[int] = None
    """Unique trade ID."""

    order_id: Optional[int] = None
    """Associated order ID."""

    crossed: Optional[bool] = None
    """True if taker (crossed the spread), false if maker."""

    fee: Optional[str] = None
    """Trading fee amount."""

    fee_token: Optional[str] = None
    """Fee denomination (e.g., USDC)."""

    closed_pnl: Optional[str] = None
    """Realized PnL if closing a position."""

    direction: Optional[str] = None
    """Position direction (e.g., 'Open Long', 'Close Short', 'Long > Short')."""

    start_position: Optional[str] = None
    """Position size before this trade."""

    user_address: Optional[str] = None
    """User's wallet address (for fill-level data)."""

    maker_address: Optional[str] = None
    """Maker's wallet address (for market-level WebSocket trades)."""

    taker_address: Optional[str] = None
    """Taker's wallet address (for market-level WebSocket trades)."""


# =============================================================================
# Instrument Types
# =============================================================================


class Instrument(BaseModel):
    """Trading instrument specification (Hyperliquid)."""

    model_config = {"populate_by_name": True}

    name: str
    """Instrument symbol (e.g., BTC)."""

    sz_decimals: int = Field(alias="szDecimals")
    """Size decimal precision."""

    max_leverage: Optional[int] = Field(default=None, alias="maxLeverage")
    """Maximum leverage allowed."""

    only_isolated: Optional[bool] = Field(default=None, alias="onlyIsolated")
    """If true, only isolated margin mode is allowed."""

    instrument_type: Optional[Literal["perp", "spot"]] = Field(default=None, alias="instrumentType")
    """Type of instrument."""

    is_active: bool = Field(default=True, alias="isActive")
    """Whether the instrument is currently tradeable."""


class LighterInstrument(BaseModel):
    """Trading instrument specification (Lighter.xyz).

    Lighter instruments have a different schema than Hyperliquid with more
    detailed market configuration including fees and minimum amounts.
    """

    symbol: str
    """Instrument symbol (e.g., BTC, ETH)."""

    market_id: int
    """Unique market identifier."""

    market_type: str
    """Market type (e.g., 'perp')."""

    status: str
    """Market status (e.g., 'active')."""

    taker_fee: float
    """Taker fee rate (e.g., 0.0005 = 0.05%)."""

    maker_fee: float
    """Maker fee rate (e.g., 0.0002 = 0.02%)."""

    liquidation_fee: float
    """Liquidation fee rate."""

    min_base_amount: float
    """Minimum order size in base currency."""

    min_quote_amount: float
    """Minimum order size in quote currency."""

    size_decimals: int
    """Size decimal precision."""

    price_decimals: int
    """Price decimal precision."""

    quote_decimals: int
    """Quote currency decimal precision."""

    is_active: bool
    """Whether the instrument is currently tradeable."""


# =============================================================================
# Funding Types
# =============================================================================


class FundingRate(BaseModel):
    """Funding rate record."""

    coin: str
    """Trading pair symbol."""

    timestamp: datetime
    """Funding timestamp (UTC)."""

    funding_rate: str
    """Funding rate as decimal (e.g., 0.0001 = 0.01%)."""

    premium: Optional[str] = None
    """Premium component of funding rate."""


# =============================================================================
# Open Interest Types
# =============================================================================


class OpenInterest(BaseModel):
    """Open interest snapshot with market context."""

    coin: str
    """Trading pair symbol."""

    timestamp: datetime
    """Snapshot timestamp (UTC)."""

    open_interest: str
    """Total open interest in contracts."""

    mark_price: Optional[str] = None
    """Mark price used for liquidations."""

    oracle_price: Optional[str] = None
    """Oracle price from external feed."""

    day_ntl_volume: Optional[str] = None
    """24-hour notional volume."""

    prev_day_price: Optional[str] = None
    """Price 24 hours ago."""

    mid_price: Optional[str] = None
    """Current mid price."""

    impact_bid_price: Optional[str] = None
    """Impact bid price for liquidations."""

    impact_ask_price: Optional[str] = None
    """Impact ask price for liquidations."""


# =============================================================================
# WebSocket Types
# =============================================================================

WsChannel = Literal["orderbook", "trades", "ticker", "all_tickers"]
"""Available WebSocket channels. Note: ticker/all_tickers are real-time only."""

WsConnectionState = Literal["connecting", "connected", "disconnected", "reconnecting"]
"""WebSocket connection state."""


class WsSubscribed(BaseModel):
    """Subscription confirmed from server."""

    type: Literal["subscribed"]
    channel: WsChannel
    coin: Optional[str] = None


class WsUnsubscribed(BaseModel):
    """Unsubscription confirmed from server."""

    type: Literal["unsubscribed"]
    channel: WsChannel
    coin: Optional[str] = None


class WsPong(BaseModel):
    """Pong response from server."""

    type: Literal["pong"]


class WsError(BaseModel):
    """Error from server."""

    type: Literal["error"]
    message: str


class WsData(BaseModel):
    """Real-time data message from server.

    Note: The `data` field can be either a dict (for orderbook) or a list (for trades).
    - Orderbook: dict with 'levels', 'time', etc.
    - Trades: list of trade objects with 'coin', 'side', 'px', 'sz', etc.
    """

    type: Literal["data"]
    channel: WsChannel
    coin: str
    data: Union[dict[str, Any], list[dict[str, Any]]]


# =============================================================================
# WebSocket Replay Types (Historical Replay Mode)
# =============================================================================


class WsReplayStarted(BaseModel):
    """Replay started response."""

    type: Literal["replay_started"]
    channel: WsChannel
    coin: str
    start: int
    """Start timestamp in milliseconds."""
    end: int
    """End timestamp in milliseconds."""
    speed: float
    """Playback speed multiplier."""


class WsReplayPaused(BaseModel):
    """Replay paused response."""

    type: Literal["replay_paused"]
    current_timestamp: int


class WsReplayResumed(BaseModel):
    """Replay resumed response."""

    type: Literal["replay_resumed"]
    current_timestamp: int


class WsReplayCompleted(BaseModel):
    """Replay completed response."""

    type: Literal["replay_completed"]
    channel: WsChannel
    coin: str
    snapshots_sent: int


class WsReplayStopped(BaseModel):
    """Replay stopped response."""

    type: Literal["replay_stopped"]


class WsHistoricalData(BaseModel):
    """Historical data point (replay mode)."""

    type: Literal["historical_data"]
    channel: WsChannel
    coin: str
    timestamp: int
    data: dict[str, Any]


# =============================================================================
# WebSocket Bulk Stream Types (Bulk Download Mode)
# =============================================================================


class WsStreamStarted(BaseModel):
    """Stream started response."""

    type: Literal["stream_started"]
    channel: WsChannel
    coin: str
    start: int
    """Start timestamp in milliseconds."""
    end: int
    """End timestamp in milliseconds."""


class WsStreamProgress(BaseModel):
    """Stream progress response (sent every ~2 seconds)."""

    type: Literal["stream_progress"]
    snapshots_sent: int


class TimestampedRecord(BaseModel):
    """A record with timestamp for batched data."""

    timestamp: int
    data: dict[str, Any]


class WsHistoricalBatch(BaseModel):
    """Batch of historical data (bulk streaming)."""

    type: Literal["historical_batch"]
    channel: WsChannel
    coin: str
    data: list[TimestampedRecord]


class WsStreamCompleted(BaseModel):
    """Stream completed response."""

    type: Literal["stream_completed"]
    channel: WsChannel
    coin: str
    snapshots_sent: int


class WsStreamStopped(BaseModel):
    """Stream stopped response."""

    type: Literal["stream_stopped"]
    snapshots_sent: int


# =============================================================================
# Error Types
# =============================================================================


class OxArchiveError(Exception):
    """SDK error class."""

    def __init__(self, message: str, code: int, request_id: Optional[str] = None):
        super().__init__(message)
        self.message = message
        self.code = code
        self.request_id = request_id

    def __str__(self) -> str:
        if self.request_id:
            return f"[{self.code}] {self.message} (request_id: {self.request_id})"
        return f"[{self.code}] {self.message}"


# =============================================================================
# Pagination Types
# =============================================================================


class CursorResponse(BaseModel, Generic[T]):
    """Response with cursor for pagination."""

    data: T
    """The paginated data."""

    next_cursor: Optional[str] = None
    """Cursor for the next page (use as cursor parameter)."""


# Type alias for timestamp parameters
Timestamp = Union[int, str, datetime]
"""Timestamp can be Unix ms (int), ISO string, or datetime object."""
