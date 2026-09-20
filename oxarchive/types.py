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

    coverage_from: Optional[str] = None
    """Coverage start date (ISO 8601), present when the requested window ends before the symbol's coverage begins."""

    notice: Optional[str] = None
    """Advisory notice explaining an empty response (e.g. window predates coverage)."""


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

    builder_address: Optional[str] = None
    """Builder address that routed this order. Present only when the order was placed through a builder."""

    builder_fee: Optional[str] = None
    """Builder fee charged on this fill, paid to the builder (in quote currency, typically USDC). Present only when builder_address is set."""

    deployer_fee: Optional[str] = None
    """HIP-3 deployer fee share on this fill (in quote currency). Negative for the maker side (rebate), positive for the taker side. Present only on HIP-3 fills."""

    priority_gas: Optional[float] = None
    """Priority fee burned in HYPE (not USDC) for write priority on the Hyperliquid validator queue. Independent of builder_fee and deployer_fee — paid to the network, not to a builder or deployer. Present only when the order paid for priority."""

    cloid: Optional[str] = None
    """Client order ID."""

    twap_id: Optional[int] = None
    """TWAP execution ID."""


# =============================================================================
# Instrument Types
# =============================================================================


class Instrument(BaseModel):
    """Trading instrument specification (Hyperliquid).

    Accepts either snake_case (``sz_decimals``, ``is_active``) or camelCase
    (``szDecimals``, ``isActive``) keys on the wire. Backend currently emits
    snake_case but the upstream Hyperliquid meta endpoint and the TypeScript
    SDK both use camelCase, so the model accepts both for compatibility.
    """

    name: str
    """Instrument symbol (e.g., BTC)."""

    sz_decimals: int = Field(alias="szDecimals")
    """Size decimal precision."""

    max_leverage: Optional[int] = Field(default=None, alias="maxLeverage")
    """Maximum leverage allowed."""

    only_isolated: Optional[bool] = Field(default=None, alias="onlyIsolated")
    """If true, only isolated margin mode is allowed."""

    instrument_type: Optional[Literal["perp", "spot"]] = Field(
        default=None, alias="instrumentType"
    )
    """Type of instrument."""

    is_active: bool = Field(default=True, alias="isActive")
    """Whether the instrument is currently tradeable."""

    model_config = {"populate_by_name": True}


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


class Hip4SideSpec(BaseModel):
    """Per-side spec inside a Hip4OutcomeAggregate.side_specs list."""

    side: int
    """Side index (0 = Yes, 1 = No)."""

    name: str
    """Side display name (e.g. 'Yes', 'No')."""

    coin: str
    """Per-side coin symbol (e.g. '#0', '#1')."""

    asset_id: int
    """Public asset id: 100_000_000 + 10*outcome_id + side."""

    display_title: Optional[str] = None
    """Human-readable per-side title (e.g. 'BTC above 78,213 on May 4 at 06:00 UTC? — Yes')."""

    slug: Optional[str] = None
    """Per-side URL slug mirroring HL's URL pattern (e.g. 'btc-above-78213-yes-may-04-0600')."""


class Hip4AggregatedOi(BaseModel):
    """Latest both-sides OI snapshot for an outcome (returned on detail only)."""

    side0_open_interest_contracts: Optional[float] = None
    side1_open_interest_contracts: Optional[float] = None
    outcome_display_open_interest_contracts: Optional[float] = None
    paired_set_supply_contracts: Optional[float] = None
    side_supply_parity: Optional[bool] = None
    currency: Optional[str] = None
    """Quote currency (typically 'USDH')."""

    as_of: Optional[datetime] = None
    side0_as_of: Optional[datetime] = None
    side1_as_of: Optional[datetime] = None


