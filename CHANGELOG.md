# Changelog

All notable changes to the `oxarchive` Python SDK are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and
this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.13.0] - 2026-10-08

### Added
- The `mempool` WebSocket channel: signed Hyperliquid transactions as our
  Hyperliquid node receives them from its peers, before they are included in
  a block, for every Hyperliquid product. It is live only (`replay()` raises
  `ValueError` for it before sending), served only at
  `wss://stream.0xarchive.io/ws`, and included with the Pro, Scale and
  Enterprise plans. Every other channel stays on every plan.
- `subscribe_mempool(symbol=None)` and `unsubscribe_mempool(symbol=None)`.
  Without a symbol they cover every pending transaction; with one, only the
  actions that reference that market. `mempool` is the only channel whose
  symbol is optional.
- `on_mempool()` handler, receiving `(symbol, [MempoolItem, ...])`, with
  `symbol` set to `None` on the unfiltered stream. Mempool messages reach
  `on_message()` as `WsMempoolData`.
- Typed items: `MempoolItem` (`received_at`, `received_at_ms`, `symbols`,
  `action`, `nonce`, `vault_address`, `expires_after_ms`, `signature`) and
  `MempoolSignature`. `action` is kept exactly as signed, as a dict in the
  order sent.
- `oxarchive.websocket.STREAM_WS_URL` (`wss://stream.0xarchive.io/ws`). Pass
  it as `WsOptions(ws_url=...)` for a client that subscribes to `mempool`.
- `ws_endpoint` and `plans` on `WsChannelSpec` and `Capability`, mirroring
  the fields `/v1/capabilities` sets on the `mempool` row only. `None` means
  every endpoint and every plan.

## [1.12.0] - 2026-10-05

Builds on 1.11.0. Two venues, Hyperliquid and Lighter; Lighter now has two
deployments in the SDK, mainnet (`client.lighter`) and Robinhood Chain
(`client.rh_lighter`). The SDK adopts API version 2026-10-01: stable error
codes, `has_more` on every paged response, the symbol and venue of every
per-symbol response, `client.capabilities()`, and replay for every L4 and
full-depth channel.

### Upgrading from 1.7

The last release on PyPI before this one is 1.7.0; versions 1.7.1 to 1.11.0
were not published, and their changes are listed below. These are the
changes that can break code written against 1.7.0:

- Lighter `funding_rate` is a fractional, non-annualized rate, no longer a
  percent (1.10.0, Breaking). Remove any division by 100.
- Times without a time zone are read as UTC on every method, not as the
  machine's local time (this release, Fixed).
- Methods that called routes the API does not serve are removed, with their
  async versions: `client.hyperliquid.hip4.l2_orderbook`,
  `client.spot.orders.flow()` and `tpsl()`, and
  `client.hyperliquid.hip3.liquidations.by_user()` (this release, Removed).
- Parameters the API never applied raise `TypeError` instead of being
  ignored, such as `user` or `status` on `client.spot.orders.history()`
  (this release, Changed).
- WebSocket: `subscribe()` raises `ValueError` for a channel without live
  data (`candles`, `hip3_candles`, `hip4_orderbook`, `hip4_open_interest`,
  `spot_twap`), `replay()` raises it for a channel without replay, and
  Lighter replay messages have the live shapes (this release). `stream()`,
  `multi_stream()` and `stream_stop()` are deprecated because the server no
  longer streams bulk data (1.11.0, Deprecated).
- In an L4 snapshot from `l4_orderbook.get()`, each resting order's
  `timestamp` is an RFC 3339 string, with `timestamp_ms` beside it (this
  release, Added).
- `SpotPair` and `SpotTwapStatus` have the fields the API returns (1.8.0,
  Fixed).

### Added
- API version 2026-10-01. Every REST request, sync and async, sends
  `0xArchive-Version: 2026-10-01` (`oxarchive.API_VERSION`,
  `oxarchive.API_VERSION_HEADER`), and `OxArchiveWs` connects with
  `version=2026-10-01`. The SDK parses the shapes this version selects:
  - Data quality responses, the public coverage summary and
    `/v1/symbols` answer with the standard `{success, data, meta}` envelope;
    `client.data_quality.*` and `client.symbols.list()` return the same
    models as before.
  - Record times that were integer milliseconds are RFC 3339 strings with an
    integer companion in a field ending `_ms`. `CvdBucket`,
    `Hip3OracleExternalPrice`, `Hip3OracleDiscoveryBounds`,
    `LighterLiquidation` and `LighterLiquidationVolume` have `timestamp` as a
    UTC `datetime` and `timestamp_ms` as Unix milliseconds.
    `LiquidationLevels`, `LiquidationLevelsHistoryItem` and
    `TriggerLevelsHistoryItem` add `snapshot_ts_ms` (`snapshot_ts` is RFC
    3339). In an L4 snapshot from `l4_orderbook.get()` (a `dict`), each
    resting order's `timestamp` is an RFC 3339 string with `timestamp_ms`
    beside it; an unknown queue time is `None` with `timestamp_ms` 0.
  - Lighter and Robinhood Chain replay messages have the live shapes: books
    `{coin, time, levels}`, a trade message holds a list with one leg, and
    open interest and funding carry `{coin, ctx}`.
