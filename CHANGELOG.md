# Changelog

All notable changes to the `oxarchive` Python SDK are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and
this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.9.1] - Unreleased

### Added
- HIP-3 breadth above current UTC-session VWAP via
  `client.hyperliquid.hip3.breadth.current()` and cursor-paginated
  `.history()`; collection begins on 2026-08-28 and `value_pct` remains null
  when no instrument is eligible.
- Typed Hyperliquid core L4 replay frames: `l4_snapshot` is followed by
  ordered `l4_batch` events for `l4_diffs` and `l4_orders`. HIP-3, HIP-4, and
  Hyperliquid Spot L4 remain live-only.

### Changed
- Lighter WebSocket channels now support bounded historical replay without
  live subscriptions. Current Lighter data remains available through REST;
  live subscription calls fail fast with guidance to REST or replay.
- Projected forced-liquidation price-level endpoints refresh about every five
  minutes. This is a measured cadence, not an exact five-minute guarantee.

### Breaking
- Lighter `funding_rate` is now a fractional, non-annualized rate. Consumers
  that compensated for the former percent units must remove that conversion;
  do not apply a second percent conversion.

## [1.9.0] - 2026-08-22

### Added
- HIP-4 candle history at `client.hyperliquid.hip4.candles.history()` and its async equivalent.
- **Hyperliquid Spot candle history.** Added `client.spot.candles.history()` and `ahistory()` for `/v1/hyperliquid/spot/candles/{symbol}`. Coverage starts at `2025-03-22T10:50:22Z`; supported intervals are `1m`, `5m`, `15m`, `30m`, `1h`, `4h`, `1d`, and `1w`, with numeric timestamp-string cursor pagination and a 1,000-row page cap.

### Changed
- Coverage copy now states HIP-4 outcome-side OI at roughly 10-second cadence, Lighter L3 at 250 orders per side from March 5, 2026, and Lighter per-fill trade history from August 27, 2025.
- HIP-4 WebSocket docs now distinguish live trades/L4/settlement delivery from stored-replay-only L2 and OI while those live bridges are paused.
- Lighter L3 `depth` now means individual resting orders per side and is validated from 1 through 250.

## [1.8.0] - 2026-07-27

### Added
- **Liquidation levels**: `liquidations.levels()` / `alevels()` and
  `levels_history()` / `alevels_history()` on the Hyperliquid and HIP-3
  clients. Projected forced-liquidation levels computed from clearinghouse
  positions and margin state (snapshots approximately every five minutes,
  `at=` point-in-time reads, `side=` filter, cursor-paginated history with
  `summary=True` discovery mode). History retained from 2026-07-27.
- **Trigger levels**: `orders.trigger_levels()` and
  `trigger_levels_history()` (+ async variants): the pending stop-loss /
  take-profit map with 15-minute snapshot history.
- New pydantic models exported at package root: `LiquidationLevels`,
  `LiquidationLevelBucket`, `LiquidationLevelsHistoryItem`,
  `TriggerLevels`, `TriggerLevelBucket`, `TriggerLevelsHistoryItem`.
- **WebSocket L4 frames**: `on_l4_snapshot()` and `on_l4_batch()` handlers.
  Previously `l4_snapshot` / `l4_batch` server messages were silently
  dropped, so L4 channel subscribers received nothing.
- **`meta.coverage_from` / `meta.notice`**: empty responses for range windows
  that end before a symbol's coverage begins now carry the coverage start
  date and an advisory notice.

