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

    name: str
    """Instrument symbol (e.g., BTC)."""

    sz_decimals: int
    """Size decimal precision."""

    max_leverage: Optional[int] = None
    """Maximum leverage allowed."""

    only_isolated: Optional[bool] = None
    """If true, only isolated margin mode is allowed."""

    instrument_type: Optional[Literal["perp", "spot"]] = None
    """Type of instrument."""

    is_active: bool = True
    """Whether the instrument is currently tradeable."""


class Hip3Instrument(BaseModel):
    """HIP-3 Builder Perps instrument with latest market data.

    Derived from live open interest data. Useful for discovering
    available HIP-3 coins and their current market context.
    """

    coin: str
    """Full coin name (e.g., km:US500, xyz:XYZ100)."""

    namespace: str
    """Builder namespace (e.g., km, xyz)."""

    ticker: str
    """Ticker within the namespace (e.g., US500, XYZ100)."""

    mark_price: Optional[float] = None
    """Latest mark price."""

    open_interest: Optional[float] = None
    """Latest open interest."""

    mid_price: Optional[float] = None
    """Latest mid price."""

    latest_timestamp: Optional[datetime] = None
    """Timestamp of latest data point."""


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
# Liquidation Types
# =============================================================================


class Liquidation(BaseModel):
    """Liquidation event record."""

    coin: str
    """Trading pair symbol."""

    timestamp: datetime
    """Liquidation timestamp (UTC)."""

    liquidated_user: str
    """Address of the liquidated user."""

    liquidator_user: str
    """Address of the liquidator."""

    price: str
    """Liquidation execution price."""

    size: str
    """Liquidation size."""

    side: Literal["B", "S"]
    """Side: 'B' (buy) or 'S' (sell)."""

    mark_price: Optional[str] = None
    """Mark price at time of liquidation."""

    closed_pnl: Optional[str] = None
    """Realized PnL from the liquidation."""

    direction: Optional[str] = None
    """Position direction (e.g., 'Open Long', 'Close Short')."""

    trade_id: Optional[int] = None
    """Unique trade ID."""

    tx_hash: Optional[str] = None
    """Blockchain transaction hash."""


# =============================================================================
# Liquidation Volume Types
# =============================================================================


class LiquidationVolume(BaseModel):
    """Pre-aggregated liquidation volume bucket."""

    coin: str
    """Trading pair symbol."""

    timestamp: datetime
    """Bucket timestamp (UTC)."""

    total_usd: float
    """Total liquidation volume in USD."""

    long_usd: float
    """Long liquidation volume in USD."""

    short_usd: float
    """Short liquidation volume in USD."""

    count: int
    """Total number of liquidations."""

    long_count: int
    """Number of long liquidations."""

    short_count: int
    """Number of short liquidations."""


# =============================================================================
# Freshness Types
# =============================================================================


class DataTypeFreshness(BaseModel):
    """Freshness data for a single data type."""

    last_updated: Optional[datetime] = None
    """Timestamp of last data point."""

    lag_ms: Optional[int] = None
    """Lag in milliseconds from real-time."""


class CoinFreshness(BaseModel):
    """Per-coin freshness across all data types."""

    coin: str
    """Trading pair symbol."""

    exchange: str
    """Exchange name."""

    measured_at: datetime
    """When this freshness was measured."""

    orderbook: DataTypeFreshness
    """Orderbook data freshness."""

    trades: DataTypeFreshness
    """Trades data freshness."""

    funding: DataTypeFreshness
    """Funding rate data freshness."""

    open_interest: DataTypeFreshness
    """Open interest data freshness."""

    liquidations: Optional[DataTypeFreshness] = None
    """Liquidations data freshness."""


# =============================================================================
# Market Summary Types
# =============================================================================


class CoinSummary(BaseModel):
    """Combined market summary for a coin."""

    coin: str
    """Trading pair symbol."""

    timestamp: datetime
    """Summary timestamp."""

    mark_price: Optional[str] = None
    """Current mark price."""

    oracle_price: Optional[str] = None
    """Current oracle price."""

    mid_price: Optional[str] = None
    """Current mid price."""

    funding_rate: Optional[str] = None
    """Current funding rate."""

    premium: Optional[str] = None
    """Current premium."""

    open_interest: Optional[str] = None
    """Current open interest."""

    volume_24h: Optional[str] = None
    """24-hour trading volume."""

    liquidation_volume_24h: Optional[float] = None
    """24-hour total liquidation volume in USD."""

    long_liquidation_volume_24h: Optional[float] = None
    """24-hour long liquidation volume in USD."""

    short_liquidation_volume_24h: Optional[float] = None
    """24-hour short liquidation volume in USD."""


