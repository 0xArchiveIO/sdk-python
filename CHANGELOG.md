# Changelog

All notable changes to the `oxarchive` Python SDK are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and
this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.7.0] - 2026-05-06

### Added

- **Hyperliquid spot support.** New top-level `client.spot` namespace under `/v1/hyperliquid/spot`. Symbols are dashed canonical (`HYPE-USDC`, `PURR-USDC`); the server resolves dashed to wire format internally.
  - REST resources: `pairs` (list and detail), `orderbook` (current and history, plus `l4`, `l4/diffs`, `l4/history`), `trades` (start/end/user query), `orders.history` (Pro+ lifecycle events), `twap.by_symbol` and `twap.by_user`, `get_freshness` (per-table lag).
  - New types: `SpotPair`, `SpotTwapStatus`, `SpotTableFreshness`. All exported from `oxarchive`.
  - New client class: `SpotClient` exported from `oxarchive`.
- **Spot WebSocket channels.** `spot_orderbook`, `spot_trades`, `spot_twap` (Build+) and `spot_l4_diffs`, `spot_l4_orders` (Pro+, realtime only). Five new helpers each: `subscribe_spot_*` and `unsubscribe_spot_*`. The existing `on_orderbook` and `on_trades` typed callbacks now also fire for `spot_orderbook` and `spot_trades`, no fallback to `on_message` required.

### Notes

- Spot has no funding, no open interest, no liquidations, and no candles by design (perp-only constructs). Those endpoints are intentionally absent from `SpotClient`. `/v1/hyperliquid/spot/candles/{symbol}` returns 501.
- Trades coverage goes back to 2025-03-22. Orderbook, L4, TWAP, and orders are live-only from 2026-05-05 (no historical backfill exists for these).
- Use `client.spot.pairs.list()` for discovery: there are 294 spot pairs covered.

## [1.6.0] - 2026-05-04

### Added

- **Real-time WebSocket support for liquidations.** Both `liquidations` (Hyperliquid) and `hip3_liquidations` (HIP-3 nodes) now stream live in addition to historical replay. Each item shares the trades wire shape (a fill row with `is_liquidation: true`).
  - New typed callback `OxArchiveWs.on_liquidations(handler)` decodes incoming frames into `Liquidation` records and invokes `handler(coin, [Liquidation, ...])`.
  - New helpers `subscribe_liquidations` / `unsubscribe_liquidations` and `subscribe_hip3_liquidations` / `unsubscribe_hip3_liquidations`.
- **Full HIP-4 outcome-market WebSocket surface.**
  - New channels in `WsChannel`: `hip4_orderbook`, `hip4_trades`, `hip4_open_interest` (realtime + replay), `hip4_l4_diffs`, `hip4_l4_orders` (realtime only, Pro+).
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
- HIP-4 has no funding, no liquidations, and no candles by design (fully collateralized binary outcomes, no oracle feed). Those endpoints return 404.
- Outcome detail (`get_outcome` / `get_outcome_by_slug`) returns `aggregated_oi` with `side0_open_interest_contracts`, `side1_open_interest_contracts`, `outcome_display_open_interest_contracts`, `paired_set_supply_contracts`, `side_supply_parity`, `currency`, `as_of`. The list endpoint omits `aggregated_oi`.