class Hip4Outcome(BaseModel):
    """HIP-4 per-side instrument metadata.

    Returned by /v1/hyperliquid/hip4/instruments and /instruments/{symbol}.
    One row per `#N` (per outcome side).
    """

    outcome_id: int
    """Outcome market id."""

    side: int
    """Side index (0 = Yes, 1 = No)."""

    asset_id: int
    """Public asset id: 100_000_000 + 10*outcome_id + side."""

    coin: str
    """Coin symbol (e.g. '#0', '#1')."""

    symbol: str
    """Same as coin, for symbol-style consumers."""

    name: Optional[str] = None
    """Human-readable per-side name."""

    description: Optional[str] = None
    """Pipe-delimited raw description from upstream."""

    side_name: Optional[str] = None
    """Side label ('Yes' or 'No')."""

    recurring_class: Optional[str] = None
    recurring_underlying: Optional[str] = None
    recurring_expiry: Optional[datetime] = None
    recurring_target_px: Optional[float] = None
    recurring_period: Optional[str] = None
    builder_address: Optional[str] = None

    is_settled: Optional[bool] = None
    """True after the outcome resolves."""

    first_seen_at: Optional[datetime] = None
    last_updated_at: Optional[datetime] = None

    display_title: Optional[str] = None
    """Human-readable per-side title."""

    slug: Optional[str] = None
    """Per-side URL slug mirroring HL's pattern."""


class Hip4OutcomeAggregate(BaseModel):
    """HIP-4 per-outcome aggregated metadata.

    Returned by /v1/hyperliquid/hip4/outcomes (list, no aggregated_oi)
    and /outcomes/{outcome_id} (detail, includes aggregated_oi).
    """

    outcome_id: int
    name: Optional[str] = None
    description_raw: Optional[str] = None
    class_: Optional[str] = Field(default=None, alias="class")
    """Outcome class (e.g. 'priceBinary'). Aliased because 'class' is a Python keyword."""

    underlying: Optional[str] = None
    expiry: Optional[datetime] = None
    target_price: Optional[float] = None
    period: Optional[str] = None
    side_specs: list[Hip4SideSpec] = Field(default_factory=list)
    is_settled: Optional[bool] = None
    status: Optional[str] = None
    """Lifecycle status (e.g. 'live', 'settled')."""

    source_seen_at: Optional[datetime] = None
    aggregated_oi: Optional[Hip4AggregatedOi] = None
    """Populated only on the detail endpoint (/outcomes/{outcome_id})."""

    display_title: Optional[str] = None
    """Per-outcome human-readable title (e.g. 'BTC above 78,213 on May 4 at 06:00 UTC?')."""

    slug: Optional[str] = None
    """Per-outcome URL slug (e.g. 'btc-above-78213-may-04-0600')."""

    outcome_pair: Optional[list[str]] = None
    """Paired sibling coins for this outcome (e.g. ['#10', '#11'])."""

    settlement_value: Optional[float] = None
    """Terminal settled value (0.0 or 1.0 for binary outcomes), if settled."""

    settlement_at: Optional[datetime] = None
    """Wallclock time the outcome settled, if settled."""

    model_config = {"populate_by_name": True}


class Hip4OpenInterestRecord(BaseModel):
    """HIP-4 OI record (per side). Mirrors HIP-3 OI plus outcome_id and side.

    Note: `mark_price` is an implied probability in [0, 1], not a USD price.
    Field name mirrors upstream Hyperliquid `markPx`. `oracle_price` is omitted
    for HIP-4 (outcomes have no oracle feed).
    """

    coin: str
    symbol: str
    outcome_id: int
    side: int
    timestamp: datetime
    open_interest: str
    mark_price: Optional[str] = None
    """Implied probability in [0, 1] (NOT USD). Same field name as perps."""

    mid_price: Optional[str] = None


