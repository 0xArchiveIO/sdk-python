"""Type definitions for the 0xarchive SDK."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Generic, Literal, Optional, TypeVar, Union

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, field_validator, model_validator


# =============================================================================
# Base Types
# =============================================================================

T = TypeVar("T")


# =============================================================================
# API Contract Types
# =============================================================================

Venue = Literal["hyperliquid", "hip3", "hip4", "spot", "lighter", "rh-lighter"]
"""A venue as the API names it in ``meta.venue``, ``/v1/capabilities`` and
``/v1/symbols``: Hyperliquid core, HIP-3, HIP-4, Hyperliquid spot, Lighter and
Lighter on Robinhood Chain (``"rh-lighter"``)."""

VENUES: tuple[str, ...] = ("hyperliquid", "hip3", "hip4", "spot", "lighter", "rh-lighter")
"""Every :data:`Venue`, in the API's order."""

ErrorCode = Literal[
    "invalid_parameter",
    "invalid_symbol",
    "invalid_interval",
    "invalid_cursor",
    "invalid_time_range",
    "range_before_coverage",
    "historical_range_exceeded",
    "historical_depth_exceeded",
    "unsupported_for_venue",
    "route_not_found",
    "not_found",
    "unauthorized",
    "forbidden",
    "insufficient_credits",
    "rate_limited",
    "conflict",
    "upstream_unavailable",
    "internal_error",
    "endpoint_unsupported",
    "slow_consumer",
    "positions_unavailable",
    "api_key_limit_reached",
    "oauth_not_permitted",
]
"""The stable ``error_code`` values of the API's public error set.

- ``invalid_parameter``: a parameter failed to parse or validate (see
  ``param`` and ``valid_values`` on the error).
- ``invalid_symbol``: the symbol is not listed on this venue.
- ``invalid_interval``: the interval is not one the route accepts.
- ``invalid_cursor``: the cursor is malformed, stale or was issued for other
  filters.
- ``invalid_time_range``: ``start`` is after ``end``, or a time could not be
  parsed.
- ``range_before_coverage``: the whole range ends before the dataset's first
  served instant.
- ``historical_range_exceeded``: the span is longer than the plan allows per
  request.
- ``historical_depth_exceeded``: the request reaches further back than the
  plan's history window.
- ``unsupported_for_venue``: the datatype, or the WebSocket mode (live,
  replay, ``replay.seek``), is not offered on this venue; the message names
  where it is.
- ``route_not_found``: no route matches the path.
- ``not_found``: the route exists but the resource id does not.
- ``unauthorized``, ``forbidden``, ``insufficient_credits``, ``rate_limited``,
  ``conflict``: authentication, plan, credit, rate and state refusals.
- ``upstream_unavailable``: a dependency is unavailable; retry later.
- ``internal_error``: an unexpected server error.
- ``endpoint_unsupported`` (WebSocket only): this endpoint does not serve the
  channel or operation; the message names the endpoint that does.
- ``slow_consumer`` (WebSocket only): the connection fell behind a stream and
  messages were dropped; re-subscribe or restart the replay to resync.
- ``positions_unavailable``, ``api_key_limit_reached``,
  ``oauth_not_permitted``: route-specific codes.

Branch on these strings rather than on messages. A server can add a code
before an SDK release names it, so ``error_code`` attributes are typed as
``str``."""

ERROR_CODES: tuple[str, ...] = (
    "invalid_parameter",
    "invalid_symbol",
    "invalid_interval",
    "invalid_cursor",
    "invalid_time_range",
    "range_before_coverage",
    "historical_range_exceeded",
    "historical_depth_exceeded",
    "unsupported_for_venue",
    "route_not_found",
    "not_found",
    "unauthorized",
    "forbidden",
    "insufficient_credits",
    "rate_limited",
    "conflict",
    "upstream_unavailable",
    "internal_error",
    "endpoint_unsupported",
    "slow_consumer",
    "positions_unavailable",
    "api_key_limit_reached",
    "oauth_not_permitted",
)
"""Every :data:`ErrorCode`, in the API's order."""

WEBSOCKET_ERROR_CODES: frozenset[str] = frozenset({"endpoint_unsupported", "slow_consumer"})
"""Codes only WebSocket error messages carry; REST never answers them."""


def _ms_from_legacy(values: Any, field: str) -> Any:
    """Fill ``<field>_ms`` from an integer ``<field>`` (the pre-2026-10 shape).

    With the ``0xArchive-Version`` the SDK sends, the API returns the time as an
    RFC 3339 string and the integer as ``<field>_ms``. A body in the older shape
    carries Unix milliseconds in ``<field>`` itself; this keeps ``<field>_ms``
    set in both cases.
    """
    if isinstance(values, dict):
        value = values.get(field)
        if (
            values.get(f"{field}_ms") is None
            and isinstance(value, (int, float))
            and not isinstance(value, bool)
        ):
            values = {**values, f"{field}_ms": int(value)}
    return values


class _ApiRecord(BaseModel):
    """A record a method returns on its own, with the response's ``meta`` attached."""

    _response_meta: Optional["ResponseMeta"] = PrivateAttr(default=None)

    @property
    def response_meta(self) -> Optional["ResponseMeta"]:
        """The ``meta`` of the response this record came in: ``request_id``,
        and on per-symbol routes ``symbol`` (the canonical public symbol) and
        ``venue``. ``None`` on a record that was not returned on its own (for
        example a row inside a list)."""
        return self._response_meta


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


class OrderBook(_ApiRecord):
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
    """Fee paid on this fill in ``fee_token``, including any builder fee; negative
    is a rebate. ``"0"`` is a recorded zero fee. ``None`` when the source did not
    record fees, for example fills from 2025-03-22 to 2025-05-25."""

    fee_token: Optional[str] = None
    """Fee denomination (e.g., USDC). Present exactly when ``fee`` and
    ``closed_pnl`` were recorded."""

    closed_pnl: Optional[str] = None
    """Realized PnL on this fill. ``"0"`` when the fill opened or added to a
    position. ``None`` when the source did not record it (same cases as ``fee``)."""

    direction: Optional[str] = None
    """Position direction (e.g., 'Open Long', 'Close Short', 'Long > Short')."""

    start_position: Optional[str] = None
    """Position size (spot: balance) before this fill; negative is short. ``"0"``
    means flat. ``None`` when the source did not record it."""

    user_address: Optional[str] = None
    """User's wallet address (for fill-level data)."""

    account_index: Optional[str] = None
    """Lighter account index of this fill's owner, as a string. Present on Lighter
    fills (REST trades and live ``lighter_trades`` legs); ``None`` for Hyperliquid."""

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
    """Priority fee burned in HYPE (not USDC) for write priority on the Hyperliquid validator queue. Independent of builder_fee and deployer_fee: paid to the network, not to a builder or deployer. Present only when the order paid for priority."""

    cloid: Optional[str] = None
    """Client order ID."""

    twap_id: Optional[int] = None
    """TWAP execution ID."""


# =============================================================================
# Instrument Types
# =============================================================================


class Instrument(_ApiRecord):
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


class Hip3Instrument(_ApiRecord):
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
    """Human-readable per-side title, as the API returns it: the outcome's question followed by the side name."""

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


class Hip4Outcome(_ApiRecord):
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


class Hip4OutcomeAggregate(_ApiRecord):
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


class Hip4OpenInterestRecord(_ApiRecord):
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


class SpotPair(_ApiRecord):
    """Hyperliquid spot trading pair metadata.

    Returned by ``/v1/hyperliquid/spot/pairs`` and the per-pair detail endpoint.
    Symbols are dashed canonical form (e.g. ``HYPE-USDC``, ``PURR-USDC``); the
    server resolves dashed to wire format (``PURR/USDC`` or ``@107``) internally.
    Spot has no funding, no open interest, or liquidations. Candle history is
    served from ``2025-03-22T10:50:22Z`` with 1,000-row pages.

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


class SpotTableFreshness(_ApiRecord):
    """Freshness of each dataset for a spot pair, from ``client.spot.get_freshness()``.

    One entry per dataset spot serves: ``orderbook``, ``trades``,
    ``l4_diffs``, ``l4_checkpoints``, ``orders`` and ``twap``. Each carries
    ``last_updated`` and ``lag_ms``, both optional. Spot has no funding, open
    interest or liquidations. Unknown fields are kept.
    """

    symbol: Optional[str] = None
    """Pair symbol in dashed canonical form (for example ``HYPE-USDC``)."""

    coin: Optional[str] = None
    """Pair symbol in dashed canonical form."""

    exchange: Optional[str] = None
    """Venue family (``spot``)."""

    measured_at: Optional[datetime] = None
    """When this freshness was measured."""

    orderbook: Optional[DataTypeFreshness] = None
    """L2 order book snapshots."""

    trades: Optional[DataTypeFreshness] = None
    """Trades."""

    l4_diffs: Optional[DataTypeFreshness] = None
    """L4 order book diffs."""

    l4_checkpoints: Optional[DataTypeFreshness] = None
    """L4 order book checkpoints."""

    orders: Optional[DataTypeFreshness] = None
    """L4 order lifecycle events."""

    twap: Optional[DataTypeFreshness] = None
    """TWAP statuses."""

    model_config = {"extra": "allow"}

    @property
    def tables(self) -> dict[str, DataTypeFreshness]:
        """The datasets present in the response, keyed by name.

        Before 1.12.0 this was a field that the API never filled, so it was
        always empty; it now lists the datasets above.
        """
        names = ("orderbook", "trades", "l4_diffs", "l4_checkpoints", "orders", "twap")
        return {name: value for name in names if (value := getattr(self, name)) is not None}


class LighterInstrument(_ApiRecord):
    """Trading instrument specification (Lighter).

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
# HIP-3 Market Breadth Types
# =============================================================================


class BreadthNamespaceCounts(BaseModel):
    """Per-builder-namespace counts for a HIP-3 breadth snapshot."""

    eligible: dict[str, int]
    """Eligible instruments by builder namespace."""

    above: dict[str, int]
    """Eligible instruments trading above session VWAP by namespace."""

    at: dict[str, int]
    """Eligible instruments exactly at session VWAP by namespace."""

    below: dict[str, int]
    """Eligible instruments trading below session VWAP by namespace."""


class BreadthCounts(BaseModel):
    """Auditable aggregate counts for a HIP-3 breadth snapshot."""

    candidates: int
    """Full HIP-3 candidate universe at calculation time."""

    eligible: int
    """Candidates with a usable completed candle and session volume."""

    above: int
    """Eligible instruments above session VWAP."""

    at: int
    """Eligible instruments whose close equals session VWAP."""

    below: int
    """Eligible instruments below session VWAP."""

    excluded_no_session_volume: int
    """Candidates excluded because they have no session volume."""

    excluded_stale_price: int
    """Candidates excluded because their completed candle is over five minutes old."""