- Error codes. `OxArchiveError` exposes `error_code`, the stable code from the
  error body (for example `invalid_parameter`, `invalid_symbol`,
  `range_before_coverage`, `unsupported_for_venue`), with `status` (the HTTP
  status, the same value as `code`), `request_id`, `param`, `valid_values`
  and `details` (the whole error body, including route-specific fields such
  as `available_on`). A body without a code, such as a proxy error page, gets
  one derived from the status. The public set is `oxarchive.ERROR_CODES` and
  the `ErrorCode` type; `WEBSOCKET_ERROR_CODES` names the two WebSocket-only
  codes, `slow_consumer` and `endpoint_unsupported`. `WsError` has
  `error_code`. `str()` of an error includes the code.
- Pagination state. `CursorResponse.has_more` comes from `meta.has_more`; on
  a route that does not send it, it is true exactly when `next_cursor` is
  set. `ResponseMeta.has_more` is typed. The iterators (`cvd.iterate()` and
  the positions `iterate_*()` helpers, sync and async) stop when `has_more`
  is false.
- The symbol and venue of a response. `ResponseMeta.symbol` (the canonical
  public symbol) and `ResponseMeta.venue` (`Venue`: `hyperliquid`, `hip3`,
  `hip4`, `spot`, `lighter` or `rh-lighter`; `VENUES` lists them). Every
  paged method now returns `meta`. A record a method returns on its own
  (order book, funding rate, open interest, instrument, spot pair,
  freshness, summary, liquidation and trigger levels, HIP-3 oracle, HIP-4
  outcome and question, breadth snapshot, wallet classification and the
  data quality results) carries the response's meta as `response_meta`.
- `client.capabilities()` and `acapabilities()` for `GET /v1/capabilities`:
  one `Capability` per venue and datatype, with its REST routes, WebSocket
  channels, `live`, `replay`, `available_from`, `cadence`, `page_limit`,
  `intervals` and `notes`.
- `client.data_quality.status_coverage()` and `astatus_coverage()` for the
  public coverage summary at `/v1/status/coverage`.
- Filters the API now applies:
  - `side="buy"` or `side="sell"` (`TradeSide`) on `trades.list()`,
    `trades.history()` and `trades.recent()`, and their async versions, on
    every venue. The API filters before paging, so a full page holds `limit`
    matching trades.
  - `triggered` on `orders.history()` for Hyperliquid core, HIP-3 and HIP-4.
  - `depth` on `l2_orderbook.history()` (Hyperliquid core and HIP-3).
    `depth` on `orderbook.history()` applies on every venue, including HIP-3,
    HIP-4 and spot.
- Consistent verbs, as aliases of the existing methods:
  `trades.history()` and `ahistory()` (the same methods as `list()` and
  `alist()`), `client.spot.twap.history()` and `ahistory()` (`by_symbol()`
  and `aby_symbol()`), and `client.hyperliquid.hip4.get_price_history()` and
  `aget_price_history()` (`get_prices()` and `aget_prices()`). Every existing
  name keeps working.
- WebSocket replay for every L4 channel (`hip3_l4_diffs`, `hip3_l4_orders`,
  `hip4_l4_diffs`, `hip4_l4_orders`, `spot_l4_diffs`, `spot_l4_orders`, as
  well as `l4_diffs` and `l4_orders`) and for the full-depth L2 channels
  `orderbook_full` and `hip3_orderbook_full`. These replays are bulk: one
  `l4_snapshot` from the nearest checkpoint at or before `start`, then
  ordered `l4_batch` messages; `speed` is ignored, `replay.seek` is refused,
  and each replays on its own.