class PriceSnapshot(BaseModel):
    """Mark/oracle price at a point in time."""

    timestamp: datetime
    """Snapshot timestamp."""

    mark_price: Optional[str] = None
    """Mark price."""

    oracle_price: Optional[str] = None
    """Oracle price."""

    mid_price: Optional[str] = None
    """Mid price."""


# =============================================================================
# Candle Types
# =============================================================================


CandleInterval = Literal["1m", "5m", "15m", "30m", "1h", "4h", "1d", "1w"]
"""Candle interval for OHLCV data."""


class Candle(BaseModel):
    """OHLCV candle data."""

    timestamp: datetime
    """Candle open timestamp (UTC)."""

    open: float
    """Opening price."""

    high: float
    """Highest price during the interval."""

    low: float
    """Lowest price during the interval."""

    close: float
    """Closing price."""

    volume: float
    """Total volume traded during the interval."""

    quote_volume: Optional[float] = None
    """Total quote volume (volume * price)."""

    trade_count: Optional[int] = None
    """Number of trades during the interval."""


# =============================================================================
# WebSocket Types
# =============================================================================

WsChannel = Literal[
    "orderbook", "trades", "candles", "liquidations", "ticker", "all_tickers",
    "open_interest", "funding",
    "lighter_orderbook", "lighter_trades", "lighter_candles",
    "lighter_open_interest", "lighter_funding",
    "hip3_orderbook", "hip3_trades", "hip3_candles",
    "hip3_open_interest", "hip3_funding",
]
"""Available WebSocket channels.

Notes:
- ticker/all_tickers are real-time only.
- liquidations is historical only (May 2025+).
- open_interest, funding, lighter_open_interest, lighter_funding,
  hip3_open_interest, hip3_funding are historical only (replay/stream).
"""

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
    """Replay started response.

    In single-channel mode, ``channel`` is set to the replayed channel.
    In multi-channel mode, ``channels`` lists all channels being replayed
    and ``channel`` may be absent or set to the first channel.
    """

    type: Literal["replay_started"]
    channel: Optional[WsChannel] = None
    """Channel (single-channel mode)."""
    channels: Optional[list[WsChannel]] = None
    """Channels (multi-channel mode)."""
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
    """Replay completed response.

    In multi-channel mode, ``channels`` lists all channels that were replayed.
    """

    type: Literal["replay_completed"]
    channel: Optional[WsChannel] = None
    """Channel (single-channel mode)."""
    channels: Optional[list[WsChannel]] = None
    """Channels (multi-channel mode)."""
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


class WsReplaySnapshot(BaseModel):
    """Initial state snapshot for a channel in multi-channel replay.

    Before the timeline starts, the server sends a replay_snapshot for each
    channel to provide the initial state. For example, the latest orderbook
    state, most recent funding rate, and current open interest at the replay
    start time.
    """

    type: Literal["replay_snapshot"]
    channel: WsChannel
    coin: str
    timestamp: int
    """Timestamp of the snapshot (ms)."""
    data: dict[str, Any]
    """Initial state data for this channel."""


class OrderbookDelta(BaseModel):
    """Orderbook delta for tick-level data."""

    timestamp: int
    """Timestamp in milliseconds."""

    side: Literal["bid", "ask"]
    """Side: 'bid' or 'ask'."""

    price: float
    """Price level."""

    size: float
    """New size (0 = level removed)."""

    sequence: int
    """Sequence number for ordering."""


class WsHistoricalTickData(BaseModel):
    """Historical tick data (granularity='tick' mode) - checkpoint + deltas.

    This message type is sent when using granularity='tick' for Lighter.xyz
    orderbook data. It provides a full checkpoint followed by incremental deltas.
    """

    type: Literal["historical_tick_data"]
    channel: WsChannel
    coin: str
    checkpoint: dict[str, Any]
    """Initial checkpoint (full orderbook snapshot)."""
    deltas: list[OrderbookDelta]
    """Incremental deltas to apply after checkpoint."""


# =============================================================================
# WebSocket Bulk Stream Types (Bulk Download Mode)
# =============================================================================