class SpotPair(BaseModel):
    """Hyperliquid spot trading pair metadata.

    Returned by ``/v1/hyperliquid/spot/pairs`` and the per-pair detail endpoint.
    Symbols are dashed canonical form (e.g. ``HYPE-USDC``, ``PURR-USDC``); the
    server resolves dashed to wire format (``PURR/USDC`` or ``@107``) internally.
    Spot has no funding, no open interest, no liquidations, and no candles by
    design (perp-only constructs).

    Backend wire shape includes both ``coin`` and ``symbol`` (same value, the
    dashed canonical form).
    """

    symbol: str
    """Dashed canonical pair symbol (e.g. ``HYPE-USDC``)."""

    coin: Optional[str] = None
    """Same as symbol. Present in some backend responses for cross-resource
    consistency with orderbook / trades payloads."""

    pair_index: Optional[int] = None
    """Hyperliquid spot pair index (wire format ``@<index>``)."""

    name: Optional[str] = None
    """Hyperliquid wire name (e.g. ``PURR/USDC``)."""

    is_canonical: Optional[bool] = None
    """Whether this is the canonical pair for the base token."""

    base_token_id: Optional[int] = None
    """Base token id in the Hyperliquid spot token registry."""

    quote_token_id: Optional[int] = None
    """Quote token id (0 = USDC)."""

    base_token_name: Optional[str] = None
    """Base token name (e.g. ``HYPE``, ``PURR``)."""

    quote_token_name: Optional[str] = None
    """Quote token name (typically ``USDC``)."""

    base_sz_decimals: Optional[int] = None
    """Base token size decimals."""

    base_wei_decimals: Optional[int] = None
    """Base token wei decimals."""

    quote_sz_decimals: Optional[int] = None
    """Quote token size decimals."""

    quote_wei_decimals: Optional[int] = None
    """Quote token wei decimals."""

    base_token_address: Optional[str] = None
    """Base token EVM address."""

    deployer_fee_share: Optional[float] = None
    """Deployer fee share for the pair."""

    first_seen_at: Optional[datetime] = None
    """First time the pair appeared in the metadata table (table rebuilds can
    reset this; do not treat it as the listing date)."""

    last_updated_at: Optional[datetime] = None
    """Last metadata update time."""

    model_config = {"extra": "ignore"}


class SpotTwapStatus(BaseModel):
    """Hyperliquid spot TWAP order status row.

    TWAP (time-weighted average price) orders are sliced into child fills over
    a window. Status records track the running execution of each TWAP.
    """

    coin: str
    """Pair symbol in dashed canonical form (e.g. ``HYPE-USDC``)."""

    timestamp: datetime
    """Status update timestamp (UTC)."""

    user_address: Optional[str] = None
    """User wallet address that placed the TWAP."""

    twap_id: Optional[int] = None
    """TWAP execution id."""

    side: Optional[Literal["A", "B"]] = None
    """Side: ``B`` (buy) or ``A`` (sell)."""

    status: Optional[str] = None
    """Lifecycle status (e.g. ``activated``, ``finished``, ``terminated``)."""

    size: Optional[float] = None
    """Total TWAP order size."""

    executed_size: Optional[float] = None
    """Cumulative executed size."""

    executed_notional: Optional[float] = None
    """Cumulative executed notional."""

    minutes: Optional[int] = None
    """Total TWAP duration in minutes."""

    reduce_only: Optional[bool] = None
    """Whether the TWAP is reduce-only."""

    randomize: Optional[bool] = None
    """Whether child slice timing is randomized."""

    block_number: Optional[int] = None
    """Block number the status was observed at."""

    block_time: Optional[datetime] = None
    """Block time of the status event (UTC)."""

    started_at: Optional[datetime] = None
    """When the TWAP started (UTC)."""

    model_config = {"extra": "ignore"}


class SpotTableFreshness(BaseModel):
    """Per-table freshness lag for a spot pair.

    Returned by ``/v1/hyperliquid/spot/freshness/{symbol}`` for each backing
    table (``spot_orderbook_snapshots``, ``spot_fills``, ``spot_orderbook_l4_diffs``,
    ``spot_orders``, ``spot_twap``). Mirrors the per-data-type shape used by
    :class:`CoinFreshness` but keyed by table name rather than fixed channels.

    The ``tables`` field accepts either fully-typed :class:`DataTypeFreshness`
    objects or raw dicts so the model survives backend shape evolution. Each
    entry typically has ``last_updated`` and ``lag_ms`` keys, both optional.
    """

    coin: Optional[str] = None
    """Pair symbol in dashed canonical form."""

    exchange: Optional[str] = None
    """Exchange name (``hyperliquid_spot``)."""

    measured_at: Optional[datetime] = None
    """When this freshness was measured."""

    tables: dict[str, Any] = Field(default_factory=dict)
    """Per-table freshness lag, keyed by ClickHouse table name. Values are
    typically ``{last_updated, lag_ms}`` dicts but the schema is permissive."""

    model_config = {"extra": "allow"}


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

    side: Literal["A", "B"]
    """Side: 'B' (buy) or 'A' (sell/ask). Mirrors the trade-side convention.
    The backend liquidations endpoint emits 'A' for ask/sell, matching the
    Hyperliquid wire convention used everywhere else in the SDK."""

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
# Liquidation Levels Types (projected forced-liquidation levels)
# =============================================================================