- `oxarchive.websocket.WS_CHANNELS`: one `WsChannelSpec` per channel (venue,
  datatype, `live`, `replay`, `bulk_replay`), mirroring `/v1/capabilities`,
  with `LIVE_CHANNELS`, `REPLAY_CHANNELS`, `BULK_REPLAY_CHANNELS` and
  `L4_REPLAY_CHANNELS`. `subscribe()` refuses a channel without live data
  (now also `candles`, `hip3_candles`, `hip4_orderbook`,
  `hip4_open_interest` and `spot_twap`), `replay()` a channel without
  replay (`ticker`, `all_tickers`, `spot_orderbook`, `spot_trades`,
  `spot_twap`), and `multi_replay()` also the bulk channels, each with
  `ValueError` before anything is sent. `spot_twap` is listed with neither
  live nor replay, since `/v1/capabilities` lists spot TWAP as REST only;
  its error (`REST_ONLY_ERROR`) says so.
- `OxArchiveWs.on_replay_data()`: every replayed record with its channel,
  `(channel, coin, timestamp, record)`. Lighter and Robinhood Chain records
  are decoded with the live parsers (`OrderBook`, `list[Trade]`,
  `LighterMarketContextUpdate`); `decode_lighter_payload()` applies the same
  decoding to any payload. `WsSubscribed.version`, `WsReplayStarted.version`
  and `WsReplayStarted.symbol` are typed.
- Lighter on Robinhood Chain: `client.rh_lighter` (`RhLighterClient`), served
  under `/v1/rh-lighter`. It has the same resources as `client.lighter` except
  the L3 order book and the L1 account resolver: `instruments`, `orderbook`,
  `trades` (`list()` canonical up to `meta.finalized_through`, `recent()`
  preliminary), `candles`, `open_interest`, `funding`, `liquidations`,
  `positions`, and `get_freshness()`, `get_summary()`, `get_price_history()`.
  Markets are USDG-quoted: perps use uppercase symbols (`BTC`), spot markets
  dashed symbols (`AAPL-USDG`). Trades and liquidations start at the venue
  launch, 2026-06-26 20:10:26 UTC; candles start 2026-06-26 20:10 UTC; order
  book, open interest and funding start 2026-08-22 18:43 UTC.
- Lighter liquidations on both deployments: `client.lighter.liquidations` and
  `client.rh_lighter.liquidations` with `history()` and `volume()` (and async
  `ahistory()` / `avolume()`), typed as `LighterLiquidation` and
  `LighterLiquidationVolume`. A row keeps both sides' account fields. On
  Robinhood Chain, rows from before live capture were backfilled from the
  venue's finalized export and have `source == "bucket"` and an empty
  `raw_json`; rows captured live have `source == "ws"` and the venue's raw
  JSON. Volume buckets carry `total_usd` and `count`.
- Account positions on four clients with the same method names:
  `client.hyperliquid.positions`, `client.hyperliquid.hip3.positions`,
  `client.lighter.positions` and `client.rh_lighter.positions`.
  - `get(key, timestamp=None, symbol=None)`: open positions now, or as of any
    instant (an exact hour serves the hourly snapshot; any other instant is
    reconstructed from the change log). Returns `WalletPositions`
    (`positions`, `account`, `account_seen`). On Lighter, `account` holds
    position aggregates only (totals, long/short value, `n_positions`).
  - `history(key, start, end)`, `changes(key, start, end)`: hourly position
    rows and the change log of every leg that moved a position.
  - `market(symbol, hour=None, side=None, min_value=None)`,
    `market_summary(symbol, start=None, end=None)`, `all(hour)`: every open
    position in a market (with `meta.totals`), long/short aggregates, and a
    bulk listing across markets at one hour.
  - `account(key)` and `account_history(key, start, end)`: the account
    summary now and hourly. On Hyperliquid and HIP-3 it is the clearinghouse
    summary (HIP-3 takes an optional `dex`); on Lighter and Robinhood Chain it
    holds position aggregates (totals, long/short value, `n_positions`).
    Lighter market methods take `include_system`.
  - `key` is a 0x address on Hyperliquid and HIP-3, and an integer account
    index on Lighter. `client.lighter.accounts.by_l1(l1_address)` resolves an
    L1 address to its account indices (Lighter mainnet only).
  - Cursor-following iterators: `iterate_history()`, `iterate_changes()`,
    `iterate_market()`, `iterate_market_summary()`, `iterate_all()`,
    `iterate_account_history()`, `client.lighter.accounts.iterate_by_l1()`,
    and `aiterate_*` async versions. Every method has an `a`-prefixed async
    version.
  - Typed models: `Position`, `PositionLeverage`, `PositionCumFunding`,
    `PositionChange`, `MarketPosition`, `MarketPositionsSummary`,
    `AccountSummary`, `WalletPositions`, `LighterL1Account`,
    `LighterL1Accounts`.
  - `client.data_quality.positions_freshness()` (and
    `apositions_freshness()`): one `PositionsFreshness` row per venue with
    the latest live and hourly snapshots, the live snapshot's age and
    quality, `stale`, `built_through` and `finalized_through`.
  - Coverage: Hyperliquid change log from 2025-05-25, HIP-3 from 2025-10-13,
    hourly history from 2026-06-07, live every 5 minutes; Lighter mainnet from
    2025-01-17 and Robinhood Chain from 2026-06-26, hourly, live every
    2 minutes. Position rows are billed like trades, 1,000 rows per credit;
    the account summary routes and `by_l1()` are billed at the per-request
    minimum.