class BreadthSnapshot(_ApiRecord):
    """Validated HIP-3 percent-above-session-VWAP market snapshot.

    Snapshots use the current UTC session and the close of the most recently
    completed one-minute candle. ``value_pct`` is unavailable (``None``), not
    zero, when no instrument is eligible. The API stores one-minute snapshots
    beginning on 2026-08-28 and downsamples history with the last snapshot in
    each requested interval bucket.
    """

    session_date: date
    """UTC calendar date for the session."""

    calculated_at: datetime
    """Job timestamp; the newest included candle closed at this minute."""

    value_pct: Optional[float]
    """100 * above / eligible, or ``None`` when eligible is zero."""

    coverage_ratio: float
    """Eligible divided by candidates, from 0 to 1."""

    counts: BreadthCounts
    """Aggregate counts whose invariants are enforced by the producer."""

    namespaces: BreadthNamespaceCounts
    """Per-builder-namespace breakdowns for the aggregate counts."""


# =============================================================================
# Funding Types
# =============================================================================


class FundingRate(_ApiRecord):
    """Funding rate record."""

    coin: str
    """Trading pair symbol."""

    timestamp: datetime
    """Funding timestamp (UTC)."""

    funding_rate: str
    """Fractional, non-annualized funding rate (e.g., 0.0001 = 0.01%).

    Lighter uses this fractional unit as a breaking normalization from its
    former percent representation; do not apply a second percent conversion.
    """

    premium: Optional[str] = None
    """Premium component of funding rate."""


# =============================================================================
# Open Interest Types
# =============================================================================


class OpenInterest(_ApiRecord):
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


class LiquidationLevels(_ApiRecord):
    """Projected forced-liquidation levels for one snapshot.

    Computed from clearinghouse positions and margin state, bucketed around
    the snapshot mark price. Snapshots refresh approximately every five minutes;
    ``snapshot_ts`` identifies the snapshot served.
    """

    mid_price: float
    """Mark price at the snapshot, center of the requested range."""

    snapshot_ts: str
    """UTC snapshot time the levels reflect, as an RFC 3339 string."""

    snapshot_ts_ms: Optional[int] = None
    """``snapshot_ts`` in Unix milliseconds."""

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
    """UTC snapshot time, as an RFC 3339 string."""

    snapshot_ts_ms: Optional[int] = None
    """``snapshot_ts`` in Unix milliseconds."""

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


class TriggerLevels(_ApiRecord):
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
    """UTC snapshot time, as an RFC 3339 string."""

    snapshot_ts_ms: Optional[int] = None
    """``snapshot_ts`` in Unix milliseconds."""

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


class CoinFreshness(_ApiRecord):
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

    funding: Optional[DataTypeFreshness] = None
    """Funding rate data freshness. ``None`` on HIP-4, which has no funding."""

    open_interest: DataTypeFreshness
    """Open interest data freshness."""

    liquidations: Optional[DataTypeFreshness] = None
    """Liquidations data freshness."""


# =============================================================================
# Market Summary Types
# =============================================================================


class CoinSummary(_ApiRecord):
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
    "rh_lighter_orderbook", "rh_lighter_trades", "rh_lighter_candles",
    "rh_lighter_open_interest", "rh_lighter_funding",
    "hip3_orderbook", "hip3_trades", "hip3_candles",
    "hip3_open_interest", "hip3_funding", "hip3_liquidations",
    "hip4_orderbook", "hip4_trades", "hip4_open_interest",
    "hip4_l4_diffs", "hip4_l4_orders",
    "l4_diffs", "l4_orders",
    "hip3_l4_diffs", "hip3_l4_orders",
    "orderbook_full", "hip3_orderbook_full",
    "spot_orderbook", "spot_trades", "spot_l4_diffs", "spot_l4_orders", "spot_twap",
]
"""Available WebSocket channels.

Which channels stream live and which replay is listed per channel in
``oxarchive.websocket.WS_CHANNELS``, which mirrors ``GET /v1/capabilities``
(``client.capabilities()``). In short:

- Live and replay: ``orderbook``, ``trades``, ``liquidations``,
  ``open_interest``, ``funding`` and their ``hip3_*`` counterparts;
  ``hip4_trades``; the four live ``lighter_*`` and ``rh_lighter_*`` channels;
  every L4 channel (``l4_diffs``, ``l4_orders`` and the ``hip3_``, ``hip4_``
  and ``spot_`` versions); and the full-depth L2 channels ``orderbook_full``
  and ``hip3_orderbook_full``.
- Replay only: ``candles``, ``hip3_candles``, ``hip4_orderbook``,
  ``hip4_open_interest``, ``lighter_candles``, ``lighter_l3_orderbook`` and
  ``rh_lighter_candles``.
- Live only: ``ticker``, ``all_tickers``, ``spot_orderbook`` and
  ``spot_trades``.
- Neither: ``spot_twap``. Spot TWAP statuses are served over REST only
  (``client.spot.twap``); subscribing raises ``ValueError``.

L4 and full-depth replay is bulk: it is single-channel only, ``speed`` is
ignored and ``replay.seek`` is refused. It opens with one ``l4_snapshot`` from
the nearest checkpoint at or before ``start``, followed by ordered
``l4_batch`` messages. Full-depth replay batches carry changed price levels,
exactly like the live channel.

Liquidation items share the trades wire shape (a fill row with
``is_liquidation: true``). Lighter and Robinhood Chain live and replay
messages share one shape per channel (see :class:`LighterLiveTrade` and
:class:`LighterMarketContext`). HIP-4 has no funding or liquidation channels,
and spot has no funding, open interest or liquidation channels.
"""

WsConnectionState = Literal["connecting", "connected", "disconnected", "reconnecting"]
"""WebSocket connection state."""


class WsSubscribed(BaseModel):
    """Subscription confirmed from server."""

    type: Literal["subscribed"]
    channel: WsChannel
    coin: Optional[str] = None
    symbol: Optional[str] = None
    """Symbol as the server echoes it (Lighter symbols are echoed uppercase)."""
    version: Optional[str] = None
    """The API version the connection selected (``2026-10-01`` with this SDK)."""


class WsUnsubscribed(BaseModel):
    """Unsubscription confirmed from server."""

    type: Literal["unsubscribed"]
    channel: WsChannel
    coin: Optional[str] = None
    symbol: Optional[str] = None
    """Symbol as the server echoes it."""


class WsPong(BaseModel):
    """Pong response from server."""

    type: Literal["pong"]


class WsError(BaseModel):
    """Error from server.

    ``error_code`` is the stable code to branch on (see :data:`ErrorCode`),
    for example ``"invalid_parameter"``, ``"unsupported_for_venue"`` (the
    channel does not offer that mode), ``"slow_consumer"`` (the connection
    fell behind and messages were dropped: re-subscribe or restart the replay
    to resync) or ``"endpoint_unsupported"`` (this endpoint does not serve the
    channel; the message names the one that does).
    """

    model_config = ConfigDict(extra="allow")

    type: Literal["error"]
    message: str
    error_code: Optional[str] = None
    """Stable machine-readable code; ``None`` only from a server that predates it."""


class WsData(BaseModel):
    """Real-time data message from server.

    Note: The `data` field can be either a dict (for orderbook) or a list (for trades).
    - Orderbook: dict with 'levels', 'time', etc.
    - Trades: list of trade objects with 'coin', 'side', 'px', 'sz', etc.
    - lighter_open_interest / lighter_funding (and the rh_lighter_* equivalents):
      dict with 'coin' and 'ctx' (see :class:`LighterMarketContextUpdate`).
    """

    type: Literal["data"]
    channel: WsChannel
    coin: str
    symbol: Optional[str] = None
    """Symbol as the server echoes it."""
    data: Union[dict[str, Any], list[dict[str, Any]]]


class WsL4Snapshot(BaseModel):
    """Initial L4 (or full-depth L2) book state for a live stream or a replay."""

    type: Literal["l4_snapshot"]
    channel: WsChannel
    coin: str
    symbol: str
    """Canonical wire symbol for the L4 stream."""

    last_block_number: int
    """Highest block applied to this snapshot."""

    timestamp: int
    """Snapshot timestamp in Unix milliseconds."""

    data: dict[str, Any]
    """Full L4 book state."""


class WsL4Batch(BaseModel):
    """Ordered L4 diff/order events following an ``l4_snapshot``."""

    type: Literal["l4_batch"]
    channel: WsChannel
    coin: str
    symbol: str
    """Canonical wire symbol for the L4 stream."""

    data: list[dict[str, Any]]
    """Events in server order; each event carries its own block/sequence data."""


# =============================================================================
# WebSocket Live Lighter Payload Types
# =============================================================================
#
# Live Lighter channels use the same ``data`` envelope as Hyperliquid live data.
# ``lighter_orderbook`` books share the Hyperliquid live book shape
# (``{coin, time, levels: [bids, asks]}``) and decode to :class:`OrderBook`.
# Trades and market context carry Lighter-specific fields and are modelled here.
# Replay of the same channels uses the same shapes.


class LighterLiveTrade(BaseModel):
    """One leg of a live ``lighter_trades`` trade, as sent in ``WsData.data``.

    Each trade arrives as two legs, one per side, that share ``tid``. Count
    trades by distinct ``tid``, not by list length, and compute volume from
    ``sz`` over one leg per ``tid``. Live legs are preliminary: the finalized
    record, with fields the live stream does not carry (such as fees), is served
    by ``client.lighter.trades.list()``.
    """

    coin: str
    """Market symbol."""

    side: Literal["A", "B"]
    """``'A'`` for the ask side, ``'B'`` for the bid side."""

    px: str
    """Price as a decimal string, exactly as Lighter publishes it."""

    sz: str
    """Size as a decimal string, exactly as Lighter publishes it."""

    time: int
    """Trade time in Unix milliseconds."""

    hash: Optional[str] = None
    """Lighter transaction hash."""

    tid: int
    """Trade id, shared by both legs of the trade."""

    oid: Optional[int] = None
    """This side's order id."""

    crossed: bool
    """``True`` for the taker leg, ``False`` for the maker leg."""

    dir: Optional[str] = None
    """Always ``None`` in live messages; Lighter's live stream does not carry it."""

    fee: Optional[str] = None
    """Always ``None`` in live messages; Lighter's live stream does not carry it."""

    fee_token: Optional[str] = None
    """Always ``None`` in live messages; Lighter's live stream does not carry it."""

    closed_pnl: Optional[str] = None
    """Always ``None`` in live messages; Lighter's live stream does not carry it."""

    start_position: Optional[str] = None
    """This account's signed position before the trade."""

    users: list[str] = Field(default_factory=list)
    """``[account_index]``: this side's Lighter account index as a string."""

    @property
    def account_index(self) -> Optional[str]:
        """This side's Lighter account index, or ``None`` when absent."""
        return self.users[0] if self.users else None