class LiquidationLevelBucket(BaseModel):
    """One price bucket of projected forced-liquidation exposure."""

    price: float
    """Bucket center price."""

    long_notional: float
    """USD notional of long positions projected to liquidate in this bucket."""

    short_notional: float
    """USD notional of short positions projected to liquidate in this bucket."""

    long_count: int
    """Number of long positions in this bucket."""

    short_count: int
    """Number of short positions in this bucket."""


class LiquidationLevels(BaseModel):
    """Projected forced-liquidation levels for one snapshot.

    Computed from clearinghouse positions and margin state, bucketed around
    the snapshot mark price. Snapshots refresh roughly every 45 minutes;
    ``snapshot_ts`` identifies the snapshot served.
    """

    mid_price: float
    """Mark price at the snapshot, center of the requested range."""

    snapshot_ts: str
    """UTC snapshot time the levels reflect."""

    block_number: int
    """Hyperliquid block height the snapshot reflects."""

    total_long: float
    """Total long notional at risk across the whole book."""

    total_short: float
    """Total short notional at risk across the whole book."""

    flagged_notional: float
    """Notional computed approximately or not bucketed (HIP-3 cross-margin
    exposure)."""

    levels: list[LiquidationLevelBucket]
    """Price buckets inside the requested range."""


class LiquidationLevelsHistoryItem(BaseModel):
    """One historical liquidation-levels snapshot.

    ``levels`` is ``None`` when the history was requested with
    ``summary=True``.
    """

    snapshot_ts: str
    block_number: int
    mid_price: float
    total_long: float
    total_short: float
    flagged_notional: float
    levels: Optional[list[LiquidationLevelBucket]] = None


# =============================================================================
# Trigger Levels Types (pending stop-loss / take-profit orders)
# =============================================================================


class TriggerLevelBucket(BaseModel):
    """Aggregated currently open trigger orders at one rounded price bucket."""

    price_bucket: float
    """Rounded trigger price bucket."""

    bid_count: int
    """Number of bid-side trigger orders in the bucket."""

    bid_size: float
    """Bid-side trigger size in the bucket."""

    ask_count: int
    """Number of ask-side trigger orders in the bucket."""

    ask_size: float
    """Ask-side trigger size in the bucket."""


class TriggerLevels(BaseModel):
    """Currently pending stop-loss and take-profit trigger orders.

    Grouped into price buckets near the current mid/mark price. Voluntary
    trigger orders, not projected forced liquidations; use
    :class:`LiquidationLevels` for those.
    """

    mid_price: float
    """Current mid/mark price, center of the requested range."""

    as_of: str
    """UTC RFC3339 server time the pending-trigger state was read."""

    total_bid_size: float
    """Total pending bid size across the returned window."""

    total_ask_size: float
    """Total pending ask size across the returned window."""

    levels: list[TriggerLevelBucket]
    """Price buckets inside the requested range."""