- `ResponseMeta` and `CursorResponse.meta`: the response's `meta`, typed, with
  `finalized_through`, `requested_end`, `clamped_to`, `coverage_from`,
  `notice`, and the new optional fields `as_of`, `snapshot_ts`, `source`,
  `quality`, `stale`, `totals` and `built_through`. Set on every paged
  method. Unknown fields are kept. `trades.recent()` still returns a plain
  list, so the `preliminary_row_count` the API sends on the Lighter
  `/recent` response is not surfaced in this release.
- Live Lighter on Robinhood Chain WebSocket channels `rh_lighter_orderbook`,
  `rh_lighter_trades`, `rh_lighter_open_interest` and `rh_lighter_funding`,
  with the same message shapes as the mainnet `lighter_*` channels, served on
  `wss://api.0xarchive.io/ws`. `rh_lighter_orderbook` accepts `interval_ms`
  (100 to 5000, default one book per second). New helpers
  `subscribe_rh_lighter_orderbook()`, `subscribe_rh_lighter_trades()`,
  `subscribe_rh_lighter_open_interest()`, `subscribe_rh_lighter_funding()`
  and their `unsubscribe_*` counterparts, and handlers
  `on_rh_lighter_orderbook()`, `on_rh_lighter_trades()` and
  `on_rh_lighter_market_context()`. Robinhood Chain messages never reach the
  mainnet `on_lighter_*` handlers; without a dedicated handler, books and
  trades fall back to `on_orderbook()` and `on_trades()`.
- `rh_lighter_candles` for replay. All five `rh_lighter_*` channels support
  historical replay and multi-channel replay within their family.
- `RH_LIGHTER_LIVE_CHANNELS`, `RH_LIGHTER_REPLAY_ONLY_CHANNELS`,
  `RH_LIGHTER_REPLAY_CHANNELS`, `RH_LIGHTER_SUBSCRIPTION_ERROR` and
  `LIGHTER_BOOK_CHANNELS` in `oxarchive.websocket`.
- `orders.flow()` and `aflow()` take `cursor` (Hyperliquid, HIP-3 and HIP-4).
  The API pages order flow: a page holds the oldest `limit` buckets of the
  window, and `next_cursor` is set while more may follow. Pass it back as
  `cursor` with the same `start`, `end` and `interval` until it is `None`.
  Before this, a `cursor` keyword was accepted and silently dropped, so every
  call returned the first page.
- Webhooks: `client.webhooks` (`WebhooksResource`) covers all 21 operations
  under `/v1/webhooks`, each with an `a`-prefixed async version:
  `event_types()`, `limits()`; `list_endpoints()`, `create_endpoint()`,
  `delete_endpoint()`, `enable_endpoint()`, `rotate_secret()`,
  `test_endpoint()`; `list_deliveries()`, `redeliver()`;
  `list_subscriptions()`, `create_subscription()`, `update_subscription()`,
  `delete_subscription()`, `resume_subscription()`,
  `resume_all_subscriptions()`; `dry_run()`, `estimate()`;
  `list_addresses()`, `add_address()`, `delete_address()`. A subscription
  configuration is passed as `config`, a dict or a
  `WebhookSubscriptionConfig`. Subscriptions report their pause state
  (`status`, `pause_reason`, `pause_message`, suppressed counts), and a
  resume returns the missed window as `WebhookResumeGap`. `limits()`
  reports the plan's caps, today's delivery budget and the paused count.
  Webhook delivery needs a paid plan; `estimate()` and `dry_run()` are
  available on every plan.
- Webhook signature verification in `oxarchive.webhook_signature`:
  `WebhookVerifier`, `verify_webhook()`, `verify_webhook_signature()`,
  `parse_signature_header()`, `WebhookEvent`, `WebhookSignature`,
  `WebhookSignatureError` and the header name constants. It verifies the raw
  request bytes, accepts every `v1=` signature in the header (two during a
  secret rotation), enforces a replay window (5 minutes by default) and
  compares in constant time.