class WsStreamStarted(BaseModel):
    """Stream started response.

    In multi-channel mode, ``channels`` lists all channels being streamed.
    """

    type: Literal["stream_started"]
    channel: Optional[WsChannel] = None
    """Channel (single-channel mode)."""
    channels: Optional[list[WsChannel]] = None
    """Channels (multi-channel mode)."""
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
    """Stream completed response.

    In multi-channel mode, ``channels`` lists all channels that were streamed.
    """

    type: Literal["stream_completed"]
    channel: Optional[WsChannel] = None
    """Channel (single-channel mode)."""
    channels: Optional[list[WsChannel]] = None
    """Channels (multi-channel mode)."""
    coin: str
    snapshots_sent: int


class WsStreamStopped(BaseModel):
    """Stream stopped response."""

    type: Literal["stream_stopped"]
    snapshots_sent: int


class WsGapDetected(BaseModel):
    """Gap detected in historical data stream.

    Sent when there's a gap exceeding the threshold between consecutive data points.
    Thresholds: 2 minutes for orderbook/candles/liquidations, 60 minutes for trades.
    """

    type: Literal["gap_detected"]
    channel: WsChannel
    coin: str
    gap_start: int
    """Start of the gap (last data point timestamp in ms)."""
    gap_end: int
    """End of the gap (next data point timestamp in ms)."""
    duration_minutes: int
    """Gap duration in minutes."""


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


# =============================================================================
# Data Quality Types
# =============================================================================


class SystemStatus(BaseModel):
    """System status values: operational, degraded, outage, maintenance."""

    status: Literal["operational", "degraded", "outage", "maintenance"]


class ExchangeStatus(BaseModel):
    """Status of a single exchange."""

    status: Literal["operational", "degraded", "outage", "maintenance"]
    """Current status."""

    last_data_at: Optional[datetime] = None
    """Timestamp of last received data."""

    latency_ms: Optional[int] = None
    """Current latency in milliseconds."""


class DataTypeStatus(BaseModel):
    """Status of a data type (orderbook, fills, etc.)."""

    status: Literal["operational", "degraded", "outage", "maintenance"]
    """Current status."""

    completeness_24h: float
    """Data completeness over last 24 hours (0-100)."""


class StatusResponse(BaseModel):
    """Overall system status response."""

    status: Literal["operational", "degraded", "outage", "maintenance"]
    """Overall system status."""

    updated_at: datetime
    """When this status was computed."""

    exchanges: dict[str, ExchangeStatus]
    """Per-exchange status."""

    data_types: dict[str, DataTypeStatus]
    """Per-data-type status."""

    active_incidents: int
    """Number of active incidents."""


class DataTypeCoverage(BaseModel):
    """Coverage information for a specific data type."""

    earliest: datetime
    """Earliest available data timestamp."""

    latest: datetime
    """Latest available data timestamp."""

    total_records: int
    """Total number of records."""

    symbols: int
    """Number of symbols with data."""

    resolution: Optional[str] = None
    """Data resolution (e.g., '1.2s', '1m')."""

    lag: Optional[str] = None
    """Current data lag."""

    completeness: float
    """Completeness percentage (0-100)."""


class ExchangeCoverage(BaseModel):
    """Coverage for a single exchange."""

    exchange: str
    """Exchange name."""

    data_types: dict[str, DataTypeCoverage]
    """Coverage per data type."""


class CoverageResponse(BaseModel):
    """Overall coverage response."""

    exchanges: list[ExchangeCoverage]
    """Coverage for all exchanges."""


class CoverageGap(BaseModel):
    """Gap information for per-symbol coverage."""

    start: datetime
    """Start of the gap (last data before gap)."""

    end: datetime
    """End of the gap (first data after gap)."""

    duration_minutes: int
    """Duration of the gap in minutes."""


class DataCadence(BaseModel):
    """Empirical data cadence measurement based on last 7 days of data."""

    median_interval_seconds: float
    """Median interval between consecutive records in seconds."""

    p95_interval_seconds: float
    """95th percentile interval between consecutive records in seconds."""

    sample_count: int
    """Number of intervals sampled for this measurement."""


class SymbolDataTypeCoverage(BaseModel):
    """Coverage for a specific symbol and data type."""

    earliest: datetime
    """Earliest available data timestamp."""

    latest: datetime
    """Latest available data timestamp."""

    total_records: int
    """Total number of records."""

    completeness: float
    """24-hour completeness percentage (0-100)."""

    historical_coverage: float | None = None
    """Historical coverage percentage (0-100) based on hours with data / total hours."""

    gaps: list[CoverageGap]
    """Detected data gaps within the requested time window."""

    cadence: DataCadence | None = None
    """Empirical data cadence (present when sufficient data exists)."""