class TriggerLevelsHistoryItem(BaseModel):
    """One historical trigger-levels snapshot (15-minute cadence).

    ``levels`` is ``None`` when the history was requested with
    ``summary=True``.
    """

    snapshot_ts: str
    mid_price: float
    total_bid_size: float
    total_ask_size: float
    levels: Optional[list[TriggerLevelBucket]] = None


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
    "lighter_open_interest", "lighter_funding", "lighter_l3_orderbook",
    "hip3_orderbook", "hip3_trades", "hip3_candles",
    "hip3_open_interest", "hip3_funding", "hip3_liquidations",
    "hip4_orderbook", "hip4_trades", "hip4_open_interest",
    "hip4_l4_diffs", "hip4_l4_orders",
    "l4_diffs", "l4_orders",
    "hip3_l4_diffs", "hip3_l4_orders",
    "spot_orderbook", "spot_trades", "spot_l4_diffs", "spot_l4_orders", "spot_twap",
]
"""Available WebSocket channels.

Notes:
- ticker/all_tickers are real-time only.
- liquidations and hip3_liquidations now stream live (realtime + replay).
  Each item shares the trades wire shape (a fill row with ``is_liquidation: true``).
- open_interest, funding, lighter_open_interest, lighter_funding,
  hip3_open_interest, hip3_funding are historical only (replay/stream).
- l4_diffs, l4_orders: Hyperliquid L4 order-level data (realtime only).
- hip3_l4_diffs, hip3_l4_orders: HIP-3 L4 order-level data (realtime only).
- hip4_orderbook, hip4_trades, hip4_open_interest: HIP-4 outcome markets
  (realtime + replay).
- hip4_l4_diffs, hip4_l4_orders: HIP-4 L4 order-level data (realtime only).
- HIP-4 has no funding / liquidations / candles by design.
- spot_orderbook, spot_trades, spot_twap: Hyperliquid spot (realtime).
- spot_l4_diffs, spot_l4_orders: Hyperliquid spot L4 (realtime only).
- Spot has no funding / open interest / liquidations / candles by design.
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
# WebSocket Bulk Stream Types (Data Catalog Mode)
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
# WebSocket HIP-4 Settlement Event
# =============================================================================


class WsOutcomeSettled(BaseModel):
    """HIP-4 outcome settlement notification.

    Pushed once per ``(outcome_id, side)`` when ``hip4_outcome_metadata.is_settled``
    flips to true. After delivering this message the server proactively
    unsubscribes the client from every ``hip4_*`` subscription on the settled
    coin. Treat the event as a terminal signal for that coin.
    """

    type: Literal["outcome_settled"]
    coin: str
    """Per-side coin symbol, e.g. ``'#55850'``."""

    outcome_id: int
    """Outcome market id."""

    side: int
    """Side index (0 = Yes, 1 = No)."""

    settlement_value: Optional[float] = None
    """Final implied probability for this side (0.0 or 1.0 for binary outcomes)."""

    settlement_at: Optional[datetime] = None
    """When the outcome resolved (UTC)."""


# =============================================================================
# Web3 Authentication Types
# =============================================================================


class SiweChallenge(BaseModel):
    """SIWE challenge message returned by the challenge endpoint."""

    message: str
    """The SIWE message to sign with personal_sign (EIP-191)."""

    nonce: str
    """Single-use nonce (expires after 10 minutes)."""


class Web3SignupResult(BaseModel):
    """Result of creating a free-tier account via wallet signature."""

    api_key: str
    """The generated API key."""

    tier: str
    """Account tier (e.g., 'free')."""

    wallet_address: str
    """The wallet address that owns this key."""


class Web3ApiKey(BaseModel):
    """An API key record returned by the keys endpoint."""

    id: str
    """Unique key ID (UUID)."""

    name: str
    """Key name."""

    key_prefix: str
    """First characters of the key for identification."""

    is_active: bool
    """Whether the key is currently active."""

    last_used_at: Optional[str] = None
    """Last usage timestamp (ISO 8601)."""

    created_at: str
    """Creation timestamp (ISO 8601)."""


class Web3KeysList(BaseModel):
    """List of API keys for a wallet."""

    keys: list[Web3ApiKey]
    """All API keys belonging to this wallet."""

    wallet_address: str
    """The wallet address."""


class Web3RevokeResult(BaseModel):
    """Result of revoking an API key."""

    message: str
    """Confirmation message."""

    wallet_address: str
    """The wallet address that owned the key."""


class Web3PaymentRequired(BaseModel):
    """x402 payment details returned by subscribe (402 response)."""

    amount: str
    """Amount in smallest unit (e.g., '49000000' for $49 USDC)."""

    asset: str
    """Payment asset (e.g., 'USDC')."""

    network: str
    """Blockchain network (e.g., 'base')."""

    pay_to: str
    """Address to send payment to."""

    asset_address: str
    """Token contract address."""


class Web3SubscribeResult(BaseModel):
    """Result of a successful x402 subscription."""

    api_key: str
    """The generated API key."""

    tier: str
    """Subscription tier."""

    expires_at: str
    """Expiration timestamp (ISO 8601)."""

    wallet_address: str
    """The wallet address that owns the subscription."""

    tx_hash: Optional[str] = None
    """On-chain transaction hash."""


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
    """Coverage for supported venue APIs."""


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

    avg_1h_ms: Optional[int] = None
    """1-hour average latency. Omitted until the platform has a real sample
    source for this venue; never fabricated."""

    avg_24h_ms: Optional[int] = None
    """24-hour average latency. Omitted when unavailable."""

    p99_24h_ms: Optional[int] = None
    """24-hour P99 latency."""


class ApiLatency(BaseModel):
    """REST API latency metrics."""

    current_ms: Optional[int] = None
    """Current latency."""

    avg_1h_ms: Optional[int] = None
    """1-hour average latency. Omitted until samples accrue for this venue."""

    avg_24h_ms: Optional[int] = None
    """24-hour average latency. Omitted when unavailable."""


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

    fills: Optional[float] = None
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


# =============================================================================
# Webhook Types
# =============================================================================
#
# Webhook delivery is a paid feature. Free plans hold no endpoints,
# subscriptions, watched wallets, or deliveries, but they keep the two
# preview routes (estimate and dry-run) so a rule can be designed and costed
# before upgrading. See the README for the full per-plan grid.
#
# Every model here allows unknown fields. The webhook surface is the newest
# part of the API and it gains fields faster than the SDK ships; an extra key
# on the wire must never raise in a customer's receiver.


class WebhookEventTypeDeclaration(BaseModel):
    """One entry in the served event-type catalog.

    The catalog is the single source the dashboard, the docs, and this SDK
    render from. Nothing client-side should hardcode an event type, a
    threshold, or an operator: read them from here.
    """

    model_config = {"extra": "allow"}

    type: str
    """Event type identifier, for example 'account.fill' or 'market.liquidation'."""

    live: bool
    """True when the type accepts subscriptions. False means published but not yet available."""

    scope: str
    """'public' (venue-wide), 'addresses' (your watched wallets), or 'user' (your account)."""

    description: str
    """What the event fires on."""

    venues: list[str] = Field(default_factory=list)
    """Venues this type covers, for example ['hyperliquid', 'hip3', 'lighter']."""

    filters: list[str] = Field(default_factory=list)
    """Filter keys the type accepts, for example ['venue', 'symbols', 'addresses']."""

    params: dict[str, Any] = Field(default_factory=dict)
    """Declared parameters, each with its type, bounds or enum, and default."""

    metrics: dict[str, Any] = Field(default_factory=dict)
    """Metrics that conditions can be written against, each with its type and unit."""

    operators: dict[str, Any] = Field(default_factory=dict)
    """Operator vocabulary, grouped by metric type."""

    latency_class: Optional[str] = None
    """Rough delivery latency after the underlying event: 'seconds' or 'minutes'."""

    schema_version: Optional[int] = None
    """Payload schema version for this event type."""

    cost_floor: Optional[float] = None
    """Minimum threshold the type enforces, when it has one."""


class WebhookEndpoint(BaseModel):
    """A registered delivery destination."""

    model_config = {"extra": "allow"}

    id: str
    """Endpoint UUID."""

    url: str
    """HTTPS destination. Redirects are not followed, so point this at the final URL."""

    description: str = ""
    """Your own label for the endpoint."""

    status: str
    """'active', 'disabled', or 'auto_disabled'.

    An endpoint auto-disables after 10 consecutive failures spanning at least
    6 hours. Recover it with ``enable_endpoint()``.
    """

    consecutive_failures: int = 0
    """Failures since the last success. Resets on any 2xx."""

    created_at: datetime
    """When the endpoint was registered (UTC)."""

    secret: Optional[str] = None
    """The signing secret, shown ONCE.

    Populated only by ``create_endpoint()`` and ``rotate_secret()``. Every
    list and get returns None. Store it when you get it: the API will not
    show it again, and without it you cannot verify a delivery.
    """


class WebhookSecret(BaseModel):
    """A newly issued signing secret, returned once by a rotation."""

    model_config = {"extra": "allow"}

    secret: str
    """The new signing secret ('whsec_' followed by 64 hex characters).

    Pass the whole string to :class:`~oxarchive.WebhookVerifier`; the prefix
    is part of the HMAC key.
    """

    note: Optional[str] = None
    """The API's own advisory, which states how long the previous secret stays valid."""