- Webhook models: `WebhookEventType` (with `WebhookEventTypeParam`,
  `WebhookEventTypeMetric`, `WebhookCostFloor`), `WebhookEndpoint`,
  `WebhookEndpointCreated`, `WebhookEndpointSecret`,
  `WebhookSubscriptionConfig`, `WebhookSubscriptionCondition`,
  `WebhookSubscription`, `WebhookSubscriptionResume`,
  `WebhookSubscriptionResumeAll`, `WebhookResumeGap`,
  `WebhookResumeReplayWindow`, `WebhookDelivery`, `WebhookDeliveryQueued`,
  `WebhookRedelivery`, `WebhookWatchedAddress`, `WebhookLimits`,
  `WebhookLimitUsage`, `WebhookDeliveryBudget`, `WebhookPausedSubscriptions`,
  `WebhookDryRun`, `WebhookEstimate`, `WebhookPreviewWindow`,
  `WebhookPreviewOccurrence`, `WebhookEstimateDayCount`,
  `WebhookEstimateRung`, `WebhookEstimateDistribution` and
  `WebhookEstimateBasis`. Every webhook model keeps unknown fields.
- Cumulative volume delta: `client.hyperliquid.cvd` and
  `client.hyperliquid.hip3.cvd` with `history()` (one page; pass
  `next_cursor` back unchanged with the same `start`, `end` and `interval`)
  and `iterate()`, which follows the cursor, plus `ahistory()` and
  `aiterate()`. Buckets are `CvdBucket`; intervals `1m` to `1w`
  (`CvdInterval`). `cumulative_delta` restarts on every page.
- HIP-3 oracle: `client.hyperliquid.hip3.oracle.external_price(symbol)` and
  `discovery_bounds(symbol)` (and `aexternal_price()`,
  `adiscovery_bounds()`), typed as `Hip3OracleExternalPrice` and
  `Hip3OracleDiscoveryBounds`.
- HIP-4 questions: `client.hyperliquid.hip4.questions.list()` (cursor paged)
  and `get(question_id)`, the flat helpers
  `client.hyperliquid.hip4.list_questions()` and `get_question()`, and their
  async versions, typed as `Hip4Question`.
- Wallet classification: `client.hyperliquid.wallets.classify()` and
  `client.hyperliquid.hip3.wallets.classify()` (and `aclassify()`), with
  every filter, sort and `limit`/`offset` paging, typed as
  `WalletClassification`, `ClassifiedWallet` and `WalletClassifyMetrics`.
  `date` takes a date, a `YYYY-MM-DD` string or a datetime (a datetime
  without a time zone is UTC).
- Hyperliquid core breadth: `client.hyperliquid.breadth` with `current()` and
  `history()` (and `acurrent()`, `ahistory()`), the same resource as HIP-3
  breadth, served from 2026-08-24. Core responses carry empty `namespaces`.
- The public symbol universe: `client.symbols.list()` and `alist()`, one
  `SymbolEntry` per market across every venue family, with data types and
  coverage dates.
- Full-depth L2 WebSocket channels `orderbook_full` (Hyperliquid core) and
  `hip3_orderbook_full` (HIP-3), with helpers `subscribe_orderbook_full()`,
  `subscribe_hip3_orderbook_full()` and their `unsubscribe_*` counterparts,
  and `FULL_DEPTH_L2_CHANNELS` in `oxarchive.websocket`. A subscription or a
  replay opens with an `l4_snapshot` of every price level, then `l4_batch`
  messages of changed levels, delivered to `on_l4_snapshot()` and
  `on_l4_batch()`. Stored full-depth history is also on REST
  `l2_orderbook.history()` and `diffs()`.
- `client.lighter.l3_orderbook.get()` and `history()` take `account`.
- The package ships a `py.typed` marker (PEP 561), so type checkers read its
  annotations. The `Typing :: Typed` classifier was already declared.

### Changed
- The venue is named "Lighter" throughout docstrings, messages and the
  README (was "Lighter.xyz").
- `client.hyperliquid.trades.recent()` still refuses before sending (the API
  does not serve it for Hyperliquid core), now with
  `error_code == "unsupported_for_venue"` and a message that names
  `trades.history()` and the venues that serve `recent()`.
- HIP-3, HIP-4 and spot L4 channels are no longer refused by `replay()`.
  `L4_LIVE_ONLY_CHANNELS` is empty and `L4_LIVE_ONLY_ERROR` is no longer
  raised; both are deprecated and kept so imports keep working.
- Docstrings and the README list live and replay per channel as
  `/v1/capabilities` does: `hip3_open_interest` and `hip3_funding` stream
  live as well as replay; `hip3_candles`, `hip4_orderbook` and
  `hip4_open_interest` are replay-only; `spot_twap` neither streams nor
  replays.