class LighterMarketContext(BaseModel):
    """Market context from a live ``lighter_open_interest`` or ``lighter_funding`` message.

    Both channels deliver the same message, about once per second per market as
    Lighter publishes it. Attributes use the SDK's snake_case names; the wire
    keys are Hyperliquid-style camelCase (``openInterest``, ``markPx``, ...) and
    are accepted as aliases. Values are decimal strings, and a field is ``None``
    when Lighter has not reported it.
    """

    model_config = {"populate_by_name": True}

    open_interest: Optional[str] = Field(default=None, alias="openInterest")
    """Lighter's reported open interest (wire ``openInterest``). Same value as
    ``open_interest`` from ``client.lighter.open_interest.current()``."""

    funding_rate: Optional[str] = Field(default=None, alias="funding")
    """Current funding rate as a fraction (wire ``funding``). Lighter publishes
    percent; this value is already divided by 100, matching REST ``funding_rate``."""

    premium: Optional[str] = None
    """Premium as a fraction."""

    mark_price: Optional[str] = Field(default=None, alias="markPx")
    """Mark price (wire ``markPx``)."""

    oracle_price: Optional[str] = Field(default=None, alias="oraclePx")
    """Lighter's index price (wire ``oraclePx``)."""

    mid_price: Optional[str] = Field(default=None, alias="midPx")
    """Mid price (wire ``midPx``)."""

    day_ntl_volume: Optional[str] = Field(default=None, alias="dayNtlVlm")
    """24-hour quote volume (wire ``dayNtlVlm``)."""

    day_base_volume: Optional[str] = Field(default=None, alias="dayBaseVlm")
    """24-hour base volume (wire ``dayBaseVlm``)."""

    prev_day_price: Optional[str] = Field(default=None, alias="prevDayPx")
    """Price 24 hours ago (wire ``prevDayPx``), derived from the last trade price
    and Lighter's 24-hour percent change."""

    impact_prices: Optional[list[str]] = Field(default=None, alias="impactPxs")
    """Always ``None`` (wire ``impactPxs``); Lighter has no impact prices."""


class LighterMarketContextUpdate(BaseModel):
    """Payload of a live ``lighter_open_interest`` or ``lighter_funding`` message."""

    coin: str
    """Market symbol."""

    ctx: LighterMarketContext
    """Market context values."""


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
    """Playback speed multiplier. Echoed but not applied on the bulk L4 and
    full-depth replays."""
    symbol: Optional[str] = None
    """Symbol as the server echoes it."""
    version: Optional[str] = None
    """The API version the connection selected (``2026-10-01`` with this SDK)."""


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
    """Historical data point (replay mode).

    ``data`` has the live shape of the channel. On ``lighter_trades`` and
    ``rh_lighter_trades`` it is a list with one trade leg (see
    :class:`LighterLiveTrade`); elsewhere it is an object.
    """

    type: Literal["historical_data"]
    channel: WsChannel
    coin: str
    timestamp: int
    data: Union[dict[str, Any], list[dict[str, Any]]]


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
    data: Union[dict[str, Any], list[dict[str, Any]]]
    """Initial state data for this channel, in the channel's live shape (a
    list of trade legs on the Lighter trade channels)."""


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

    This message type is sent when using granularity='tick' for Lighter
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
# WebSocket Bulk Stream Types (deprecated)
#
# The server has discontinued WebSocket bulk streaming and no longer sends
# these messages. The models stay exported for backward compatibility. For
# large dataset downloads, use the S3 Parquet bulk export at
# https://0xarchive.io/data.
# =============================================================================


class WsStreamStarted(BaseModel):
    """Stream started response.

    .. deprecated:: 1.11.0
        The server has discontinued bulk streaming and no longer sends this
        message. For large dataset downloads, use the S3 Parquet bulk export
        at https://0xarchive.io/data.

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
    """Stream progress response.

    .. deprecated:: 1.11.0
        The server has discontinued bulk streaming and no longer sends this
        message.
    """

    type: Literal["stream_progress"]
    snapshots_sent: int


class TimestampedRecord(BaseModel):
    """A record with timestamp for batched data.

    .. deprecated:: 1.11.0
        Only used by :class:`WsHistoricalBatch`, which the server no longer
        sends because it has discontinued bulk streaming.
    """

    timestamp: int
    data: dict[str, Any]


class WsHistoricalBatch(BaseModel):
    """Batch of historical data (bulk streaming).

    .. deprecated:: 1.11.0
        The server has discontinued bulk streaming and no longer sends this
        message. For large dataset downloads, use the S3 Parquet bulk export
        at https://0xarchive.io/data.
    """

    type: Literal["historical_batch"]
    channel: WsChannel
    coin: str
    data: list[TimestampedRecord]


class WsStreamCompleted(BaseModel):
    """Stream completed response.

    .. deprecated:: 1.11.0
        The server has discontinued bulk streaming and no longer sends this
        message.

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
    """Stream stopped response.

    .. deprecated:: 1.11.0
        The server has discontinued bulk streaming and no longer sends this
        message.
    """

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


def _code_for_status(status: int) -> Optional[str]:
    """The ``error_code`` for an error body that carries none, from its HTTP status.

    Mirrors the API's own fallback, so a proxy error page (a 502 with an HTML
    body, say) still gets a code to branch on.
    """
    if status < 400:
        return None
    if status == 401:
        return "unauthorized"
    if status == 402:
        return "insufficient_credits"
    if status == 403:
        return "forbidden"
    if status in (404, 410):
        return "not_found"
    if status == 405:
        return "route_not_found"
    if status == 409:
        return "conflict"
    if status == 429:
        return "rate_limited"
    if 502 <= status <= 504:
        return "upstream_unavailable"
    if status >= 500:
        return "internal_error"
    return "invalid_parameter"