class WebhookSubscription(BaseModel):
    """A rule: which event type goes to which endpoint, under which conditions."""

    model_config = {"extra": "allow"}

    id: str
    """Subscription UUID."""

    endpoint_id: str
    """The endpoint this rule delivers to."""

    event_type: str
    """The subscribed event type."""

    filters: dict[str, Any] = Field(default_factory=dict)
    """The stored, normalised configuration: filters, params, and conditions.

    The API returns it under the name ``filters``; this SDK sends it as
    ``config``. Same object. Declared parameter defaults are filled in
    server-side, so what comes back is more complete than what you sent.
    """

    enabled: bool = True
    """Your own on/off switch for the rule."""

    created_at: datetime
    """When the rule was created (UTC)."""

    @property
    def config(self) -> dict[str, Any]:
        """Alias for :attr:`filters`, matching the SDK's request vocabulary."""
        return self.filters


class WebhookDelivery(BaseModel):
    """One delivery attempt record from the endpoint's delivery log."""

    model_config = {"extra": "allow"}

    id: str
    """Delivery UUID. Pass this to ``redeliver()``."""

    event_id: str
    """Event UUID, sent as the '0xa-event-id' header.

    Stable across retries and across manual redelivery. This is what a
    receiver deduplicates on.
    """

    event_type: str
    """The event type that was delivered."""

    state: str
    """'pending', 'delivered', or 'exhausted'."""

    attempts: int = 0
    """Attempts made so far. The ladder is 5s, 30s, 2m, 10m, 1h, then hourly, capped at 24 hours."""

    last_status_code: Optional[int] = None
    """HTTP status from the most recent attempt. Only 2xx counts as success."""

    last_error: Optional[str] = None
    """Failure detail from the most recent attempt."""

    last_latency_ms: Optional[int] = None
    """Round-trip time of the most recent attempt. The request times out at 10 seconds."""

    next_attempt_at: Optional[datetime] = None
    """When the next attempt is due (UTC)."""

    delivered_at: Optional[datetime] = None
    """When the delivery first succeeded (UTC), if it has."""

    created_at: datetime
    """When the delivery was queued (UTC)."""

    payload: dict[str, Any] = Field(default_factory=dict)
    """The event body as stored.

    Useful for inspection. It is NOT byte-identical to what was signed and
    sent, so never verify a signature against a re-serialised copy of this.
    """