class SymbolCoverageResponse(BaseModel):
    """Per-symbol coverage response."""

    exchange: str
    """Exchange name."""

    symbol: str
    """Symbol name."""

    data_types: dict[str, SymbolDataTypeCoverage]
    """Coverage per data type."""


class Incident(BaseModel):
    """Data quality incident."""

    id: str
    """Unique incident ID."""

    status: str
    """Status: open, investigating, identified, monitoring, resolved."""

    severity: str
    """Severity: minor, major, critical."""

    exchange: Optional[str] = None
    """Affected exchange (if specific to one)."""

    data_types: list[str]
    """Affected data types."""

    symbols_affected: list[str]
    """Affected symbols."""

    started_at: datetime
    """When the incident started."""

    resolved_at: Optional[datetime] = None
    """When the incident was resolved."""

    duration_minutes: Optional[int] = None
    """Total duration in minutes."""

    title: str
    """Incident title."""

    description: Optional[str] = None
    """Detailed description."""

    root_cause: Optional[str] = None
    """Root cause analysis."""

    resolution: Optional[str] = None
    """Resolution details."""

    records_affected: Optional[int] = None
    """Number of records affected."""

    records_recovered: Optional[int] = None
    """Number of records recovered."""


class Pagination(BaseModel):
    """Pagination info for incident list."""

    total: int
    """Total number of incidents."""

    limit: int
    """Page size limit."""

    offset: int
    """Current offset."""


class IncidentsResponse(BaseModel):
    """Incidents list response."""

    incidents: list[Incident]
    """List of incidents."""

    pagination: Pagination
    """Pagination info."""


class WebSocketLatency(BaseModel):
    """WebSocket latency metrics."""

    current_ms: int
    """Current latency."""

    avg_1h_ms: int
    """1-hour average latency."""

    avg_24h_ms: int
    """24-hour average latency."""

    p99_24h_ms: Optional[int] = None
    """24-hour P99 latency."""


class ApiLatency(BaseModel):
    """REST API latency metrics."""

    current_ms: int
    """Current latency."""

    avg_1h_ms: int
    """1-hour average latency."""

    avg_24h_ms: int
    """24-hour average latency."""


class DataFreshness(BaseModel):
    """Data freshness metrics (lag from source)."""

    orderbook_lag_ms: Optional[int] = None
    """Orderbook data lag."""

    fills_lag_ms: Optional[int] = None
    """Fills/trades data lag."""

    funding_lag_ms: Optional[int] = None
    """Funding rate data lag."""

    oi_lag_ms: Optional[int] = None
    """Open interest data lag."""


class ExchangeLatency(BaseModel):
    """Latency metrics for a single exchange."""

    websocket: Optional[WebSocketLatency] = None
    """WebSocket latency metrics."""

    rest_api: Optional[ApiLatency] = None
    """REST API latency metrics."""

    data_freshness: DataFreshness
    """Data freshness metrics."""


class LatencyResponse(BaseModel):
    """Overall latency response."""

    measured_at: datetime
    """When these metrics were measured."""

    exchanges: dict[str, ExchangeLatency]
    """Per-exchange latency metrics."""


class SlaTargets(BaseModel):
    """SLA targets."""

    uptime: float
    """Uptime target percentage."""

    data_completeness: float
    """Data completeness target percentage."""

    api_latency_p99_ms: int
    """API P99 latency target in milliseconds."""


class CompletenessMetrics(BaseModel):
    """Completeness metrics per data type."""

    orderbook: float
    """Orderbook completeness percentage."""

    fills: float
    """Fills completeness percentage."""

    funding: float
    """Funding rate completeness percentage."""

    overall: float
    """Overall completeness percentage."""


class SlaActual(BaseModel):
    """Actual SLA metrics."""

    uptime: float
    """Actual uptime percentage."""

    uptime_status: str
    """'met' or 'missed'."""

    data_completeness: CompletenessMetrics
    """Actual completeness metrics."""

    completeness_status: str
    """'met' or 'missed'."""

    api_latency_p99_ms: int
    """Actual API P99 latency."""

    latency_status: str
    """'met' or 'missed'."""


class SlaResponse(BaseModel):
    """SLA compliance response."""

    period: str
    """Period covered (e.g., '2026-01')."""

    sla_targets: SlaTargets
    """Target SLA metrics."""

    actual: SlaActual
    """Actual SLA metrics."""

    incidents_this_period: int
    """Number of incidents in this period."""

    total_downtime_minutes: int
    """Total downtime in minutes."""