### Fixed
- `spot.trades.recent()` was blocked client-side claiming the endpoint does
  not exist; it exists and serves data. Unblocked. (The Hyperliquid perp
  mount's block remains: that backend really has no `/recent`.)
- `SpotTwapStatus` required `user` and modeled `executed_sz`/`executed_ntl`;
  the wire sends `user_address` and `executed_size`/`executed_notional`, so
  every spot TWAP call raised `ValidationError`. Fields renamed to the wire
  names, plus `size`, `block_number`, `block_time`, `started_at`.
- `SpotPair` rewritten to the actual wire shape (pair_index, name,
  is_canonical, token ids/names/decimals, base_token_address,
  deployer_fee_share, first/last timestamps). The old base/quote/asset_id/
  wire_name/sz_decimals/px_decimals fields never arrived, and `is_active`
  always defaulted to `True` regardless of state.

### Changed
- The server-side `/liquidations/{symbol}/levels` endpoints now serve
  projected forced-liquidation levels; the pending trigger-order map moved
  to `/orders/{symbol}/trigger-levels`.

## [1.7.1] - 2026-06-29

- Remove tier-gating language from doc comments, open-catalog rollout.

## [1.7.0] - 2026-05-06

### Added

- **Hyperliquid spot support.** New top-level `client.spot` namespace under `/v1/hyperliquid/spot`. Symbols are dashed canonical (`HYPE-USDC`, `PURR-USDC`); the server resolves dashed to wire format internally.
  - REST resources: `pairs` (list and detail), `orderbook` (current and history, plus `l4`, `l4/diffs`, `l4/history`), `trades` (start/end/user query), `orders.history` (Pro+ lifecycle events), `twap.by_symbol` and `twap.by_user`, `get_freshness` (per-table lag).
  - New types: `SpotPair`, `SpotTwapStatus`, `SpotTableFreshness`. All exported from `oxarchive`.
  - New client class: `SpotClient` exported from `oxarchive`.
- **Spot WebSocket channels.** `spot_orderbook`, `spot_trades`, `spot_twap` (Build+) and `spot_l4_diffs`, `spot_l4_orders` (Pro+, realtime only). Five new helpers each: `subscribe_spot_*` and `unsubscribe_spot_*`. The existing `on_orderbook` and `on_trades` typed callbacks now also fire for `spot_orderbook` and `spot_trades`, no fallback to `on_message` required.

### Notes

- Spot has no funding, no open interest, or liquidations. Candle history is served by `/v1/hyperliquid/spot/candles/{symbol}` from `2025-03-22T10:50:22Z` with a 1,000-row page cap; trades coverage goes back to 2025-03-22.
- Orderbook, L4, TWAP, and orders are live-only from 2026-05-05 (no historical backfill exists for these).
- Use `client.spot.pairs.list()` for discovery: there are 294 spot pairs covered.

## [1.6.0] - 2026-05-04

### Added

- **Real-time WebSocket support for liquidations.** Both `liquidations` (Hyperliquid) and `hip3_liquidations` (HIP-3 nodes) now stream live in addition to historical replay. Each item shares the trades wire shape (a fill row with `is_liquidation: true`).
  - New typed callback `OxArchiveWs.on_liquidations(handler)` decodes incoming frames into `Liquidation` records and invokes `handler(coin, [Liquidation, ...])`.
  - New helpers `subscribe_liquidations` / `unsubscribe_liquidations` and `subscribe_hip3_liquidations` / `unsubscribe_hip3_liquidations`.
- **HIP-4 outcome-market WebSocket channel helpers.**
  - New channels in `WsChannel`: `hip4_trades` (live + replay), `hip4_orderbook` and `hip4_open_interest` (stored replay; live bridges currently paused), plus `hip4_l4_diffs` and `hip4_l4_orders` (live only).
  - New helpers: `subscribe_hip4_orderbook`, `subscribe_hip4_trades`, `subscribe_hip4_open_interest`, `subscribe_hip4_l4_diffs`, `subscribe_hip4_l4_orders` (and matching `unsubscribe_*`).
  - WebSocket subscribes use the raw `#N` coin form in the JSON body.
- **HIP-4 settlement event.** New `WsOutcomeSettled` type and `OxArchiveWs.on_outcome_settled(handler)` callback. The server pushes `outcome_settled` once per `(outcome_id, side)` when a market resolves and proactively unsubscribes the client from every `hip4_*` channel for the settled coin. The SDK mirrors that locally so resubscribes after a reconnect do not try to re-arm a settled market.
- **HIP-4 REST: `by-slug` lookup.** New `client.hyperliquid.hip4.get_outcome_by_slug(slug)` (and `aget_outcome_by_slug`) hitting `/v1/hyperliquid/hip4/outcomes/by-slug/{slug}`. Accepts the per-outcome slug (`btc-above-78213-may-04-0600`) or a per-side slug (`btc-above-78213-yes-may-04-0600`); response includes `aggregated_oi` like `/outcomes/{outcome_id}`.
- **HIP-4 REST: `?slug=` filter on the list endpoint.** `list_outcomes(slug=...)` short-circuits to a one-item response and composes with `is_settled`.

### Changed

- **HIP-4 path encoding: bare numeric form is now the default.** Backend routes accept both `/v1/hyperliquid/hip4/orderbook/0` (bare) and `/v1/hyperliquid/hip4/orderbook/%230` (URL-encoded `#0`). Customers kept tripping on the percent-encoding requirement, so the SDK now sends the bare form. Callers can still pass either `"0"` or `"#0"` to the SDK; results are identical. WebSocket subscribes still use the raw `#N` form in the JSON body.
- `Hip4InstrumentsResource.get` and the per-side resources mounted on `Hip4Client` (orderbook, trades, open_interest, orders, l4_orderbook, l2_orderbook) all share the new normalization helper.
- `WsChannel` Literal extended with the five new HIP-4 channel names.
- README: new HIP-4 section under REST (`outcomes`, `by-slug`, `?slug=`, per-side instruments, paired OI), new HIP-4 channel table under WebSocket, and a worked `outcome_settled` handler example.

### Notes

- HIP-4 `mark_price` (returned on OI/summary/prices responses) is an **implied probability in `[0, 1]`**, not a USD price. Field name mirrors upstream Hyperliquid `markPx`.
- HIP-4 has no funding or liquidations. Candle history and outcome-side OI are served from May 2, 2026.
- Outcome detail (`get_outcome` / `get_outcome_by_slug`) returns `aggregated_oi` with `side0_open_interest_contracts`, `side1_open_interest_contracts`, `outcome_display_open_interest_contracts`, `paired_set_supply_contracts`, `side_supply_parity`, `currency`, `as_of`. The list endpoint omits `aggregated_oi`.