class WebhookTestResult(BaseModel):
    """The queued 'webhook.test' delivery from a test fire."""

    model_config = {"extra": "allow"}

    delivery_id: str
    """UUID of the queued delivery. Watch it in the delivery log."""

    event_id: str
    """Event UUID, which arrives as the '0xa-event-id' header."""


class WebhookRedelivery(BaseModel):
    """The outcome of asking for a past delivery to be sent again."""

    model_config = {"extra": "allow"}

    delivery_id: str
    """UUID of the queued delivery."""

    event_id: Optional[str] = None
    """Event UUID. Unchanged from the original, so receivers dedupe it away
    unless they are meant to reprocess it."""

    event_type: Optional[str] = None
    """The event type being resent."""

    state: Optional[str] = None
    """Delivery state after requeueing."""

    attempts: Optional[int] = None
    """Attempts made so far."""

    next_attempt_at: Optional[datetime] = None
    """When the attempt is due (UTC)."""


class WebhookWatchedAddress(BaseModel):
    """A wallet the account-scoped event types are allowed to fire on."""

    model_config = {"extra": "allow"}

    id: str
    """Watched-address UUID."""

    address: str
    """The wallet, normalised to lowercase 0x form."""

    label: str = ""
    """Your own label, up to 64 characters."""

    created_at: datetime
    """When the wallet was added (UTC)."""