- `subscribe_hip4_orderbook()`, `subscribe_hip4_open_interest()` and
  `subscribe_spot_twap()` raise `ValueError` before anything is sent. The
  server accepts these subscriptions but sends no data on them: HIP-4 order
  book and open interest replay only (follow the live HIP-4 book on
  `hip4_l4_diffs`), and spot TWAP statuses are served over REST only
  (`client.spot.twap`).
- `WsChannel` includes the five `rh_lighter_*` channels, `orderbook_full` and
  `hip3_orderbook_full`. Before, the acknowledgement, snapshot and batch
  messages of the two full-depth channels failed to parse.
- `rh_lighter_candles` raises `ValueError` with `RH_LIGHTER_SUBSCRIPTION_ERROR`
  on a live subscribe, like the other replay-only Lighter channels.
- `interval_ms` is accepted on `rh_lighter_orderbook` as well as
  `lighter_orderbook`. The out-of-range error names the channel it was
  passed for.
- Data quality docstrings list every venue scope: `hyperliquid`, `hip3`,
  `hip4`, `spot`, `lighter` and `rh-lighter`.
- `LighterClient` shares its resources with `RhLighterClient` through a common
  base class; its paths and behavior are unchanged.
- Parameters the API never applied are removed, and passing one now raises
  `TypeError` before anything is sent instead of returning unfiltered data:
  `user`, `status`, `order_type` and `triggered` on
  `client.spot.orders.history()` (core, HIP-3 and HIP-4 order history keep
  them); `depth` on `l4_orderbook.history()` and
  `lighter.l3_orderbook.history()` (it still applies to `get()`); and
  `granularity` on `lighter.l3_orderbook.history()`.
- `client.hyperliquid.hip3.breadth.history()` and `ahistory()` accept
  `interval="1m"`. The API serves 1-minute buckets on breadth, open
  interest, funding, price and liquidation-volume history for every venue.
  The other methods already pass `interval` through unchanged.
- The order-flow docstring and README list the buckets the API serves: `1m`
  (the default), `5m`, `15m` and `1h`. The docstring used to suggest `4h` and
  `1d`, which the API refuses.

### Removed
- Methods that called routes the API does not serve, so every call failed
  with a 404:
  - `client.hyperliquid.hip4.l2_orderbook` (`get()`, `history()`,
    `diffs()` and their async versions). HIP-4 has no full-depth L2 route;
    use `hip4.orderbook` and `hip4.l4_orderbook`.
  - `client.hyperliquid.hip4.orders.trigger_levels()` and
    `trigger_levels_history()`.
  - `client.spot.orders.flow()`, `tpsl()`, `trigger_levels()` and
    `trigger_levels_history()`. Spot serves order history only.
  - `client.hyperliquid.hip3.liquidations.by_user()`. The per-user route
    exists for Hyperliquid core only.
- The async versions of those methods go with them. The affected resources
  are now `Hip4OrdersResource`, `SpotOrdersResource` and
  `Hip3LiquidationsResource`; Hyperliquid core and HIP-3 keep
  `OrdersResource`, and Hyperliquid core keeps `LiquidationsResource`.

### Fixed
- `import oxarchive` raised `TypeError` on Python 3.9, which the package
  declares as supported. Two fields of `SymbolDataTypeCoverage`
  (`historical_coverage` and `cadence`) used the `X | None` annotation
  syntax, which Python 3.9 cannot evaluate. They use `Optional` now, and the
  test suite passes on Python 3.9.
- `hip4.outcomes.get_by_slug()` URL-encodes the slug. Slugs with spaces,
  colons, `#` or `/` reached the wrong route before.
- `trades.list()` and `alist()` send `cursor` back exactly as the API
  returned it. A trades cursor is an opaque string such as
  `"1790640000578_218303497631402"` (Lighter adds a third part), and it was
  converted as if it were a timestamp, so asking for the second page raised
  `ValueError` or sent a different cursor. Integer and datetime cursors are
  still accepted.
- `CoinFreshness.funding` is optional. HIP-4 has no funding, and
  `client.hyperliquid.hip4.get_freshness()` raised a validation error on
  every response.
- `data_quality.symbol_coverage()` and `asymbol_coverage()` send the symbol
  as given, URL-encoded as one path segment. They upper-cased it, which
  turned case-sensitive HIP-3 symbols such as `km:US500` into a symbol
  with no data, and they did not encode the `#` of HIP-4 symbols, which cut
  the path short.
- `SpotTableFreshness` has the shape the API returns: `symbol`, `coin`,
  `exchange`, `measured_at`, and `orderbook`, `trades`, `l4_diffs`,
  `l4_checkpoints`, `orders` and `twap` as `DataTypeFreshness`. Its
  `tables` field was never filled; `tables` is now a property that returns
  the datasets present.