class OxArchiveError(Exception):
    """An error from the API, or a request the SDK refused before sending.

    Attributes:
        message: The error message.
        code: The HTTP status (``0`` for a network error). Also available as
            :attr:`status`.
        request_id: The API's request id, when the response carried one.
        error_code: The stable, machine-readable code (see
            :data:`ErrorCode`), for example ``"invalid_parameter"`` or
            ``"unsupported_for_venue"``. Branch on it rather than on
            ``message``. ``None`` for network errors. When an error body
            carries no code (a proxy error page, for example), it is derived
            from the HTTP status the way the API derives it.
        param: The parameter that was refused, when the API names one.
        valid_values: The values that parameter accepts, when the API lists
            them.
        details: The whole error body as the API sent it, including any
            route-specific fields (``available_on`` on
            ``unsupported_for_venue``, for example). Empty when there was no
            JSON body.
    """

    def __init__(
        self,
        message: str,
        code: int,
        request_id: Optional[str] = None,
        *,
        error_code: Optional[str] = None,
        param: Optional[str] = None,
        valid_values: Optional[list[Any]] = None,
        details: Optional[dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.request_id = request_id
        self.error_code = error_code
        self.param = param
        self.valid_values = valid_values
        self.details: dict[str, Any] = dict(details or {})

    @property
    def status(self) -> int:
        """The HTTP status (``0`` for a network error); the same value as ``code``."""
        return self.code

    @classmethod
    def from_response(cls, status: int, body: Any) -> "OxArchiveError":
        """Build the error for a non-2xx response from its status and JSON body."""
        details = body if isinstance(body, dict) else {}
        message = details.get("error") or details.get("message")
        if not isinstance(message, str) or not message:
            message = f"Request failed with status {status}"
        error_code = details.get("error_code")
        if not isinstance(error_code, str) or not error_code:
            error_code = _code_for_status(status)
        valid_values = details.get("valid_values")
        param = details.get("param")
        request_id = details.get("request_id")
        return cls(
            message,
            status,
            request_id if isinstance(request_id, str) else None,
            error_code=error_code,
            param=param if isinstance(param, str) else None,
            valid_values=valid_values if isinstance(valid_values, list) else None,
            details=details,
        )

    def __str__(self) -> str:
        context = []
        if self.error_code:
            context.append(f"error_code: {self.error_code}")
        if self.request_id:
            context.append(f"request_id: {self.request_id}")
        if context:
            return f"[{self.code}] {self.message} ({', '.join(context)})"
        return f"[{self.code}] {self.message}"


# =============================================================================
# Lighter Liquidation Types (Lighter mainnet and Lighter on Robinhood Chain)
# =============================================================================


class LighterLiquidation(BaseModel):
    """One Lighter liquidation event.

    Returned by ``client.lighter.liquidations.history()`` and
    ``client.rh_lighter.liquidations.history()``. Lighter liquidations are the
    liquidation trades of the venue's trade stream. The row keeps both sides'
    raw account fields (``ask_account``, ``bid_account``, ``is_maker_ask`` and
    the ``*_position_sign_changed`` flags) rather than a single liquidated
    account, because the trade payload does not always say which side was
    liquidated. Prices and sizes are in market units; the integer margin and
    fee fields are in the venue's raw integer units.
    """

    symbol: str
    """Market symbol."""

    timestamp: datetime
    """Trade time (UTC)."""

    timestamp_ms: Optional[int] = None
    """Trade time in Unix milliseconds."""

    transaction_time_us: Optional[int] = None
    """Transaction time in microseconds (orders events within a block)."""

    trade_id: int
    """Lighter trade id."""

    liquidation_type: Optional[str] = None
    """Liquidation type as reported by Lighter."""

    price: float
    """Execution price."""

    size: float
    """Execution size in base units."""

    usd_amount: Optional[float] = None
    """Notional in the quote asset (USDC on mainnet, USDG on Robinhood Chain)."""

    ask_account: Optional[str] = None
    """Account index of the ask side, as a string."""

    bid_account: Optional[str] = None
    """Account index of the bid side, as a string."""

    ask_order_id: Optional[int] = None
    """Order id of the ask side."""

    bid_order_id: Optional[int] = None
    """Order id of the bid side."""

    is_maker_ask: Optional[bool] = None
    """``True`` when the ask side was the maker."""

    taker_position_size_before: Optional[float] = None
    """Taker's signed position before the trade (positive long, negative short)."""

    maker_position_size_before: Optional[float] = None
    """Maker's signed position before the trade."""

    taker_entry_quote_before: Optional[float] = None
    """Taker's entry quote before the trade."""

    maker_entry_quote_before: Optional[float] = None
    """Maker's entry quote before the trade."""

    taker_initial_margin_fraction_before: Optional[int] = None
    """Taker's initial margin fraction before the trade (raw integer units)."""

    maker_initial_margin_fraction_before: Optional[int] = None
    """Maker's initial margin fraction before the trade (raw integer units)."""

    taker_allocated_margin_usdc_before: Optional[int] = None
    """Taker's allocated margin before the trade (raw integer units)."""

    taker_allocated_margin_usdc_after: Optional[int] = None
    """Taker's allocated margin after the trade (raw integer units)."""

    maker_allocated_margin_usdc_before: Optional[int] = None
    """Maker's allocated margin before the trade (raw integer units)."""

    maker_allocated_margin_usdc_after: Optional[int] = None
    """Maker's allocated margin after the trade (raw integer units)."""

    taker_fee: Optional[int] = None
    """Taker fee (raw integer units)."""

    maker_fee: Optional[int] = None
    """Maker fee (raw integer units)."""

    taker_position_sign_changed: Optional[bool] = None
    """``True`` when the trade flipped the taker's position sign."""

    maker_position_sign_changed: Optional[bool] = None
    """``True`` when the trade flipped the maker's position sign."""

    block_height: Optional[int] = None
    """Block height of the trade."""

    tx_hash: Optional[str] = None
    """Transaction hash."""

    raw_json: Optional[str] = None
    """The trade object exactly as captured, as a JSON string. Empty for rows
    backfilled from the venue's finalized export (``source == "bucket"``)."""

    source: Optional[str] = None
    """Where the row came from. ``"ws"`` marks rows captured live, which keep
    the venue's raw JSON in ``raw_json``. ``"bucket"`` marks rows backfilled
    from the venue's finalized export, which carry an empty ``raw_json``; on
    Robinhood Chain these cover the span before live capture."""

    @model_validator(mode="before")
    @classmethod
    def _timestamp_ms(cls, values: Any) -> Any:
        return _ms_from_legacy(values, "timestamp")


class LighterLiquidationVolume(BaseModel):
    """Aggregated Lighter liquidation volume for one time bucket.

    Lighter buckets carry the total only. There is no long/short split because
    the trade payload does not reliably say which side was liquidated.
    """

    symbol: str
    """Market symbol."""

    timestamp: datetime
    """Bucket start (UTC)."""

    timestamp_ms: Optional[int] = None
    """Bucket start in Unix milliseconds."""

    total_usd: float
    """Total liquidated notional in the bucket, in the quote asset."""

    count: int
    """Number of liquidation trades in the bucket."""

    @model_validator(mode="before")
    @classmethod
    def _timestamp_ms(cls, values: Any) -> Any:
        return _ms_from_legacy(values, "timestamp")


# =============================================================================
# Account Positions Types
# =============================================================================
#
# Numbers are decimal strings (sizes at the market's size precision, prices at
# its price precision, USD values to 6 decimals); a flat position is ``"0"``.
# A field is ``None`` when it is unknown, never a guess. Timestamps are UTC.


class PositionLeverage(BaseModel):
    """Leverage of a position."""

    type: str
    """``"cross"``, ``"isolated"`` or ``"unknown"`` (always ``"unknown"`` on
    reconstructed Hyperliquid rows). On Lighter, the margin mode."""

    value: Optional[str] = None
    """Leverage multiple, or ``None`` when not reported."""


class PositionCumFunding(BaseModel):
    """Cumulative funding of a position, in USD (Hyperliquid snapshot rows only)."""

    all_time: Optional[str] = None
    since_open: Optional[str] = None
    since_change: Optional[str] = None


class Position(BaseModel):
    """One open position of an account.

    Returned by the wallet or account routes (``positions.get()``,
    ``positions.history()``). Hyperliquid rows carry the full snapshot fields;
    Lighter rows carry ``account_index``, ``account_kind`` and the Lighter
    extras, and leave the Hyperliquid-only fields ``None``.
    """

    snapshot_ts: Optional[datetime] = None
    """Hour the row describes (hourly history rows only)."""

    account_index: Optional[str] = None
    """Lighter account index, as a string (Lighter only)."""

    account_kind: Optional[str] = None
    """Lighter only: ``"user"``, ``"settlement"``, ``"insurance"`` or ``"system"``."""

    symbol: str
    """Market symbol."""

    coin: str
    """Alias of ``symbol``."""

    dex: Optional[str] = None
    """HIP-3 dex (HIP-3 only)."""

    size: str
    """Signed position size; negative is short."""

    side: Literal["long", "short"]
    """Position side."""

    entry_price: Optional[str] = None
    mark_price: Optional[str] = None

    mark_time: Optional[datetime] = None
    """Time of the mark used for ``mark_price``, ``position_value`` and ``unrealized_pnl``."""

    position_value: Optional[str] = None
    """Absolute size times mark, in USD."""

    unrealized_pnl: Optional[str] = None
    return_on_equity: Optional[str] = None
    leverage: PositionLeverage
    max_leverage: Optional[int] = None
    margin_used: Optional[str] = None
    liquidation_price: Optional[str] = None

    liquidation_price_status: str
    """How ``liquidation_price`` was determined: ``"exact"`` (set),
    ``"not_published_cross"`` (Hyperliquid does not publish cross-margin
    liquidation prices), ``"changed_since_snapshot"`` or ``"unavailable"``."""

    cum_funding: PositionCumFunding

    opened_at: Optional[datetime] = None
    """When the current position was opened."""

    snapshot_as_of: Optional[datetime] = None
    """Instant the leverage, funding and account fields describe. Size, entry
    and mark fields describe ``snapshot_ts`` (or the response's ``as_of``)."""

    quality: str
    """Row quality: ``"complete"``, ``"partial"`` (for example no mark),
    ``"degraded"``; Lighter also uses ``"preliminary"``, ``"unreconciled"`` and
    ``"incomplete"``."""

    initial_margin_fraction: Optional[str] = None
    """Lighter only: initial margin fraction at the last trade, as a fraction."""

    allocated_margin: Optional[str] = None
    """Lighter only: allocated margin in the quote asset."""

    margin_mode: Optional[str] = None
    """Lighter only: margin mode."""

    mark_source: Optional[str] = None
    """Lighter only: where the mark came from (``"none"`` when there was no mark)."""

    finalized: Optional[bool] = None
    """Lighter only: ``True`` when every event behind the row is final."""


class MarketPosition(BaseModel):
    """One open position in a market-wide listing (``positions.market()`` and
    ``positions.all()``). A lean record: the account plus size, price and value."""

    snapshot_ts: Optional[datetime] = None
    """Hour the row describes (bulk ``positions.all()`` rows)."""

    user_address: Optional[str] = None
    """Wallet address (Hyperliquid and HIP-3)."""

    account_index: Optional[str] = None
    """Account index, as a string (Lighter)."""

    account_kind: Optional[str] = None
    """Account kind (Lighter): ``"user"``, ``"settlement"``, ``"insurance"`` or ``"system"``."""

    symbol: str
    coin: str
    dex: Optional[str] = None
    size: str
    side: Literal["long", "short"]
    entry_price: Optional[str] = None
    mark_price: Optional[str] = None
    position_value: Optional[str] = None
    unrealized_pnl: Optional[str] = None

    leverage_type: str
    """``"cross"``, ``"isolated"`` or ``"unknown"``; on Lighter, the margin mode."""

    liquidation_price: Optional[str] = None
    quality: str


class PositionChange(BaseModel):
    """One change-log leg: a fill or event that changed an account's position.

    ``side`` is ``"B"`` or ``"A"`` exactly as on trades. Hyperliquid rows carry
    ``direction``, ``closed_pnl``, ``crossed`` and ``seq``; Lighter rows carry
    ``realized_pnl``, ``is_maker`` and the Lighter extras.
    """

    timestamp: datetime
    account_index: Optional[str] = None
    account_kind: Optional[str] = None
    symbol: str
    coin: str
    dex: Optional[str] = None
    side: Literal["A", "B"]
    price: Optional[str] = None
    size: Optional[str] = None

    start_position: Optional[str] = None
    """Signed position before the leg."""

    end_position: Optional[str] = None
    """Signed position after the leg."""

    entry_price_after: Optional[str] = None
    """Entry price after the leg; ``None`` when the position is flat."""

    event_type: str
    """What the leg did to the position: ``"open"``, ``"increase"``,
    ``"reduce"``, ``"close"`` or ``"flip"``. On Lighter, a leg that leaves the
    position unchanged is ``"settlement"`` (the settlement counterparty's side
    of a market settlement) or otherwise ``"unchanged"``."""

    cause: str
    """What produced the leg: ``"trade"``, ``"liquidation"``,
    ``"liquidation_counterparty"``, ``"adl"``, ``"settlement"`` or ``"unknown"``."""

    direction: Optional[str] = None
    """Hyperliquid only: direction as on trades (for example ``"Open Long"``)."""

    closed_pnl: Optional[str] = None
    """Hyperliquid only: realized PnL of the leg."""

    realized_pnl: Optional[str] = None
    """Lighter only: realized PnL of the leg."""

    fee: Optional[str] = None
    fee_token: str

    crossed: Optional[bool] = None
    """Hyperliquid only: ``True`` for the taker leg."""

    is_maker: Optional[bool] = None
    """Lighter only: ``True`` for the maker leg."""

    trade_id: int
    order_id: Optional[int] = None
    opened_at: Optional[datetime] = None

    seq: Optional[int] = None
    """Hyperliquid only: order of the leg among legs with the same timestamp."""

    block_number: Optional[int] = None
    """Hyperliquid only: block of the leg, when known."""

    event_index: Optional[int] = None
    """Hyperliquid only: index of the leg within its block, when known."""

    continuity: str
    """``"ok"``, ``"inferred"`` (the chain was re-seeded from the venue's
    reported start position), ``"first_seen"`` or ``"quarantined"``."""

    position_size_before: Optional[str] = None
    """Lighter alias of ``start_position``."""

    position_size_after: Optional[str] = None
    """Lighter alias of ``end_position``."""

    fee_rate: Optional[str] = None
    """Lighter only: fee rate as a fraction."""

    fee_usdc: Optional[str] = None
    """Lighter only: fee in the quote asset."""

    usdc_amount: Optional[str] = None
    """Lighter only: notional of the leg in the quote asset."""

    finalized: Optional[bool] = None
    """``True`` when the leg is final and will not be re-derived."""


class AccountSummary(BaseModel):
    """Account summary at one snapshot.

    Hyperliquid and HIP-3: the full clearinghouse summary, one row per
    clearinghouse (Hyperliquid core has one per address, HIP-3 one per dex),
    returned by ``positions.account()`` / ``positions.account_history()`` and
    as ``WalletPositions.account``. ``withdrawable`` is only available for
    older hourly history.

    Lighter mainnet and Robinhood Chain: position aggregates only, returned by
    ``positions.account()`` / ``positions.account_history()`` and as
    ``WalletPositions.account`` on ``positions.get()``. ``account_index``,
    ``total_position_value``, ``total_unrealized_pnl``, ``long_value``,
    ``short_value``, ``n_positions`` and ``quality`` are set; ``dex``, the
    margin fields (``account_value``, ``cross_account_value``, ``collateral``,
    ``total_margin_used``, ``cross_maintenance_margin_used``,
    ``withdrawable``), ``account_mode`` and ``snapshot_as_of`` are ``None``.
    A Lighter total is ``None`` when any position in it has no mark, never a
    partial sum.
    """

    snapshot_ts: Optional[datetime] = None
    """Hour the row describes (hourly history rows only)."""

    account_index: Optional[str] = None
    """Lighter account index, as a string (Lighter summaries only)."""

    dex: Optional[str] = None
    account_value: Optional[str] = None
    cross_account_value: Optional[str] = None
    collateral: Optional[str] = None
    total_margin_used: Optional[str] = None
    cross_maintenance_margin_used: Optional[str] = None
    withdrawable: Optional[str] = None
    total_position_value: Optional[str] = None
    total_unrealized_pnl: Optional[str] = None
    long_value: Optional[str] = None
    short_value: Optional[str] = None
    n_positions: int
    account_mode: Optional[str] = None
    snapshot_as_of: Optional[datetime] = None
    quality: str


class MarketPositionsSummary(BaseModel):
    """Long/short aggregates of every open position in one market at one snapshot.

    Returned by ``positions.market_summary()`` and as ``meta.totals`` on the
    first page of ``positions.market()``. Average entries cover only the
    positions whose entry is known (``*_positions_with_entry``). A total or share
    is ``None`` when any position in it has no mark, never a partial sum.
    """

    snapshot_ts: Optional[datetime] = None
    symbol: str
    coin: str
    dex: Optional[str] = None
    long_count: int
    short_count: int
    long_size: str
    short_size: str
    long_value: Optional[str] = None
    short_value: Optional[str] = None
    long_avg_entry_price: Optional[str] = None
    short_avg_entry_price: Optional[str] = None
    long_positions_with_entry: int
    short_positions_with_entry: int

    long_top10_value_share: Optional[str] = None
    """Share of long value held by the 10 largest longs, as a fraction."""

    short_top10_value_share: Optional[str] = None
    """Share of short value held by the 10 largest shorts, as a fraction."""

    top10_value_share: Optional[str] = None
    """Share of total value held by the 10 largest positions, as a fraction."""

    quality: str


class WalletPositions(BaseModel):
    """``data`` of ``positions.get()``: an account's open positions at one instant."""

    positions: list[Position] = Field(default_factory=list)
    """Open positions (flat markets are not listed)."""

    account: Optional[AccountSummary] = None
    """Account summary on the first page of a snapshot (the live snapshot, or a
    ``timestamp`` on an exact UTC hour). Hyperliquid core: when the wallet has
    an account in that snapshot. HIP-3: when ``dex`` (or a ``symbol``) names
    one dex. Lighter mainnet and
    Robinhood Chain: when the request has no ``symbol`` filter; the summary
    holds position aggregates only (see :class:`AccountSummary`). ``None`` on
    later pages and on reconstructions (a ``timestamp`` between hours)."""

    account_seen: Optional[str] = None
    """Set only when ``positions`` is empty: ``"flat"`` (activity recorded, no
    open position), ``"never_seen"`` (no activity recorded in the covered
    history; see ``meta.notice`` and ``meta.coverage_from``) or
    ``"outside_coverage"`` (the instant is before coverage begins)."""


class PositionsFreshness(BaseModel):
    """Freshness of the account positions data of one venue.

    Returned by ``client.data_quality.positions_freshness()``, one row per
    venue: Hyperliquid core (``venue="hyperliquid"``, ``product="core"``),
    HIP-3 (``"hyperliquid"``, ``"hip3"``), Lighter (``"lighter"``,
    ``"lighter"``) and Lighter on Robinhood Chain (``"rh_lighter"``,
    ``"rh_lighter"``).
    """

    venue: str
    """Venue: ``"hyperliquid"``, ``"lighter"`` or ``"rh_lighter"``."""

    product: str
    """Product within the venue: ``"core"``, ``"hip3"``, ``"lighter"`` or ``"rh_lighter"``."""

    live_snapshot_ts: Optional[datetime] = None
    """Time of the latest live snapshot."""

    live_age_seconds: Optional[int] = None
    """Age of the latest live snapshot, in seconds."""

    stale: bool
    """``True`` when the latest live snapshot is older than 12 minutes (or there is none)."""

    live_quality: Optional[str] = None
    """Quality of the latest live snapshot: ``"complete"``, ``"partial"`` or ``"degraded"``."""

    hourly_snapshot_ts: Optional[datetime] = None
    """Hour of the latest hourly snapshot."""

    built_through: Optional[datetime] = None
    """Every event before this instant is built into the change log and the as-of state."""

    finalized_through: Optional[datetime] = None
    """Every event before this instant is final and will not be re-derived."""


class LighterL1Account(BaseModel):
    """One Lighter account owned by an L1 address."""

    account_index: str
    """Account index, as a string. Pass it to ``positions.get()``."""

    account_type: int
    """Lighter account type."""

    first_seen: Optional[datetime] = None
    """When the account was first seen."""


class LighterL1Accounts(BaseModel):
    """``data`` of ``client.lighter.accounts.by_l1()``."""

    l1_address: str
    """The L1 address, lowercased."""

    total_accounts: int
    """Number of accounts the address owns (across all pages)."""

    accounts: list[LighterL1Account] = Field(default_factory=list)
    """Accounts on this page, ascending by account index."""


class ResponseMeta(BaseModel):
    """Response metadata (the ``meta`` object of an API response).

    Every field is optional; a route sets only the fields that apply to it.
    Unknown fields are kept. Instants are UTC.
    """

    model_config = ConfigDict(extra="allow")

    count: Optional[int] = None
    """Rows in this page."""

    next_cursor: Optional[str] = None
    """Cursor for the next page; ``None`` on the last page."""

    has_more: Optional[bool] = None
    """On cursor-paged routes, whether another page follows. ``next_cursor``
    is set exactly when it is ``True``. A final page can be empty when the
    page before it was exactly full."""

    request_id: Optional[str] = None

    symbol: Optional[str] = None
    """On per-symbol routes, the canonical public symbol the response is for
    (for example ``BTC``, ``km:US500``, ``HYPE-USDC``, ``#0``)."""

    venue: Optional[str] = None
    """On per-symbol routes, the venue that served it: ``"hyperliquid"``,
    ``"hip3"``, ``"hip4"``, ``"spot"``, ``"lighter"`` or ``"rh-lighter"``
    (see :data:`Venue`)."""

    finalized_through: Optional[datetime] = None
    """Every event before this instant is final and will not be re-derived.
    On Lighter trades, the canonical boundary; on account positions, how far the
    position data is final."""

    requested_end: Optional[datetime] = None
    """Set with ``clamped_to`` when the request asked past the served boundary:
    the end (or ``timestamp``) the request asked for."""

    clamped_to: Optional[datetime] = None
    """Set when the request was clamped: the boundary it was clamped to
    (``finalized_through`` on Lighter trades, ``built_through`` on positions)."""

    preliminary_row_count: Optional[int] = None
    """Rows in the page that are not final yet. The API sends it only on the
    Lighter ``/trades/{symbol}/recent`` response, and ``trades.recent()``
    returns a plain list without the meta, so no SDK method returns it in this
    release. It is typed so the meta parses wherever it appears."""

    coverage_from: Optional[datetime] = None
    """Where coverage begins, set with ``notice`` when a window is before coverage."""

    notice: Optional[str] = None
    """Human-readable advisory about this response."""

    as_of: Optional[datetime] = None
    """Instant the returned state describes, taken from the data."""

    snapshot_ts: Optional[datetime] = None
    """Snapshot the response was read from (market routes echo ``hour`` here)."""

    source: Optional[str] = None
    """How the rows were produced: ``"snapshot"``, ``"reconstructed"`` or ``"changes"``."""

    quality: Optional[str] = None
    """Completeness of the snapshot the response was read from, for example
    ``"complete"``, ``"partial"`` or ``"degraded"``."""

    stale: Optional[bool] = None
    """``True`` when the latest live snapshot is older than 12 minutes (with a ``notice``)."""

    totals: Optional[Union[MarketPositionsSummary, dict[str, Any]]] = Field(
        default=None, union_mode="left_to_right"
    )
    """Totals over the whole filtered result set, not just this page. Set on the
    first page of ``positions.market()``."""

    built_through: Optional[datetime] = None
    """Account positions: every event before this instant is built into the
    change log and the as-of state; reads are clamped to it. Data before it may
    still be preliminary (see ``finalized_through``)."""

    @field_validator(
        "finalized_through",
        "requested_end",
        "clamped_to",
        "coverage_from",
        "as_of",
        "snapshot_ts",
        "built_through",
        mode="before",
    )
    @classmethod
    def _empty_instant_is_none(cls, value: Any) -> Any:
        return None if value == "" else value

    @classmethod
    def of(cls, envelope: Any) -> "ResponseMeta":
        """The typed ``meta`` of a response envelope (empty when it has none)."""
        meta = envelope.get("meta") if isinstance(envelope, dict) else None
        return cls.model_validate(meta if isinstance(meta, dict) else {})


# =============================================================================
# Pagination Types
# =============================================================================


RecordT = TypeVar("RecordT", bound=_ApiRecord)


def _record(model: type[RecordT], envelope: dict[str, Any]) -> RecordT:
    """Parse ``envelope["data"]`` as ``model`` and attach the response's meta."""
    record = model.model_validate(envelope["data"])
    record._response_meta = ResponseMeta.of(envelope)
    return record


def _body(envelope: dict[str, Any]) -> Any:
    """The payload of a data quality, status coverage or symbols response.

    With the ``0xArchive-Version`` the SDK sends, these routes answer with the
    standard envelope and the payload is ``data``. A body in the older shape
    has the payload's fields at the top level instead; it is returned as is.
    """
    data = envelope.get("data")
    return data if isinstance(data, (dict, list)) and "success" in envelope else envelope


def _outlier_record(model: type[RecordT], envelope: dict[str, Any]) -> RecordT:
    """Parse a data quality style response as ``model`` and attach its meta."""
    record = model.model_validate(_body(envelope))
    record._response_meta = ResponseMeta.of(envelope)
    return record


class CursorResponse(BaseModel, Generic[T]):
    """One page of a cursor-paged response.

    While ``has_more`` is ``True``, pass ``next_cursor`` back unchanged as
    ``cursor`` with the other arguments unchanged. Stop when ``has_more`` is
    ``False``: a page can be short, or even empty, and still not be the last,
    so stop on ``has_more`` rather than on the page size.
    """

    data: T
    """The paginated data."""

    next_cursor: Optional[str] = None
    """Cursor for the next page (use as cursor parameter). Set exactly when
    ``has_more`` is ``True``."""

    has_more: bool = False
    """Whether another page follows. Taken from the response's
    ``meta.has_more``; on a route that does not send it, ``True`` exactly when
    ``next_cursor`` is set."""

    meta: Optional[ResponseMeta] = None
    """The response's metadata: ``request_id``, ``count``, ``has_more``, and on
    per-symbol routes ``symbol`` and ``venue``, plus route-specific fields such
    as ``finalized_through`` (Lighter trades) or ``coverage_from`` and
    ``notice`` (a window before coverage)."""

    @model_validator(mode="before")
    @classmethod
    def _page_state(cls, values: Any) -> Any:
        if not isinstance(values, dict):
            return values
        meta = values.get("meta")
        if isinstance(meta, ResponseMeta):
            meta_cursor, meta_more = meta.next_cursor, meta.has_more
        elif isinstance(meta, dict):
            meta_cursor, meta_more = meta.get("next_cursor"), meta.get("has_more")
        else:
            meta_cursor, meta_more = None, None
        values = dict(values)
        if values.get("next_cursor") is None and meta_cursor is not None:
            values["next_cursor"] = meta_cursor
        if values.get("has_more") is None:
            values["has_more"] = (
                bool(meta_more) if meta_more is not None else values.get("next_cursor") is not None
            )
        return values

    @classmethod
    def from_envelope(cls, envelope: dict[str, Any], data: Any) -> "CursorResponse[Any]":
        """A page from a response envelope and its already-parsed ``data``."""
        meta = ResponseMeta.of(envelope)
        return cls(data=data, next_cursor=meta.next_cursor, meta=meta)


# Type alias for timestamp parameters
Timestamp = Union[int, str, datetime]
"""Timestamp can be Unix ms (int), an ISO 8601 string, or a datetime.

A time without a time zone is UTC: a naive datetime, an ISO string without an
offset (``"2026-09-01T12:00:00"``) and a date alone (``"2026-09-01"``, midnight
UTC) mean the same instant on every machine."""


# =============================================================================
# Capabilities
# =============================================================================


class Capability(BaseModel):
    """What one venue serves for one datatype, from ``client.capabilities()``.

    One row per venue and datatype. Coverage per symbol is on
    ``client.symbols.list()``.
    """

    model_config = ConfigDict(extra="allow")

    venue: str
    """The venue (see :data:`Venue`)."""

    datatype: str
    """Datatype id, for example ``"trades"``, ``"l2_orderbook"``,
    ``"l4_diffs"``, ``"funding"`` or ``"oi"``."""

    rest_routes: list[str] = Field(default_factory=list)
    """REST route templates that serve it, for example
    ``/v1/hyperliquid/trades/{symbol}``."""

    ws_channels: list[str] = Field(default_factory=list)
    """WebSocket channels that carry it."""

    live: bool = False
    """``True`` when a WebSocket subscription streams it live."""

    replay: bool = False
    """``True`` when a WebSocket replay serves its history."""

    available_from: Optional[datetime] = None
    """The first served instant across the venue (UTC), or ``None`` where the
    datatype has no venue-wide floor."""

    cadence: Optional[str] = None
    """``"event"``, ``"snapshot"``, ``"sample"``, ``"interval"`` or
    ``"reference"``."""

    page_limit: Optional[int] = None
    """The largest ``limit`` one page accepts."""

    intervals: list[str] = Field(default_factory=list)
    """Values ``interval`` accepts, where the datatype is bucketed."""

    notes: Optional[str] = None
    """Anything else worth knowing, such as how its replay behaves."""


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


class StatusResponse(_ApiRecord):
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


class ExchangeCoverage(_ApiRecord):
    """Coverage for a single exchange."""

    exchange: str
    """Exchange name."""

    data_types: dict[str, DataTypeCoverage]
    """Coverage per data type."""


class CoverageResponse(_ApiRecord):
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

    historical_coverage: Optional[float] = None
    """Historical coverage percentage (0-100) based on hours with data / total hours."""

    gaps: list[CoverageGap]
    """Detected data gaps within the requested time window."""

    cadence: Optional[DataCadence] = None
    """Empirical data cadence (present when sufficient data exists)."""


class SymbolCoverageResponse(_ApiRecord):
    """Per-symbol coverage response."""

    exchange: str
    """Exchange name."""

    symbol: str
    """Symbol name."""

    data_types: dict[str, SymbolDataTypeCoverage]
    """Coverage per data type."""


class Incident(_ApiRecord):
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


class IncidentsResponse(_ApiRecord):
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


class LatencyResponse(_ApiRecord):
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


class SlaResponse(_ApiRecord):
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
# Cumulative Volume Delta Types
# =============================================================================

CvdInterval = Literal["1m", "5m", "15m", "30m", "1h", "4h", "1d", "1w"]
"""Cumulative volume delta bucket widths. ``1h`` and longer roll up hourly
totals; ``1m`` to ``30m`` are summed from taker fills."""


class CvdBucket(BaseModel):
    """One cumulative volume delta bucket: taker buy and sell notional."""

    timestamp: datetime
    """Bucket open time (UTC)."""

    timestamp_ms: Optional[int] = None
    """Bucket open time in Unix milliseconds."""

    @model_validator(mode="before")
    @classmethod
    def _timestamp_ms(cls, values: Any) -> Any:
        return _ms_from_legacy(values, "timestamp")

    buy_volume: float
    """Taker buy notional in the bucket."""

    sell_volume: float
    """Taker sell notional in the bucket."""

    delta: float
    """``buy_volume`` minus ``sell_volume``."""

    cumulative_delta: float
    """Running total of ``delta`` from the first bucket of this response. It
    restarts on every page, so rebuild it from ``delta`` when joining pages."""


# =============================================================================
# HIP-3 Oracle Types
# =============================================================================


class Hip3OracleDiscoveryBounds(_ApiRecord):
    """Instantaneous HIP-3 discovery bounds from the reference price and max leverage.

    The full ratcheted range can be wider when a deployer's reset
    configuration applies.
    """

    symbol: str
    """HIP-3 symbol (for example ``km:US500``)."""

    reference_price: float
    """External price when available, otherwise the mark price."""

    reference_source: str
    """Source of ``reference_price``: ``"external"`` or ``"mark"``."""

    max_leverage: int
    """Market max leverage used for the bound fraction."""

    bound_fraction: float
    """Fraction applied on each side of ``reference_price``."""

    lower_bound: float
    """Instantaneous lower discovery bound."""

    upper_bound: float
    """Instantaneous upper discovery bound."""

    block_number: int
    """Source block number."""

    timestamp: datetime
    """Source time (UTC)."""

    timestamp_ms: Optional[int] = None
    """Source time in Unix milliseconds."""

    @model_validator(mode="before")
    @classmethod
    def _timestamp_ms(cls, values: Any) -> Any:
        return _ms_from_legacy(values, "timestamp")


class Hip3OracleExternalPrice(_ApiRecord):
    """Latest deployer-pushed external price and mark price for a HIP-3 market."""

    symbol: str
    """HIP-3 symbol (for example ``km:US500``)."""

    external_price: Optional[float] = None
    """Externally derived reference price, when available."""

    mark_price: Optional[float] = None
    """On-chain mark input."""

    block_number: int
    """Source block number."""

    timestamp: datetime
    """Source time (UTC)."""

    timestamp_ms: Optional[int] = None
    """Source time in Unix milliseconds."""

    @model_validator(mode="before")
    @classmethod
    def _timestamp_ms(cls, values: Any) -> Any:
        return _ms_from_legacy(values, "timestamp")


# =============================================================================
# HIP-4 Question Types
# =============================================================================


class Hip4Question(_ApiRecord):
    """A HIP-4 question: a multi-choice resolver grouping binary outcome markets.

    One named outcome per choice, plus a fallback outcome that resolves Yes
    when no named choice does.
    """

    model_config = ConfigDict(extra="allow")

    question_id: int
    """Question identifier."""

    name: str
    """Question name as published on-chain (recurring markets use a generic
    name such as ``"Recurring"``)."""

    description: str
    """Pipe-delimited question metadata, for example
    ``"class:priceBucket|underlying:BTC|expiry:20260508-0600|priceThresholds:79303,82540|period:1d"``."""

    fallback_outcome_id: int
    """Outcome that resolves Yes when no named outcome does."""

    named_outcome_ids: list[int] = Field(default_factory=list)
    """Outcomes of the named choices grouped under this question."""

    settled_named_outcomes: list[int] = Field(default_factory=list)
    """The named outcomes that have already settled."""

    first_seen_at: datetime
    """When 0xArchive first observed the question (UTC)."""

    last_updated_at: datetime
    """When the question record was last updated (UTC)."""


# =============================================================================
# Wallet Classification Types
# =============================================================================

WalletClassifySort = Literal[
    "total_orders",
    "total_fills",
    "total_volume",
    "total_volume_usd",
    "cancel_rate",
    "fill_rate",
    "maker_ratio",
    "avg_order_size_usd",
    "avg_order_notional",
    "max_order_size_usd",
    "max_order_notional",
    "active_hours",
    "unique_coins",
    "total_fees",
    "total_fees_usd",
    "realized_pnl",
    "realized_pnl_usd",
    "median_cancel_speed_ms",
    "twap_fills",
    "total_priority_gas",
    "total_priority_gas_paid",
    "total_builder_fees",
    "total_builder_fees_paid",
]
"""Metrics wallet classification can sort by."""


class WalletClassifyMetrics(BaseModel):
    """Precomputed daily behavior metrics for one wallet. Every field is optional."""

    model_config = ConfigDict(extra="allow")

    total_orders: Optional[int] = None
    cancel_rate: Optional[float] = None
    fill_rate: Optional[float] = None
    order_to_trade_ratio: Optional[float] = None
    ioc_ratio: Optional[float] = None
    post_only_ratio: Optional[float] = None
    tpsl_ratio: Optional[float] = None
    trigger_order_ratio: Optional[float] = None
    unique_coins_traded: Optional[int] = None
    uses_tpsl: Optional[bool] = None
    uses_builder: Optional[bool] = None
    top_builder: Optional[str] = None
    avg_order_size_usd: Optional[float] = None
    max_order_size_usd: Optional[float] = None
    median_cancel_speed_ms: Optional[float] = None
    active_hours: Optional[int] = None
    total_fills: Optional[int] = None
    total_volume_usd: Optional[float] = None
    maker_ratio: Optional[float] = None
    long_short_ratio: Optional[float] = None
    buy_volume_usd: Optional[float] = None
    sell_volume_usd: Optional[float] = None
    total_fees_usd: Optional[float] = None
    realized_pnl_usd: Optional[float] = None
    liquidation_count: Optional[int] = None
    max_single_fill_usd: Optional[float] = None
    unique_fill_coins: Optional[int] = None
    uses_twap: Optional[bool] = None
    twap_fill_ratio: Optional[float] = None
    uses_cloid: Optional[bool] = None
    cloid_ratio: Optional[float] = None
    uses_priority_gas: Optional[bool] = None
    total_priority_gas_paid: Optional[float] = None
    total_builder_fees_paid: Optional[float] = None


class ClassifiedWallet(BaseModel):
    """A wallet and its precomputed behavior metrics."""

    address: str
    """Wallet address."""

    metrics: WalletClassifyMetrics
    """Behavior metrics over ``period``."""

    period: str
    """Metric lookback period (for example ``"24h"``)."""


class WalletClassification(_ApiRecord):
    """One page of wallet classification results."""

    wallets: list[ClassifiedWallet] = Field(default_factory=list)
    """Wallets on this page, in the requested sort order."""

    total: int
    """Wallets matching the filters, across every page."""

    date: str
    """Daily snapshot date the metrics describe (``YYYY-MM-DD``)."""


# =============================================================================
# Symbol Universe Types
# =============================================================================


class SymbolEntry(BaseModel):
    """One market in the public symbol universe, from ``client.symbols.list()``."""

    model_config = ConfigDict(extra="allow")

    symbol: str
    """Symbol as the venue's routes take it (for example ``BTC``, ``km:US500``,
    ``HYPE-USDC``, ``#0``)."""

    exchange: str
    """Venue family: ``"hyperliquid"``, ``"hip3"``, ``"hip4"``, ``"spot"``,
    ``"lighter"`` or ``"rh-lighter"``."""

    coverage_from: Optional[datetime] = None
    """Earliest data for the symbol (UTC)."""

    coverage_to: Optional[datetime] = None
    """Latest data for the symbol (UTC), when it has ended."""

    data_types: list[str] = Field(default_factory=list)
    """Data types served for the symbol (for example ``"trades"``, ``"l2_orderbook"``)."""

    coverage_by_type: dict[str, datetime] = Field(default_factory=dict)
    """Earliest data per data type (UTC)."""

    size_per_day: dict[str, float] = Field(default_factory=dict)
    """Approximate size per day by data type."""

    slug: Optional[str] = None
    """HIP-4 slug, when available."""

    outcome_pair: Optional[list[str]] = None
    """HIP-4: the two side symbols of the outcome."""

    display_title: Optional[str] = None
    """HIP-4: human-readable title."""

    is_settled: Optional[bool] = None
    """HIP-4: whether the outcome has settled."""

    is_active: Optional[bool] = None
    """Whether the market is active, when the venue reports it."""


# =============================================================================
# Webhook Types
# =============================================================================
#
# Webhook delivery is a paid feature. Free has no endpoints, subscriptions,
# watched wallets or deliveries, but every plan keeps the two previews
# (estimate and dry-run), so a rule can be designed and sized before
# upgrading. ``client.webhooks.limits()`` reports what the plan allows.
#
# Every model here keeps unknown fields. The webhook surface gains fields
# faster than the SDK ships, and an extra key must never raise in a receiver.


class WebhookEventTypeParam(BaseModel):
    """A tunable parameter an event type declares.

    Values sent under ``params`` are checked against this declaration, and a
    declared parameter left unset is stored at its default.
    """

    model_config = ConfigDict(extra="allow")

    type: Optional[str] = None
    """Value type: ``"integer"``, ``"number"``, ``"string"`` or ``"array_of_number"``."""

    unit: Optional[str] = None
    """Unit the value is expressed in, when it has one (for example ``"s"``)."""

    default: Any = None
    """Value used when the parameter is not supplied."""

    min: Optional[float] = None
    """Lowest accepted value, when bounded below."""

    max: Optional[float] = None
    """Highest accepted value, when bounded above."""

    enum: Optional[list[Any]] = None
    """Accepted values, when the parameter is a fixed choice."""

    description: Optional[str] = None
    """What the parameter changes."""


class WebhookEventTypeMetric(BaseModel):
    """A metric an event carries, and so a metric a condition may be written against."""

    model_config = ConfigDict(extra="allow")

    type: Optional[str] = None
    """Value type, which decides the operators a condition may use: for example
    ``"number"``, ``"integer"``, ``"string"``, ``"boolean"`` or ``"timestamp"``."""

    unit: Optional[str] = None
    """Unit the metric is expressed in, when it has one (for example ``"USD"``)."""

    values: Optional[list[str]] = None
    """Accepted values, when the metric is a fixed choice."""

    description: Optional[str] = None
    """What the metric measures, including when it is null."""


class WebhookCostFloor(BaseModel):
    """The smallest occurrence an event type reports at all."""

    model_config = ConfigDict(extra="allow")

    metric: Optional[str] = None
    """Metric the floor applies to (for example ``"notional_usd"``)."""

    min: Optional[float] = None
    """Lowest value still reported."""


class WebhookEventType(BaseModel):
    """One entry in the event catalog, from ``client.webhooks.event_types()``.

    Subscriptions are validated against this declaration, so it is the
    authority on the filters, parameters, metrics and operators a
    configuration may use. Read them from here rather than hardcoding them.
    """

    model_config = ConfigDict(extra="allow")

    type: str
    """Event type identifier, for example ``"market.liquidation"``. Send it as
    ``event_type`` when creating a subscription."""

    schema_version: int
    """Version of the delivered payload shape for this event type."""

    live: bool
    """True when the type accepts subscriptions. A type that is published but
    not yet live is refused at create time."""

    scope: str
    """Who the event is about: ``"public"`` (market wide), ``"user"`` (your own
    account and platform activity) or ``"addresses"`` (only wallets on your
    watched list)."""

    venues: list[str] = Field(default_factory=list)
    """Venues the type covers. Empty when the type is not venue scoped."""

    filters: list[str] = Field(default_factory=list)
    """Filter keys a configuration accepts. A key not listed is refused."""

    params: dict[str, WebhookEventTypeParam] = Field(default_factory=dict)
    """Tunable parameters, keyed by parameter name."""

    metrics: dict[str, WebhookEventTypeMetric] = Field(default_factory=dict)
    """Metrics the event carries, keyed by name. Conditions may only use these."""

    cost_floor: Optional[WebhookCostFloor] = None
    """The smallest occurrence the type reports. ``None`` when it has no floor."""

    latency_class: str
    """Rough delivery latency from the occurrence to the first attempt:
    ``"seconds"`` or ``"minutes"``."""

    description: str
    """What the event reports and what one occurrence means."""

    filters_example: Optional[dict[str, Any]] = None
    """A worked example of a configuration for this type."""

    operators: dict[str, list[str]] = Field(default_factory=dict)
    """Operator vocabulary grouped by metric type, plus the ``any`` group that
    applies to every metric."""


class WebhookEndpoint(BaseModel):
    """A delivery destination.

    The signing secret is not part of this shape: it is returned once when the
    endpoint is created (:class:`WebhookEndpointCreated`) and again when it is
    rotated (:class:`WebhookEndpointSecret`), never on a list.
    """

    model_config = ConfigDict(extra="allow")

    id: str
    """Endpoint identifier (UUID)."""

    url: str
    """HTTPS destination that receives deliveries."""

    description: str = ""
    """Your own label for the endpoint."""

    status: str
    """``"active"`` is serving, ``"disabled"`` means you switched it off, and
    ``"auto_disabled"`` means a long run of failed deliveries switched it off
    for you. Bring it back with ``enable_endpoint()``."""

    consecutive_failures: int = 0
    """Failed attempts since the last success. Resets to zero on a delivery that lands."""

    created_at: datetime
    """When the endpoint was created (UTC)."""


class WebhookEndpointCreated(WebhookEndpoint):
    """A newly created endpoint, with its signing secret.

    Creation and rotation are the only responses that carry the secret. Store
    it now: no later call returns it.
    """

    secret: str
    """Signing secret (``whsec_`` followed by 64 hex characters). Pass the whole
    string to :class:`~oxarchive.WebhookVerifier`; the prefix is part of the key."""

    note: Optional[str] = None
    """The API's advisory that the secret is shown once."""


class WebhookEndpointSecret(BaseModel):
    """A freshly rotated signing secret."""

    model_config = ConfigDict(extra="allow")

    secret: str
    """The new signing secret. The previous one keeps verifying for 24 hours."""

    note: Optional[str] = None
    """The API's advisory on how long the previous secret keeps verifying."""


class WebhookSubscriptionCondition(BaseModel):
    """One condition on an event metric; every condition must hold for a delivery."""

    model_config = ConfigDict(extra="allow")

    metric: str
    """A metric the event type declares (for example ``"notional_usd"``)."""

    op: str
    """Comparison, in canonical spelling: ``greater_than``,
    ``greater_than_or_equal``, ``less_than``, ``less_than_or_equal``, ``equal``,
    ``not_equal``, ``between``, ``not_between``, ``in``, ``not_in``,
    ``contains``, ``not_contains``, ``starts_with``, ``ends_with``, ``before``,
    ``after``, ``is_empty`` or ``is_not_empty``. Symbol spellings such as
    ``">="`` are accepted on the way in and stored canonically."""

    value: Any = None
    """What to compare against: a number, string, boolean or RFC 3339
    timestamp; a ``[low, high]`` pair for ``between`` and ``not_between``; a
    non-empty list for ``in`` and ``not_in``. Left out for ``is_empty`` and
    ``is_not_empty``."""


class WebhookSubscriptionConfig(BaseModel):
    """What a subscription matches on.

    Every key is checked against the event type's catalog declaration, so an
    unknown key, an undeclared parameter or a condition on an undeclared
    metric is refused rather than ignored. The stored form is normalised:
    venues and addresses lowercased, declared parameters filled in at their
    defaults, operators in canonical spelling. A declared parameter may also
    appear at the top level; such keys are kept as extra fields.
    """

    model_config = ConfigDict(extra="allow")

    venue: Optional[Union[str, list[str]]] = None
    """Venue or venues to match, from the event type's ``venues``. A single
    string, a pipe separated string or a list. ``None`` matches every covered
    venue."""

    symbols: Optional[list[str]] = None
    """Instrument symbols to match. ``None`` matches every symbol."""

    addresses: Optional[list[str]] = None
    """Wallets to match, for an address scoped type. Each must already be on
    your watched list. ``None`` matches all of them."""

    params: Optional[dict[str, Any]] = None
    """Parameter values, keyed by the names the event type declares."""

    conditions: Optional[list[WebhookSubscriptionCondition]] = None
    """Conditions on the event's metrics, all of which must hold. At most 16."""

    min_notional_usd: Optional[float] = None
    """Shorthand for a ``notional_usd`` at-or-above condition, kept for
    compatibility. It is stored as a condition and mirrored back here as the
    loosest notional lower bound the configuration carries."""


class WebhookSubscription(BaseModel):
    """A rule: one event type and one configuration, delivered to one endpoint."""

    model_config = ConfigDict(extra="allow")

    id: str
    """Subscription identifier (UUID)."""

    endpoint_id: str
    """Endpoint that receives this rule's deliveries."""

    event_type: str
    """Event type this rule subscribes to."""

    filters: WebhookSubscriptionConfig = Field(default_factory=WebhookSubscriptionConfig)
    """The stored, normalised configuration. The API names it ``filters``; the
    SDK methods take it as ``config`` (see :attr:`config`)."""

    enabled: bool
    """Your own on and off switch. Resuming a paused rule never changes it."""

    created_at: datetime
    """When the rule was created (UTC)."""

    status: str
    """``"active"`` is serving. ``"auto_paused"`` means delivery was paused for
    you and nothing is being sent; it stays paused until you resume it."""

    pause_message: Optional[str] = None
    """Why the rule is paused and what clears it, in plain words. Present only
    while the rule is paused."""

    paused_at: Optional[datetime] = None
    """Start of the current gap. ``None`` while the rule is serving."""

    pause_reason: Optional[str] = None
    """Machine readable cause of the current pause: ``"deliveries_per_day_cap"``
    (the account reached its daily delivery limit) or ``"plan_no_webhooks"``
    (the plan does not include webhook delivery). ``None`` while serving."""

    suppressed_count: int = 0
    """Matches observed but not delivered since the current pause began. A
    lower bound, not a total."""

    suppressed_first_at: Optional[datetime] = None
    """First suppressed match of the current pause."""

    suppressed_last_at: Optional[datetime] = None
    """Most recent suppressed match of the current pause."""

    last_paused_at: Optional[datetime] = None
    """Start of the last pause that has already ended."""

    last_resumed_at: Optional[datetime] = None
    """When that pause ended."""

    last_pause_reason: Optional[str] = None
    """Cause of the last ended pause, in the same vocabulary as ``pause_reason``."""

    last_suppressed_count: int = 0
    """Matches suppressed during the last pause that has already ended."""

    last_suppressed_first_at: Optional[datetime] = None
    """First suppressed match of that pause."""

    last_suppressed_last_at: Optional[datetime] = None
    """Most recent suppressed match of that pause."""

    @property
    def config(self) -> WebhookSubscriptionConfig:
        """Alias for :attr:`filters`, matching the SDK's request vocabulary."""
        return self.filters


class WebhookResumeReplayWindow(BaseModel):
    """The missed window of a resume, as a range to re-read for yourself."""

    model_config = ConfigDict(extra="allow")

    start: Optional[datetime] = None
    """Window start (UTC)."""

    end: Optional[datetime] = None
    """Window end (UTC)."""


class WebhookResumeGap(BaseModel):
    """The window a resume just closed.

    Nothing is buffered while a rule is paused, so this describes what was
    missed rather than replaying it. Re-read the window through the REST
    routes to recover it.
    """

    model_config = ConfigDict(extra="allow")

    paused_at: Optional[datetime] = None
    """Start of the gap."""

    resumed_at: Optional[datetime] = None
    """End of the gap."""

    replay_window: WebhookResumeReplayWindow = Field(
        default_factory=WebhookResumeReplayWindow
    )
    """The gap as a window to re-read."""

    reason: Optional[str] = None
    """Cause of the pause that was cleared. ``None`` on a bulk resume whose
    rules were paused for more than one reason."""

    reasons: Optional[list[str]] = None
    """Distinct causes across the resumed rules. Bulk resume only."""

    pause_message: Optional[str] = None
    """The cause in plain words."""

    suppressed_count: Optional[int] = None
    """Matches suppressed inside the window. ``None`` when the rules were address
    scoped, because their occurrences were never looked at."""

    counted: bool = False
    """Whether anything inside the window was counted. False means the count is
    ``None`` because nothing was looked at, not because nothing happened."""

    suppressed_first_at: Optional[datetime] = None
    """First suppressed match inside the window."""

    suppressed_last_at: Optional[datetime] = None
    """Most recent suppressed match inside the window."""

    uncounted_subscriptions: Optional[int] = None
    """How many resumed rules were address scoped and so not counted. Bulk resume only."""

    note: Optional[str] = None
    """What can and cannot be recovered for the window, and how."""


class WebhookSubscriptionResume(BaseModel):
    """Result of ``resume_subscription()``."""

    model_config = ConfigDict(extra="allow")

    subscription: WebhookSubscription
    """The subscription after the resume."""

    gap: Optional[WebhookResumeGap] = None
    """The window the resume closed. ``None`` when the rule was already
    serving, in which case nothing changed."""

    note: Optional[str] = None
    """Present only when nothing changed, to say why."""


class WebhookSubscriptionResumeAll(BaseModel):
    """Result of ``resume_all_subscriptions()``."""

    model_config = ConfigDict(extra="allow")

    subscriptions: list[WebhookSubscription] = Field(default_factory=list)
    """The rules that were put back into service."""

    resumed_count: int = 0
    """How many rules were put back into service."""

    gap: Optional[WebhookResumeGap] = None
    """The window the resume closed, across the rules it cleared. ``None`` when
    nothing was paused."""

    note: Optional[str] = None
    """Present only when nothing changed, to say why."""


class WebhookDelivery(BaseModel):
    """One record in an endpoint's delivery log.

    An event and an endpoint share a single record for their whole life, so a
    repeat delivery rewrites this record rather than adding another.
    """

    model_config = ConfigDict(extra="allow")

    id: str
    """Delivery identifier. Pass it to ``redeliver()``."""

    event_id: str
    """Event identifier, sent as the ``0xa-event-id`` header. Stable across
    retries and repeat deliveries: deduplicate on it."""

    event_type: str
    """Event type delivered."""

    state: str
    """``"pending"`` (queued or waiting to retry), ``"delivered"``, ``"failed"``
    (the last attempt's result) or ``"exhausted"`` (the retry window closed
    without success)."""

    attempts: int = 0
    """Attempts made so far."""

    last_status_code: Optional[int] = None
    """HTTP status your receiver returned on the last attempt."""

    last_error: Optional[str] = None
    """Why the last attempt failed. ``None`` when it succeeded."""

    last_latency_ms: Optional[int] = None
    """How long the last attempt took, in milliseconds."""

    next_attempt_at: datetime
    """When the next attempt is due (UTC)."""

    delivered_at: Optional[datetime] = None
    """When the delivery landed. ``None`` until it does."""

    created_at: datetime
    """When the delivery was queued. A repeat delivery resets it."""

    payload: dict[str, Any] = Field(default_factory=dict)
    """The event body as sent, with its ``id``, ``type``, ``schema_version``,
    ``observed_at`` and ``data``. For inspection only: verify signatures
    against the raw request bytes your receiver got, never against a
    re-serialised copy of this."""


class WebhookDeliveryQueued(BaseModel):
    """A delivery that has just been queued, from ``test_endpoint()``."""

    model_config = ConfigDict(extra="allow")

    delivery_id: str
    """Delivery identifier. Read it back from ``list_deliveries()``."""

    event_id: str
    """Event identifier carried in the delivered payload and the ``0xa-event-id`` header."""


class WebhookRedelivery(BaseModel):
    """A past delivery queued for another attempt, re-queued in place."""

    model_config = ConfigDict(extra="allow")

    delivery_id: str
    """Delivery identifier, the same one that was asked for."""

    event_id: str
    """Event identifier, unchanged, so a receiver that already processed the
    event can deduplicate on it."""

    event_type: str
    """Event type being delivered again."""

    state: str
    """Always ``"pending"`` immediately after a repeat delivery is queued."""

    attempts: int = 0
    """Attempt counter, restarted from zero."""

    next_attempt_at: datetime
    """When the attempt is due, which is immediately."""

    note: Optional[str] = None
    """The API's note on what the repeat delivery rewrites on the record."""


class WebhookWatchedAddress(BaseModel):
    """A wallet on your watched list. Address scoped event types report only on these."""

    model_config = ConfigDict(extra="allow")

    id: str
    """Watched address identifier. Pass it to ``delete_address()``."""

    address: str
    """The wallet, stored lowercase."""

    label: str = ""
    """Your own label for the wallet, at most 64 characters."""

    created_at: datetime
    """When the wallet was added (UTC)."""


class WebhookLimitUsage(BaseModel):
    """One cap: what the plan allows, what is in use and what is left."""

    model_config = ConfigDict(extra="allow")

    used: int
    """In use now."""

    limit: int
    """What the plan allows. Zero on a plan without webhook delivery."""

    remaining: int
    """What is left, never below zero. A plan change can leave an account
    legitimately over a cap."""


class WebhookDeliveryBudget(BaseModel):
    """Today's delivery budget. It resets on its own; a paused rule does not."""

    model_config = ConfigDict(extra="allow")

    used: int
    """Deliveries today."""

    limit: Optional[int] = None
    """Deliveries a day the plan allows. ``None`` when the plan has no ceiling."""

    remaining: Optional[int] = None
    """Deliveries left today, never below zero. ``None`` when there is no ceiling."""

    unlimited: bool = False
    """True when the plan has no daily ceiling."""

    resets_at: datetime
    """When the budget resets (UTC)."""

    resets_at_note: Optional[str] = None
    """Present only while something is paused, to say that the reset time is
    the budget's and not the pause's."""


class WebhookPausedSubscriptions(BaseModel):
    """Paused rules on the account. Always present, so zero needs no special case."""

    model_config = ConfigDict(extra="allow")

    count: int = 0
    """How many rules are paused and delivering nothing."""

    earliest_paused_at: Optional[datetime] = None
    """Start of the oldest pause still in force."""

    reasons: list[str] = Field(default_factory=list)
    """Distinct causes across the paused rules."""

    message: Optional[str] = None
    """What is paused and what clears it. Present only when something is paused."""


class WebhookLimits(BaseModel):
    """What the plan allows for webhooks and what is in use, from ``limits()``."""

    model_config = ConfigDict(extra="allow")

    plan: str
    """The plan webhook decisions are priced at (for example ``"pro"``)."""

    plan_label: Optional[str] = None
    """The plan's display name."""

    included: bool
    """Whether the plan has webhook delivery at all. False on Free."""

    preview_included: bool
    """Whether the estimate and the dry-run are available. True on every plan."""

    endpoints: WebhookLimitUsage
    """Endpoint cap and usage."""

    subscriptions: WebhookLimitUsage
    """Subscription cap and usage."""

    watched_addresses: WebhookLimitUsage
    """Watched wallet cap and usage."""

    deliveries_per_day: WebhookDeliveryBudget
    """Today's delivery budget."""

    paused_subscriptions: WebhookPausedSubscriptions
    """Paused rules, reported next to the budget because a paused rule does not
    restart when the budget resets."""

    notice: Optional[str] = None
    """Why the caps are zero, and what to do about it. Present only on a plan
    without webhook delivery."""


class WebhookPreviewWindow(BaseModel):
    """The window a preview vouches for.

    It can start later than the one asked for when a scan reached its row cap.
    """

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    from_: datetime = Field(alias="from")
    """Start of the window the answer covers. Named ``from_`` because ``from``
    is a Python keyword."""

    to: datetime
    """End of the window, which is the moment of the request."""


class WebhookPreviewOccurrence(BaseModel):
    """One occurrence a preview says would have been delivered."""

    model_config = ConfigDict(extra="allow")

    observed_at_estimate: datetime
    """The occurrence's own timestamp. A real delivery's ``observed_at`` is this
    plus the time it takes to see the occurrence."""

    data: dict[str, Any] = Field(default_factory=dict)
    """The occurrence body, the same ``data`` a delivery would carry."""


class WebhookDryRun(BaseModel):
    """Which occurrences a would-be subscription would have delivered, from ``dry_run()``."""

    model_config = ConfigDict(extra="allow")

    event_type: str
    """Event type that was evaluated."""

    window: WebhookPreviewWindow
    """The window the answer covers."""

    matched: int = 0
    """Occurrences that matched inside the window, before ``limit`` is applied."""

    truncated: bool = False
    """True when fewer occurrences are returned than matched, or a scan hit its
    row cap and the window was narrowed."""

    occurrences: list[WebhookPreviewOccurrence] = Field(default_factory=list)
    """Matches, newest first, at most ``limit``."""


class WebhookEstimateDayCount(BaseModel):
    """One 24 hour bin of an estimate."""

    model_config = ConfigDict(extra="allow")

    date: date
    """UTC date the bin ends on."""

    count: int
    """Occurrences that would have been delivered in the bin."""


class WebhookEstimateRung(BaseModel):
    """The daily rate the same configuration would have had at another threshold."""

    model_config = ConfigDict(extra="allow")

    value: float
    """Threshold on the primary metric."""

    per_day: float
    """Deliveries a day at that threshold, everything else unchanged."""


class WebhookEstimateDistribution(BaseModel):
    """Quantiles of the primary metric over the matched occurrences."""

    model_config = ConfigDict(extra="allow")

    n: int
    """Occurrences the quantiles are computed over."""

    p50: float
    """Median."""

    p90: float
    """90th percentile."""

    p99: float
    """99th percentile."""

    max: float
    """Largest value seen."""


class WebhookEstimateBasis(BaseModel):
    """How an estimate was produced."""

    model_config = ConfigDict(extra="allow")

    mode: str
    """``"exact"`` counted every occurrence, ``"sampled"`` scaled the counts
    from a capped scan (the note says by how much), and ``"replayed"`` re-ran a
    windowed rule over history at your own parameters."""

    note: Optional[str] = None
    """What qualifies the numbers, when anything does."""


class WebhookEstimate(BaseModel):
    """How often a would-be subscription would have fired, from ``estimate()``.

    Compare ``per_day_p50`` and ``per_day_max`` with the plan's daily delivery
    budget before turning a rule on.
    """

    model_config = ConfigDict(extra="allow")

    event_type: str
    """Event type that was evaluated."""

    window: WebhookPreviewWindow
    """The window the answer covers."""

    days: int
    """Days covered. Shorter than requested when the event type caps its own window."""

    total: int
    """Occurrences that would have been delivered across the window."""

    per_day: list[WebhookEstimateDayCount] = Field(default_factory=list)
    """One entry per day, oldest first, zero filled."""

    per_day_p50: float = 0.0
    """Median deliveries a day."""

    per_day_max: int = 0
    """Busiest day in the window."""

    primary_metric: Optional[str] = None
    """The metric the ladder and the distribution are about. ``None`` when the type has none."""

    ladder: list[WebhookEstimateRung] = Field(default_factory=list)
    """Daily rates at other thresholds, ascending. Empty without a primary metric."""

    distribution: Optional[WebhookEstimateDistribution] = None
    """Quantiles of the primary metric. ``None`` without a primary metric or a match."""

    sample: list[WebhookPreviewOccurrence] = Field(default_factory=list)
    """A sample of matches, newest first, in the dry-run's shape."""

    basis: WebhookEstimateBasis
    """How the estimate was produced."""