class WebhookWindow(BaseModel):
    """The time range a preview answer vouches for."""

    model_config = {"extra": "allow", "populate_by_name": True}

    from_: str = Field(alias="from")
    """Start of the window (RFC 3339).

    Named ``from_`` because ``from`` is a Python keyword. It moves later than
    you asked when a capped scan could not reach back that far.
    """

    to: str
    """End of the window (RFC 3339)."""


class WebhookOccurrence(BaseModel):
    """One historical event a preview says would have been delivered."""

    model_config = {"extra": "allow"}

    observed_at_estimate: str
    """The occurrence's own timestamp (RFC 3339).

    A real delivery's ``observed_at`` would be this plus the detector's
    ingest lag.
    """

    data: dict[str, Any] = Field(default_factory=dict)
    """The event data, shaped as the delivered payload's ``data`` would be."""


class WebhookDryRun(BaseModel):
    """Which occurrences a rule would have delivered over a recent window.

    Available on every plan, Free included, so a rule can be checked before
    there is anywhere to deliver it.
    """

    model_config = {"extra": "allow"}

    event_type: str
    """The event type that was evaluated."""

    window: WebhookWindow
    """The window the answer vouches for."""

    matched: int = 0
    """Occurrences that matched inside the window, before the page limit."""

    truncated: bool = False
    """True when fewer occurrences are listed than matched, or a scan hit its row cap."""

    occurrences: list[WebhookOccurrence] = Field(default_factory=list)
    """The matches, newest first."""


class WebhookDayCount(BaseModel):
    """One 24-hour bin of an estimate."""

    model_config = {"extra": "allow"}

    date: str
    """The UTC date the bin ends on."""

    count: int
    """Matches in the bin."""


class WebhookLadderRung(BaseModel):
    """The daily rate a rule would have had at a different threshold."""

    model_config = {"extra": "allow"}

    value: float
    """The threshold on the estimate's primary metric."""

    per_day: float
    """Deliveries per day at that threshold, everything else unchanged."""


class WebhookDistribution(BaseModel):
    """Quantiles of an estimate's primary metric over the matched occurrences."""

    model_config = {"extra": "allow"}

    n: int
    """Occurrences the quantiles are computed over."""

    p50: float
    """Median."""

    p90: float
    """90th percentile."""

    p99: float
    """99th percentile."""

    max: float
    """Largest observed value."""


class WebhookEstimateBasis(BaseModel):
    """How an estimate was computed."""

    model_config = {"extra": "allow"}

    mode: str
    """Which evaluation path answered, for example an exact scan or a replay."""

    note: Optional[str] = None
    """Any caveat attached to the answer."""


class WebhookEstimate(BaseModel):
    """How often a rule would have fired over a historical window.

    Available on every plan, Free included. Use it to size a rule before
    paying for the deliveries: ``per_day_p50`` against the plan's
    deliveries-per-day allowance is the number that matters.
    """

    model_config = {"extra": "allow"}

    event_type: str
    """The event type that was evaluated."""

    window: WebhookWindow
    """The window the answer vouches for."""

    days: int
    """Days covered. Shorter than requested when the type caps its own window."""

    total: int
    """Matches across the whole window."""

    per_day: list[WebhookDayCount] = Field(default_factory=list)
    """One entry per day, oldest first, zero-filled."""

    per_day_p50: float = 0.0
    """Median deliveries per day."""

    per_day_max: int = 0
    """Busiest single day."""

    primary_metric: Optional[str] = None
    """The metric the ladder and the distribution describe."""

    ladder: list[WebhookLadderRung] = Field(default_factory=list)
    """Ascending what-if thresholds and the daily rate each would have produced."""

    distribution: Optional[WebhookDistribution] = None
    """Quantiles of the primary metric, when the type has one."""

    sample: list[WebhookOccurrence] = Field(default_factory=list)
    """A sample of matches, newest first."""

    basis: Optional[WebhookEstimateBasis] = None
    """How the answer was computed."""