- Times without a time zone are UTC on every method. Before, a naive
  `datetime` and an ISO string without an offset (`"2026-09-01"`,
  `"2026-09-01T00:00:00"`) were read as the machine's local time, so the
  same call asked for a different window on machines in different time
  zones. A date alone is now midnight UTC and an offset-less date-time is
  UTC. A naive `datetime.now()` is local wall-clock time; for the current
  time pass an aware datetime such as `datetime.now(timezone.utc)`. Every
  resource now converts times with one shared helper, and a value that is
  not a timestamp raises `ValueError` instead of being dropped from the
  request.

### Documentation
- README sections on the API version, pagination with `has_more`, response
  metadata, capabilities and error codes; the trades, orders, L2, L3, L4 and
  WebSocket replay sections describe the filters and replays above. The
  channel tables mirror `/v1/capabilities`.
- The README's coverage table gives each dataset's first served instant on
  every venue, as `/v1/capabilities` reports it, and the docstrings give the
  same dates. It replaces month-only dates (Hyperliquid "April 2023+", HIP-3
  "February 2026+", HIP-4 "May 2026+", spot TWAP "May 2026"), lists
  Hyperliquid liquidations from 2025-12-22 (was "May 2025+"), and corrects
  the spot L4 start (2026-05-05 22:57 UTC; PURR-USDC from 2026-03-11 01:03
  UTC) and the spot candle start (2025-03-22 10:50 UTC).
- The Quick Start runs as pasted on any plan: it reads an active HIP-3
  market (`xyz:TSLA`), finds a real wallet for the positions call instead of
  a placeholder address, and reads the last hour of order book history.
- Examples read recent windows (the last hour, day or week), which every
  plan can reach, instead of fixed dates. Several of those dates fell before
  the dataset's coverage (candles, the Lighter order book, L2, L3 and L4,
  order history and liquidations) or outside the Free plan's 30-day history.
  HIP-4 examples find an open outcome instead of a settled one.
- The Lighter tick-level example uses `orderbook.history_tick()`.
  `orderbook.history()` returns snapshots and cannot parse tick data, and its
  docstring now says so.
- Market counts are no longer pinned; `client.rh_lighter.instruments.list()`
  and `client.spot.pairs.list()` return the current sets.
- The HIP-3 coin table is removed, since builders list and delist markets;
  call `client.hyperliquid.hip3.instruments.list()` for the current set.
- Documentation links point at docs.0xarchive.io.
- The breadth `history()` docstring says `start` defaults to 24 hours before
  now, as the API applies it, rather than 24 hours before `end`.
- The README's order-flow example pages a full day at `1m`, following
  `next_cursor` until it is `None`, and the `flow()` docstring describes
  paging.
- A README section on webhooks: plan limits, pauses and resumes, the event
  catalog, configuration, previews, verifying deliveries, secret rotation and
  retries.
- README sections for cumulative volume delta, the HIP-3 oracle, HIP-4
  questions, wallet classification, the symbol universe and the full-depth L2
  WebSocket channels.

## [1.11.0] - 2026-09-25

Versions 1.7.1, 1.8.0, 1.9.0, 1.9.1 and 1.10.0 were not published to PyPI.
This release includes their changes, listed in the sections below. The last
release on PyPI is 1.7.0, so upgrading from PyPI goes straight from 1.7.0 to
1.11.0.

### Added
- Live Lighter WebSocket subscriptions for `lighter_orderbook`,
  `lighter_trades`, `lighter_open_interest`, and `lighter_funding` on
  `wss://api.0xarchive.io/ws` (the client default). New helpers
  `subscribe_lighter_orderbook()`, `subscribe_lighter_trades()`,
  `subscribe_lighter_open_interest()`, `subscribe_lighter_funding()` and their
  `unsubscribe_*` counterparts.
- `interval_ms` keyword on `subscribe()`, `subscribe_async()` and
  `subscribe_lighter_orderbook()`. Live Lighter books default to one per
  second; pass 100 to 5000 to choose the rate. Each book sent is one metered
  message. It is accepted on `lighter_orderbook` only, must be an integer, is
  checked before anything is sent, and is re-sent on reconnect.
- Live Lighter subscriptions are tracked by the uppercase symbol, matching the
  server, so subscribing as `btc` and unsubscribing as `BTC` removes the
  subscription and it is not restored on reconnect.
- `on_lighter_orderbook()`, `on_lighter_trades()` and
  `on_lighter_market_context()` handlers. The first two take precedence over
  `on_orderbook()` and `on_trades()` for Lighter messages, so Lighter `BTC`
  is not mixed up with Hyperliquid `BTC`; without them, Lighter books and
  trades still reach the generic handlers.
- Typed live payloads: `LighterLiveTrade` (one trade leg, with the Lighter
  account index in `users`) and `LighterMarketContext` /
  `LighterMarketContextUpdate` (the message shared by `lighter_open_interest`
  and `lighter_funding`). Live books decode to the existing `OrderBook`.
- `Trade.account_index`: the Lighter account index of a fill's owner, set on
  live Lighter trade legs and on Lighter REST trades.
- `symbol` on `WsSubscribed`, `WsUnsubscribed` and `WsData`.
- `LIGHTER_LIVE_CHANNELS`, `LIGHTER_REPLAY_ONLY_CHANNELS` and the
  `LIGHTER_BOOK_INTERVAL_*` constants in `oxarchive.websocket`.

### Changed
- Live subscribe calls no longer raise for the four live Lighter channels.
  `lighter_candles` and `lighter_l3_orderbook` remain replay-only and still
  raise `ValueError` with `LIGHTER_SUBSCRIPTION_ERROR`, whose text now names
  those two channels.
- Live Lighter trade legs decode with their own mapping instead of the
  Hyperliquid one: `users` becomes `Trade.account_index` (not
  `maker_address`), and `order_id`, `crossed` and `start_position` are kept.
  Each trade arrives as two legs sharing `trade_id`; `fee`, `fee_token`,
  `closed_pnl` and `direction` are `None` in live messages. Live trades are
  preliminary; `client.lighter.trades.list()` serves the reconciled record.
- Replay of all six Lighter channels is unchanged and keeps its historical
  row shapes, which differ from the live messages.

### Deprecated
- `OxArchiveWs.stream()`, `multi_stream()` and `stream_stop()`. The server has
  discontinued WebSocket bulk streaming and answers these requests with an
  error message instead of data. Each call now emits a `DeprecationWarning`.
  For large dataset downloads, use the S3 Parquet bulk export at
  https://0xarchive.io/data. The `on_batch()`, `on_stream_start()`,
  `on_stream_progress()` and `on_stream_complete()` handler setters and the
  bulk stream message models are deprecated with them.

### Fixed
- The README and the `WsChannel` docstring now list Hyperliquid
  `open_interest` and `funding` as available for live subscription as well as
  replay.

## [1.10.0] - 2026-09-23

Versions 1.8.0, 1.9.0 and 1.9.1 are not available on PyPI. This release
includes all of their changes; upgrade from 1.7.0 straight to 1.10.0.

### Added
- HIP-3 breadth above current UTC-session VWAP via
  `client.hyperliquid.hip3.breadth.current()` and cursor-paginated
  `.history()`; collection begins on 2026-08-28 and `value_pct` remains null
  when no instrument is eligible. History accepts `5m`, `15m`, `30m`, `1h`,
  `4h`, and `1d` downsampling intervals.
- Typed Hyperliquid core L4 replay frames: `l4_snapshot` is followed by
  ordered `l4_batch` events for `l4_diffs` and `l4_orders`. HIP-3, HIP-4, and
  Hyperliquid Spot L4 remain live-only.

### Changed
- Trade `fee`, `closed_pnl` and `start_position` are now returned as `"0"`
  when the venue recorded a zero, instead of being omitted. A missing value
  now means the source did not record it (for example fills from 2025-03-22 to
  2025-05-25), never zero. This is a server-side change and applies to every
  SDK version.
- HIP-3 and HIP-4 trades now include `fee`, `fee_token`, `closed_pnl` and
  `start_position`.
- Correct Lighter per-fill trade history to the observed global floor of
  January 17, 2025; exact starts vary by market. This supersedes the August
  floor documented in the earlier release notes below.
- Lighter WebSocket channels now support bounded historical replay without
  live subscriptions. Current Lighter data remains available through REST;
  live subscription calls fail fast with guidance to REST or replay.
- Projected forced-liquidation price-level endpoints refresh about every five
  minutes. This is a measured cadence, not an exact five-minute guarantee.

### Fixed
- Lighter symbols are encoded as a single path segment in every resource and
  convenience method, sync and async.

### Breaking
- Lighter `funding_rate` is now a fractional, non-annualized rate. Consumers
  that compensated for the former percent units must remove that conversion;
  do not apply a second percent conversion.

## [1.9.1] - 2026-08-31

### Changed
- Documented the Free plan history window: Free includes every market, route,
  schema, and served depth, with history limited to the most recent rolling
  30 days and a maximum 30-day span per request or replay. Build and above
  keep the full retained archive. Plans gate capacity and Free's 30-day
  history window, not route families, schemas, or served depth.

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
