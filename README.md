# oxarchive

[![PyPI version](https://img.shields.io/pypi/v/oxarchive.svg)](https://pypi.org/project/oxarchive/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)

Python client for 0xArchive market data in notebooks, research scripts, and data pipelines.

0xArchive is granular market data infrastructure for two venues: Hyperliquid and Lighter. Hyperliquid includes core perps, HIP-3 builder perps, HIP-4 outcome markets, and Hyperliquid Spot. HIP-3, HIP-4, and Spot live under the Hyperliquid namespace (`/v1/hyperliquid/hip3`, `client.hyperliquid.hip3`, etc.). Lighter has two deployments: mainnet (`/v1/lighter`, `client.lighter`) and Robinhood Chain (`/v1/rh-lighter`, `client.rh_lighter`). Account positions are available on Hyperliquid, HIP-3, and both Lighter deployments.

Use the Python SDK when the workflow already lives in Python and you want typed REST helpers, async support, WebSocket support, pagination, and reconstruction utilities before moving into a larger pipeline.

## Installation

```bash
pip install oxarchive
```

For WebSocket support:

```bash
pip install oxarchive[websocket]
```

## Quick Start

```python
from datetime import datetime, timedelta, timezone

from oxarchive import Client

client = Client(api_key="0xa_your_api_key")

# First successful call: Hyperliquid BTC order book
hl_orderbook = client.hyperliquid.orderbook.get("BTC")
print(f"Hyperliquid BTC mid price: {hl_orderbook.mid_price}")

# Lighter uses its own venue client
lighter_orderbook = client.lighter.orderbook.get("BTC")
print(f"Lighter BTC mid price: {lighter_orderbook.mid_price}")

# Lighter on Robinhood Chain: the second Lighter deployment (USDG-quoted)
rh_orderbook = client.rh_lighter.orderbook.get("AAPL-USDG")
print(f"Robinhood Chain AAPL-USDG mid price: {rh_orderbook.mid_price}")

# Hyperliquid HIP-3 builder perps stay under client.hyperliquid.hip3.
# Coins are case-sensitive and carry the builder prefix.
hip3_instruments = client.hyperliquid.hip3.instruments.list()
hip3_orderbook = client.hyperliquid.hip3.orderbook.get("xyz:TSLA")
hip3_trades = client.hyperliquid.hip3.trades.recent("xyz:TSLA", limit=10)
hip3_funding = client.hyperliquid.hip3.funding.current("xyz:TSLA")
hip3_oi = client.hyperliquid.hip3.open_interest.current("xyz:TSLA")
print(f"xyz:TSLA mid: {hip3_orderbook.mid_price}, funding: {hip3_funding.funding_rate}")

# Hyperliquid spot pairs live under client.spot. Symbols are dashed canonical.
spot_pairs = client.spot.pairs.list()
spot_orderbook = client.spot.orderbook.get("HYPE-USDC")
print(f"HYPE-USDC mid: {spot_orderbook.mid_price}")

# Account positions: the largest open BTC position, then everything its wallet holds
largest = client.hyperliquid.positions.market("BTC", limit=1).data[0]
positions = client.hyperliquid.positions.get(largest.user_address)
for p in positions.data.positions:
    print(p.symbol, p.side, p.size, p.unrealized_pnl)

# Order book history for the last hour (every plan reads the most recent 30 days)
now = datetime.now(timezone.utc)
history = client.hyperliquid.orderbook.history(
    "ETH",
    start=now - timedelta(hours=1),
    end=now,
    limit=100,
)
print(f"{len(history.data)} ETH snapshots; more pages: {history.has_more}")
```

## Choose Your Next Path

| Need | Link |
| --- | --- |
| First authenticated route | [Quick Start](https://docs.0xarchive.io/quickstart) |
| SDK install and route docs | [SDK docs](https://docs.0xarchive.io/sdks) |
| Claude Code, ChatGPT Codex, and coding-agent workflows | [AI Clients](https://docs.0xarchive.io/ai-clients) |
| File-based historical pulls | [Data Catalog](https://www.0xarchive.io/data) |
| Route contract and machine context | [OpenAPI](https://www.0xarchive.io/openapi.json), [llms.txt](https://www.0xarchive.io/llms.txt) |
| Plans and limits | [Pricing](https://www.0xarchive.io/pricing) |

## Data Coverage

First served instant of each dataset, as `client.capabilities()` reports it (times are UTC):

| Venue | Coverage | Notes |
| --- | --- | --- |
| Hyperliquid | Order book from 2023-04-15; trades from 2023-04-15 03:31; funding, open interest and price history from 2023-05-20 02:50; candles from 2025-03-22 12:00; liquidations from 2025-12-22; L4, order history and full-depth L2 from 2026-03-11 01:03 | Core perpetuals. |
| Hyperliquid HIP-3 | Price history from 2025-10-13 12:12; trades from 2025-10-13 12:24; candles and liquidations from 2025-12-22; order book from 2026-02-16 16:57; funding and OI from 2026-02-16 17:03; L4, order history and full-depth L2 from 2026-03-11 01:03 | Builder perps; funding and OI update at roughly 10 seconds. |
| Hyperliquid HIP-4 | L4 and order history from 2026-05-02 07:47; trades and candles from 2026-05-02 08:00; order book, outcome-side OI and price history from 2026-05-02 16:51 | Outcome markets; OI updates at ~10s. No funding or liquidations. |
| Hyperliquid Spot | Candles from 2025-03-22 10:50; trades from 2025-03-22 10:50:22; TWAP from 2026-05-05 13:05; order book from 2026-05-05 19:56; L4 from 2026-05-05 22:57 (PURR-USDC from 2026-03-11 01:03), with REST order history reaching back further | Dashed canonical symbols (`HYPE-USDC`, `PURR-USDC`); `client.spot.pairs.list()` lists the pairs. Candle intervals are 1m/5m/15m/30m/1h/4h/1d/1w with a 1,000-row page cap and numeric timestamp-string cursors; pass each `next_cursor` back unchanged. No funding/OI/liquidations. |
| Lighter | Trades from 2025-01-17 08:43; candles from 2025-08-01; funding, OI and price history from 2025-08-25 15:28; order book from 2026-01-29 02:13; L3 from 2026-03-05 03:33; liquidations from 2026-06-10 | Exact starts vary by market. Maker/taker trade context; L3 caps at 250 orders per side; funding/OI update at ~10s. |
| Lighter on Robinhood Chain | Trades and liquidations from 2026-06-26 20:10:26 UTC (venue launch); candles from 2026-06-26 20:10; order book, OI, funding and price history from 2026-08-22 18:43 | The second Lighter deployment: USDG-quoted perps (`BTC`) and spot markets (`AAPL-USDG`); `client.rh_lighter.instruments.list()` lists them. No L3. |
| Account positions | Hyperliquid change log from 2025-05-25, HIP-3 from 2025-10-13, hourly history from 2026-06-07; Lighter mainnet from 2025-01-17, Robinhood Chain from 2026-06-26 | Live snapshots every 5 minutes (Hyperliquid, HIP-3) or 2 minutes (Lighter). See [Account Positions](#account-positions). |

`client.capabilities()` returns the first served instant of every datatype on every venue, and `client.symbols.list()` the coverage of each symbol, so a market listed later starts later. See [Capabilities](#capabilities). Free plans read the most recent 30 days of these datasets.

## Async Support

All methods have async versions prefixed with `a`:

```python
import asyncio
from oxarchive import Client

async def main():
    client = Client(api_key="0xa_your_api_key")

    # Async get (Hyperliquid)
    orderbook = await client.hyperliquid.orderbook.aget("BTC")
    print(f"BTC mid price: {orderbook.mid_price}")

    # Async get (Lighter)
    lighter_ob = await client.lighter.orderbook.aget("BTC")

    # Don't forget to close the client
    await client.aclose()

asyncio.run(main())
```

Or use as async context manager:

```python
async with Client(api_key="0xa_your_api_key") as client:
    orderbook = await client.hyperliquid.orderbook.aget("BTC")
```

## Configuration

```python
client = Client(
    api_key="0xa_your_api_key",           # Required (or via OXARCHIVE_API_KEY env var)
    base_url="https://api.0xarchive.io", # Optional
    timeout=30.0,                         # Optional, request timeout in seconds (default: 30.0)
)
```

If ``api_key`` is omitted, the SDK falls back to the ``OXARCHIVE_API_KEY``
environment variable.

```python
# OXARCHIVE_API_KEY=0xa_your_api_key python script.py
client = Client()
```

### API Version

Every request sends `0xArchive-Version: 2026-10-01` (`oxarchive.API_VERSION`), and WebSocket connections select the same version. The version fixes the response shapes the SDK parses: every route answers with the `{success, data, meta}` envelope, record times are RFC 3339 strings with an integer companion in fields ending `_ms`, errors carry a stable `error_code`, and Lighter replay messages have the live shapes. The API echoes the version in the `0xArchive-Version` response header.

## Pagination

Paged methods return a `CursorResponse` with `data`, `has_more`, `next_cursor` and `meta`. While `has_more` is `True`, pass `next_cursor` back unchanged as `cursor`, with the other arguments unchanged. Stop when `has_more` is `False`: a page can be short, or even empty, and still not be the last, so stop on `has_more` rather than on the page size.

```python
from datetime import datetime, timedelta, timezone

end = datetime.now(timezone.utc)
start = end - timedelta(hours=1)

page = client.hyperliquid.trades.history("BTC", start=start, end=end, limit=1000)
trades = list(page.data)
while page.has_more:
    page = client.hyperliquid.trades.history(
        "BTC", start=start, end=end, limit=1000, cursor=page.next_cursor
    )
    trades.extend(page.data)
```

The iterators (`cvd.iterate()`, `positions.iterate_history()` and the other `iterate_*` helpers) follow the cursor for you and stop when `has_more` is `False`.

## Response Metadata

`CursorResponse.meta` is the response's `meta`: `request_id`, `count`, `has_more`, and on per-symbol routes `symbol` (the canonical public symbol) and `venue` (`"hyperliquid"`, `"hip3"`, `"hip4"`, `"spot"`, `"lighter"` or `"rh-lighter"`). A record that a method returns on its own, such as an order book, a funding rate, an instrument or a market summary, carries the same meta as `response_meta`.

```python
book = client.hyperliquid.hip3.orderbook.get("xyz:TSLA")
print(book.response_meta.venue, book.response_meta.symbol)  # hip3 xyz:TSLA

page = client.spot.trades.history("HYPE-USDC", start=start, end=end)
print(page.meta.venue, page.meta.symbol, page.meta.request_id)
```

Methods that return a raw `dict` (the full-depth L2, L3 and L4 snapshots) or a plain list do not carry it.

## Capabilities

`client.capabilities()` lists what each venue serves, one `Capability` per venue and datatype: the REST routes and WebSocket channels, whether the datatype streams live (`live`) and replays (`replay`), the first served instant (`available_from`), its cadence, the largest page (`page_limit`) and the accepted intervals. The route needs no API key and costs no credits.

```python
rows = client.capabilities()
for row in rows:
    if row.venue == "spot":
        print(row.datatype, row.live, row.replay, row.available_from, row.page_limit)

replayable = {channel for row in rows if row.replay for channel in row.ws_channels}

# Async version
rows = await client.acapabilities()
```

Per-symbol coverage is on `client.symbols.list()`. The WebSocket client checks subscriptions and replays against the same table (see [Available Channels](#available-channels)).

## REST API Reference

All examples use `client.hyperliquid.*` but the same methods are available on `client.lighter.*` for Lighter data.

The examples read these recent windows, which every plan can reach (Free reads the most recent 30 days, at most 30 days per request):

```python
from datetime import datetime, timedelta, timezone

now = datetime.now(timezone.utc)
hour_ago = now - timedelta(hours=1)
day_ago = now - timedelta(days=1)
week_ago = now - timedelta(days=7)
```

### Order Book

```python
# Get current order book (Hyperliquid)
orderbook = client.hyperliquid.orderbook.get("BTC")

# Get current order book (Lighter)
orderbook = client.lighter.orderbook.get("BTC")

# Get order book at specific timestamp
historical = client.hyperliquid.orderbook.get("BTC", timestamp=day_ago)

# Get with limited depth
shallow = client.hyperliquid.orderbook.get("BTC", depth=10)

# Get historical snapshots (start and end are required)
history = client.hyperliquid.orderbook.history(
    "BTC",
    start=hour_ago,
    end=now,
    limit=1000,
    depth=20  # Price levels per side
)

# HIP-3 order book (case-sensitive coins)
hip3_ob = client.hyperliquid.hip3.orderbook.get("xyz:TSLA")
hip3_history = client.hyperliquid.hip3.orderbook.history("xyz:TSLA", start=hour_ago, end=now)

# Async versions
orderbook = await client.hyperliquid.orderbook.aget("BTC")
history = await client.hyperliquid.orderbook.ahistory("BTC", start=..., end=...)
hip3_ob = await client.hyperliquid.hip3.orderbook.aget("xyz:TSLA")
```

#### Orderbook Depth

The `depth` parameter is route-specific. Hyperliquid-family native L2 is capped at 20 levels per side. Lighter native L2 includes all served levels, and Lighter L3 is capped at 250 orders per side. `depth` applies to `get()` and to `history()` on every venue (Hyperliquid core, HIP-3, HIP-4, spot and Lighter), and to the full-depth `l2_orderbook.get()` and `l2_orderbook.history()`.

**Note:** Hyperliquid native L2 source data contains 20 levels per side. Dedicated L2 routes derived from L4 return all served levels where supported. Lighter native L2 also includes all served levels; Lighter L3 returns up to 250 individual resting orders per side.

#### Lighter Orderbook Granularity

Lighter order book history (mainnet and Robinhood Chain) supports a `granularity` parameter for different data resolutions. `history()` returns snapshots at `checkpoint`, `30s`, `10s` and `1s`; tick-level data (a checkpoint plus raw deltas) comes from `history_tick()` and the other methods under [Orderbook Reconstruction](#orderbook-reconstruction).

| Granularity | Interval | Credit Multiplier |
|-------------|----------|-------------------|
| `checkpoint` | ~60s | 1x |
| `30s` | 30s | 2x |
| `10s` | 10s | 3x |
| `1s` | 1s | 10x |
| `tick` | tick-level | 20x |

```python
# Get Lighter orderbook history with 10s resolution
history = client.lighter.orderbook.history(
    "BTC",
    start=hour_ago,
    end=now,
    granularity="10s"
)

# Get 1-second resolution
history = client.lighter.orderbook.history(
    "BTC",
    start=hour_ago,
    end=now,
    granularity="1s"
)

# Tick-level data: a checkpoint plus raw deltas
tick_data = client.lighter.orderbook.history_tick(
    "BTC",
    start=hour_ago,
    end=now,
)
```

**Note:** The `granularity` parameter is ignored for Hyperliquid orderbook history.

#### Orderbook Reconstruction

For tick-level data, the SDK provides client-side orderbook reconstruction. This efficiently reconstructs full orderbook state from a checkpoint and incremental deltas.

```python
from datetime import datetime, timedelta, timezone
from oxarchive import OrderBookReconstructor

# Option 1: Get fully reconstructed snapshots (simplest)
snapshots = client.lighter.orderbook.history_reconstructed(
    "BTC",
    start=datetime.now(timezone.utc) - timedelta(hours=1),
    end=datetime.now(timezone.utc)
)

for ob in snapshots:
    print(f"{ob.timestamp}: bid={ob.bids[0].px} ask={ob.asks[0].px}")

# Option 2: Get raw tick data for custom reconstruction
tick_data = client.lighter.orderbook.history_tick(
    "BTC",
    start=datetime.now(timezone.utc) - timedelta(hours=1),
    end=datetime.now(timezone.utc)
)

print(f"Checkpoint: {len(tick_data.checkpoint.bids)} bids")
print(f"Deltas: {len(tick_data.deltas)} updates")

# Option 3: Auto-paginating iterator (recommended for large time ranges)
# Automatically handles pagination, fetching up to 1,000 deltas per request
for snapshot in client.lighter.orderbook.iterate_tick_history(
    "BTC",
    start=datetime.now(timezone.utc) - timedelta(days=1),  # 24 hours of data
    end=datetime.now(timezone.utc)
):
    print(snapshot.timestamp, "Mid:", snapshot.mid_price)
    if some_condition:
        break  # Early exit supported

# Option 4: Manual iteration (single page, for custom logic)
for snapshot in client.lighter.orderbook.iterate_reconstructed(
    "BTC", start=start, end=end
):
    # Process each snapshot without loading all into memory
    process(snapshot)
    if some_condition:
        break  # Early exit if needed

# Option 5: Get only final state (most efficient)
reconstructor = client.lighter.orderbook.create_reconstructor()
final = reconstructor.reconstruct_final(tick_data.checkpoint, tick_data.deltas)

# Check for sequence gaps
gaps = OrderBookReconstructor.detect_gaps(tick_data.deltas)
if gaps:
    print("Sequence gaps detected:", gaps)

# Async versions available
snapshots = await client.lighter.orderbook.ahistory_reconstructed("BTC", start=..., end=...)
tick_data = await client.lighter.orderbook.ahistory_tick("BTC", start=..., end=...)
# Async auto-paginating iterator
async for snapshot in client.lighter.orderbook.aiterate_tick_history("BTC", start=..., end=...):
    process(snapshot)
```

**Methods:**
| Method | Description |
|--------|-------------|
| `history_tick(coin, ...)` | Get raw checkpoint + deltas (single page, max 1,000 deltas) |
| `history_reconstructed(coin, ...)` | Get fully reconstructed snapshots (single page) |
| `iterate_tick_history(coin, ...)` | Auto-paginating iterator for large time ranges |
| `aiterate_tick_history(coin, ...)` | Async auto-paginating iterator |
| `iterate_reconstructed(coin, ...)` | Memory-efficient iterator (single page) |
| `create_reconstructor()` | Create a reconstructor instance for manual control |

**Note:** The API returns a maximum of 1,000 deltas per request. For time ranges with more deltas, use `iterate_tick_history()` / `aiterate_tick_history()` which handle pagination automatically.

**Parameters:**
| Parameter | Default | Description |
|-----------|---------|-------------|
| `depth` | all | Maximum price levels in output |
| `emit_all` | `True` | If `False`, only return final state |

### Trades

`trades.history()` pages the trade tape of a window with a cursor. `trades.list()` is the same method under its earlier name and keeps working.

```python
# Get trade history with cursor-based pagination
result = client.hyperliquid.trades.history("ETH", start=hour_ago, end=now, limit=1000)
trades = list(result.data)

# Paginate through all results
while result.has_more:
    result = client.hyperliquid.trades.history(
        "ETH",
        start=hour_ago,
        end=now,
        cursor=result.next_cursor,
        limit=1000
    )
    trades.extend(result.data)

# One side of the tape: side="buy" (side == "B") or side="sell" (side == "A").
# The API filters before paging, so a full page holds `limit` matching trades.
buys = client.hyperliquid.trades.history("ETH", start=hour_ago, end=now, side="buy")

# Get recent trades (HIP-3, HIP-4, spot and Lighter), optionally one side
recent = client.lighter.trades.recent("BTC", limit=100)
recent_sells = client.spot.trades.recent("HYPE-USDC", limit=100, side="sell")

# HIP-3 recent trades (case-sensitive coins)
hip3_recent = client.hyperliquid.hip3.trades.recent("xyz:TSLA", limit=100)

# HIP-3 trade history
hip3_trades = client.hyperliquid.hip3.trades.history("xyz:TSLA", start=day_ago, end=now)

# Async versions
result = await client.hyperliquid.trades.ahistory("ETH", start=..., end=...)
recent = await client.lighter.trades.arecent("BTC", limit=100)
hip3_recent = await client.hyperliquid.hip3.trades.arecent("xyz:TSLA", limit=100)
```

**Note:** `recent()` is available on HIP-3, HIP-4, spot and both Lighter deployments. The API does not serve it for Hyperliquid core, so `client.hyperliquid.trades.recent()` raises `OxArchiveError` with `error_code == "unsupported_for_venue"` before sending; use `history()` with a time range there.

### Instruments

```python
# List all trading instruments (Hyperliquid)
instruments = client.hyperliquid.instruments.list()

# Get specific instrument details
btc = client.hyperliquid.instruments.get("BTC")
print(f"BTC size decimals: {btc.sz_decimals}")

# Async versions
instruments = await client.hyperliquid.instruments.alist()
btc = await client.hyperliquid.instruments.aget("BTC")
```

#### Lighter Instruments

Lighter instruments have a different schema with additional fields for fees, market IDs, and minimum order amounts:

```python
# List Lighter instruments (returns LighterInstrument, not Instrument)
lighter_instruments = client.lighter.instruments.list()

# Get specific Lighter instrument
eth = client.lighter.instruments.get("ETH")
print(f"ETH taker fee: {eth.taker_fee}")
print(f"ETH maker fee: {eth.maker_fee}")
print(f"ETH market ID: {eth.market_id}")
print(f"ETH min base amount: {eth.min_base_amount}")

# Async versions
lighter_instruments = await client.lighter.instruments.alist()
eth = await client.lighter.instruments.aget("ETH")
```

**Key differences:**
| Field | Hyperliquid (`Instrument`) | Lighter (`LighterInstrument`) |
|-------|---------------------------|------------------------------|
| Symbol | `name` | `symbol` |
| Size decimals | `sz_decimals` | `size_decimals` |
| Fee info | Not available | `taker_fee`, `maker_fee`, `liquidation_fee` |
| Market ID | Not available | `market_id` |
| Min amounts | Not available | `min_base_amount`, `min_quote_amount` |

#### HIP-3 Instruments

HIP-3 instruments are derived from live market data and include mark price, open interest, and mid price:

```python
# List all HIP-3 instruments
hip3_instruments = client.hyperliquid.hip3.instruments.list()
for inst in hip3_instruments:
    print(f"{inst.coin} ({inst.namespace}:{inst.ticker}): mark={inst.mark_price}, OI={inst.open_interest}")

# Get specific HIP-3 instrument (case-sensitive)
tsla = client.hyperliquid.hip3.instruments.get("xyz:TSLA")
print(f"Mark price: {tsla.mark_price}")

# Async versions
hip3_instruments = await client.hyperliquid.hip3.instruments.alist()
tsla = await client.hyperliquid.hip3.instruments.aget("xyz:TSLA")
```

**HIP-3 coins:** builders list and delist markets over time, so this README does not pin a list. Call `client.hyperliquid.hip3.instruments.list()` for the current set. Coin names are case-sensitive and carry the builder prefix (`xyz:TSLA`, `xyz:XYZ100`).

#### HIP-3 Market Breadth

HIP-3 breadth reports the percentage of eligible instruments trading above their current UTC-session VWAP. The current snapshot is available from `client.hyperliquid.hip3.breadth.current()`, and history is cursor-paginated through `client.hyperliquid.hip3.breadth.history()`:

```python
current = client.hyperliquid.hip3.breadth.current()
print(f"{current.value_pct}% above VWAP ({current.counts.eligible} eligible)")

history = client.hyperliquid.hip3.breadth.history(
    start=day_ago,
    end=now,
    interval="5m",  # 1m, 5m, 15m, 30m, 1h, 4h, 1d
    limit=1000,
)
while history.has_more:
    history = client.hyperliquid.hip3.breadth.history(
        start=day_ago,
        end=now,
        interval="5m",
        cursor=history.next_cursor,
        limit=1000,
    )
```

The session resets at 00:00 UTC and compares the close of the most recently completed one-minute candle with session VWAP. Instruments without session volume or with a completed candle older than five minutes are excluded, so `coverage_ratio` varies with market hours. `value_pct` is `None`, not zero, when no instrument is eligible. History begins on 2026-08-28; the SDK does not imply synthetic pre-launch history. Interval downsampling uses the last snapshot in each bucket, never an average of percentages.

The same breadth is served for Hyperliquid core perpetuals on `client.hyperliquid.breadth`, with the same methods, intervals and cursor paging. Core history begins on 2026-08-24, and core responses carry empty `namespaces` maps.

```python
current = client.hyperliquid.breadth.current()
history = client.hyperliquid.breadth.history(start=day_ago, interval="1h")
```

#### HIP-3 Oracle

The deployer-pushed external price of a HIP-3 market, and its instantaneous discovery bounds:

```python
price = client.hyperliquid.hip3.oracle.external_price("xyz:TSLA")
print(price.external_price, price.mark_price, price.block_number)

bounds = client.hyperliquid.hip3.oracle.discovery_bounds("xyz:TSLA")
print(bounds.reference_source, bounds.lower_bound, bounds.upper_bound)

# Async versions
price = await client.hyperliquid.hip3.oracle.aexternal_price("xyz:TSLA")
bounds = await client.hyperliquid.hip3.oracle.adiscovery_bounds("xyz:TSLA")
```

`external_price` and `mark_price` are `None` when the market has none. The discovery bounds are `reference_price` times one minus and one plus `bound_fraction`, where the reference is the external price when available and the mark price otherwise (`reference_source`) and the fraction follows from the market's max leverage. The full ratcheted range can be wider when a deployer's reset configuration applies. `timestamp` is a UTC `datetime`, and `timestamp_ms` the same instant in Unix milliseconds.

#### HIP-4 Outcome Markets

HIP-4 binary-outcome markets resolve to ``Yes`` (side 0) or ``No`` (side 1) at expiry. Each outcome has two per-side coins (``#N``, where ``N = 10*outcome_id + side``). The SDK accepts both the bare numeric (``"0"``) and ``#``-prefixed (``"#0"``) forms. On REST paths it sends the bare form (the backend routes both to the same record). HIP-4 serves L4 and order history from 2026-05-02 07:47 UTC, trades and candles from 2026-05-02 08:00 UTC, and the order book, outcome-side OI and prices from 2026-05-02 16:51 UTC, with raw OI updates at ~10s. HIP-3 and Lighter candle pages accept up to 10,000 rows; HIP-4 candle pages are capped at 1,000 rows. HIP-4 has **no funding and no liquidations**. The ``mark_price`` field on HIP-4 OI/summary responses is an **implied probability in [0, 1]**, not a USD price.

```python
# Outcome-level metadata (one row per outcome_id; sides folded into side_specs).
result = client.hyperliquid.hip4.list_outcomes(is_settled=False, limit=50)
for o in result.data:
    print(f"#{o.outcome_id}: {o.underlying} {o.class_} expiry={o.expiry}")

# Outcomes settle and new ones list every day, so find one rather than pin it.
# Here: the Yes side of an open BTC price outcome, from the symbol universe.
yes = next(
    s for s in client.symbols.list()
    if s.exchange == "hip4" and not s.is_settled
    and (s.slug or "").startswith("btc-above-") and "-yes-" in s.slug
)
coin = yes.symbol                     # "#N"
outcome_id = int(coin[1:]) // 10      # N = 10 * outcome_id + side

# Single-outcome detail. Includes aggregated_oi (paired both-sides snapshot).
outcome = client.hyperliquid.hip4.get_outcome(outcome_id)
agg = outcome.aggregated_oi
print(f"Display OI: {agg.outcome_display_open_interest_contracts} {agg.currency}")
print(f"Side parity: {agg.side_supply_parity}")

# Look up by slug (per-outcome OR per-side). Returns aggregated_oi too.
outcome = client.hyperliquid.hip4.get_outcome_by_slug(outcome.slug)

# Filter the list endpoint by slug. Short-circuits to a one-item response.
result = client.hyperliquid.hip4.list_outcomes(slug=yes.slug)

# Questions group several binary outcomes under one multi-choice resolver:
# one named outcome per choice, plus a fallback outcome that resolves Yes when
# no named choice does. Page with next_cursor, passed back unchanged.
page = client.hyperliquid.hip4.list_questions(limit=100)
question = client.hyperliquid.hip4.get_question(page.data[0].question_id)
print(question.named_outcome_ids, question.fallback_outcome_id, question.settled_named_outcomes)
# Also: client.hyperliquid.hip4.questions.list() / .get(), and alist() / aget()

# Per-side instruments. Either bare or "#"-prefixed works.
yes_side = client.hyperliquid.hip4.instruments.get(coin[1:])                   # bare, recommended
no_side = client.hyperliquid.hip4.instruments.get(f"#{10 * outcome_id + 1}")   # also works

# Market data.
ob = client.hyperliquid.hip4.get_orderbook(coin)
trades = client.hyperliquid.hip4.get_trades_recent(coin, limit=50)
candles = client.hyperliquid.hip4.candles.history(coin, start=day_ago, end=now, interval="1h")
oi = client.hyperliquid.hip4.get_open_interest_current(coin)  # mark_price is in [0, 1]
summary = client.hyperliquid.hip4.get_summary(coin)           # mark_price is in [0, 1]
```

#### Hyperliquid Spot

Hyperliquid spot pairs live at `/v1/hyperliquid/spot` and are accessible via `client.spot`. Symbols use dashed canonical form (`HYPE-USDC`, `PURR-USDC`); the server resolves dashed to wire format (`PURR/USDC` or `@107`) internally. Spot has **no funding, no open interest, or liquidations**. Candle history is served at `/v1/hyperliquid/spot/candles/{symbol}` from 2025-03-22 10:50 UTC, supports `1m`, `5m`, `15m`, `30m`, `1h`, `4h`, `1d`, and `1w`, and accepts a maximum of 1,000 rows per page with numeric timestamp-string cursors; pass each `next_cursor` back unchanged.

Trades are served from 2025-03-22 10:50:22 UTC, TWAP statuses from 2026-05-05 13:05 UTC, the order book from 2026-05-05 19:56 UTC, and L4 from 2026-05-05 22:57 UTC (PURR-USDC from 2026-03-11 01:03 UTC); REST order history reaches back further. Pairs listed later start later; `client.symbols.list()` has each pair's starts.

```python
# Pair discovery
pairs = client.spot.pairs.list()
hype = client.spot.pairs.get("HYPE-USDC")
print(
    f"{hype.symbol}: base={hype.base_token_name} "
    f"quote={hype.quote_token_name} pair_index={hype.pair_index}"
)

# Current orderbook
ob = client.spot.orderbook.get("HYPE-USDC")
print(f"HYPE-USDC mid: {ob.mid_price}, spread bps: {ob.spread_bps}")

# Orderbook history
history = client.spot.orderbook.history("HYPE-USDC", start=hour_ago, end=now)

# Trades by time window
trades = client.spot.trades.list("HYPE-USDC", start=hour_ago, end=now, limit=1000)

# Candle history (coverage starts at 2025-03-22 10:50 UTC)
spot_candles = client.spot.candles.history(
    "HYPE-USDC",
    start=day_ago,
    end=now,
    interval="1h",
    limit=1000,
)

# L4 endpoints (full reconstruction, raw diffs, and checkpoint history)
snapshot = client.spot.l4_orderbook.get("HYPE-USDC")
diffs = client.spot.l4_orderbook.diffs("HYPE-USDC", start=..., end=...)
checkpoints = client.spot.l4_orderbook.history("HYPE-USDC", start=..., end=...)

# L4 order lifecycle
orders = client.spot.orders.history("HYPE-USDC", start=..., end=...)

# TWAP statuses, by symbol (history() is the same method as by_symbol()) or by user wallet
twap_pair = client.spot.twap.history("HYPE-USDC", start=..., end=...)
twap_user = client.spot.twap.by_user("0xabc...", start=..., end=...)

# Per-dataset freshness lag: orderbook, trades, l4_diffs, l4_checkpoints,
# orders and twap, each with optional lag_ms and last_updated
fresh = client.spot.get_freshness("HYPE-USDC")
print(fresh.orderbook.lag_ms, fresh.trades.last_updated)
for dataset, lag in fresh.tables.items():
    print(f"{dataset}: lag={lag.lag_ms}ms last_updated={lag.last_updated}")

# Async versions are available on every method:
ob = await client.spot.orderbook.aget("HYPE-USDC")
pairs = await client.spot.pairs.alist()
twap = await client.spot.twap.aby_user("0xabc...", start=..., end=...)
fresh = await client.spot.aget_freshness("HYPE-USDC")
```

#### Lighter on Robinhood Chain

Lighter has two deployments: mainnet (`client.lighter`) and Robinhood Chain (`client.rh_lighter`, REST root `/v1/rh-lighter`). The Robinhood Chain deployment has the same resources as `client.lighter` except the L3 order book, which is not captured there, and the L1 account resolver. Markets are quoted in USDG. Perps use uppercase symbols (`BTC`); spot markets use dashed symbols (`AAPL-USDG`). Symbols are case-insensitive. Market symbols and ids belong to each deployment, so `BTC` on `client.rh_lighter` is a different market from `BTC` on `client.lighter`.

Coverage: trades and liquidations from the venue launch, 2026-06-26 20:10:26 UTC; order book, open interest, and funding from 2026-08-22 18:43 UTC; account positions from 2026-06-26. A request that starts before a data type's first date is refused with the API's coverage error. Liquidations from before live capture were backfilled from the venue's finalized export: those rows have `source == "bucket"` and an empty `raw_json`, while rows captured live have `source == "ws"` and the venue's raw JSON. Candles are served from 2026-06-26 20:10 UTC.

Trades follow the same finalization contract as mainnet Lighter. `trades.list()` returns canonical trades only: `end` is clamped to the finalization watermark, about a day behind, reported as `result.meta.finalized_through`, with `meta.requested_end` and `meta.clamped_to` set when the clamp applied. `trades.recent()` serves the preliminary tier.

```python
rh = client.rh_lighter

# Markets
markets = rh.instruments.list()
aapl = rh.instruments.get("AAPL-USDG")

# Order book (from 2026-08-22 18:43 UTC)
book = rh.orderbook.get("AAPL-USDG")
books = rh.orderbook.history("BTC", start=hour_ago, end=now)

# Trades (from 2026-06-26 20:10:26 UTC). end is clamped to the finalization watermark.
page = rh.trades.list("BTC", start=day_ago, end=now, limit=1000)
print(page.meta.finalized_through, page.meta.clamped_to)
recent = rh.trades.recent("BTC")  # preliminary tier

# Open interest and funding (perps)
oi = rh.open_interest.current("BTC")
funding = rh.funding.history("BTC", start=day_ago, end=now)

# Liquidations and liquidation volume (from 2026-06-26 20:10:26 UTC)
liqs = rh.liquidations.history("BTC", start=week_ago, end=now)
volume = rh.liquidations.volume("BTC", start=week_ago, end=now, interval="1d")

# Freshness, summary, price history
fresh = rh.get_freshness("BTC")
summary = rh.get_summary("BTC")
prices = rh.get_price_history("BTC", start=day_ago, end=now, interval="1h")

# Account positions by Lighter account index (perp markets)
positions = rh.positions.get(4521)

# Async versions are available on every method
book = await rh.orderbook.aget("AAPL-USDG")
```

### Funding Rates

```python
# Get current funding rate
current = client.hyperliquid.funding.current("BTC")

# Get funding rate history (start is required)
history = client.hyperliquid.funding.history(
    "ETH",
    start=week_ago,
    end=now
)

# Get funding rate history with aggregation interval
history = client.hyperliquid.funding.history(
    "BTC",
    start=week_ago,
    end=now,
    interval="1h"
)

# HIP-3 funding (case-sensitive coins)
hip3_current = client.hyperliquid.hip3.funding.current("xyz:TSLA")
hip3_history = client.hyperliquid.hip3.funding.history("xyz:TSLA", start=week_ago, end=now)

# Async versions
current = await client.hyperliquid.funding.acurrent("BTC")
history = await client.hyperliquid.funding.ahistory("ETH", start=..., end=...)
hip3_current = await client.hyperliquid.hip3.funding.acurrent("xyz:TSLA")
```

**Unit note:** `funding_rate` is a fractional, non-annualized rate. For example, `0.0001` means `0.01%` for the funding interval. This is a breaking normalization for Lighter consumers that previously compensated for percent units; do not apply a second percent conversion.

#### Funding History Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `coin` | `str` | Yes | Coin symbol (e.g., `'BTC'`, `'ETH'`) |
| `start` | `Timestamp` | Yes | Start timestamp |
| `end` | `Timestamp` | Yes | End timestamp |
| `cursor` | `Timestamp` | No | Cursor from previous response for pagination |
| `limit` | `int` | No | Max results (default: 100, max: 1000) |
| `interval` | `str` | No | Aggregation interval: `'1m'`, `'5m'`, `'15m'`, `'30m'`, `'1h'`, `'4h'`, `'1d'`. Omit for raw rows: Hyperliquid core funding is ~1 min; HIP-3 and Lighter funding are ~10s. HIP-4 has no funding. |

### Open Interest

```python
# Get current open interest
current = client.hyperliquid.open_interest.current("BTC")

# Get open interest history (start is required)
history = client.hyperliquid.open_interest.history(
    "ETH",
    start=week_ago,
    end=now
)

# Get open interest history with aggregation interval
oi = client.hyperliquid.open_interest.history(
    "BTC",
    start=week_ago,
    end=now,
    interval="1h"
)

# HIP-3 open interest (case-sensitive coins)
hip3_current = client.hyperliquid.hip3.open_interest.current("xyz:TSLA")
hip3_history = client.hyperliquid.hip3.open_interest.history("xyz:TSLA", start=week_ago, end=now)

# Async versions
current = await client.hyperliquid.open_interest.acurrent("BTC")
history = await client.hyperliquid.open_interest.ahistory("ETH", start=..., end=...)
hip3_current = await client.hyperliquid.hip3.open_interest.acurrent("xyz:TSLA")
```

#### Open Interest History Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `coin` | `str` | Yes | Coin symbol (e.g., `'BTC'`, `'ETH'`) |
| `start` | `Timestamp` | Yes | Start timestamp |
| `end` | `Timestamp` | Yes | End timestamp |
| `cursor` | `str` | No | Numeric timestamp string returned as `next_cursor`; pass it back unchanged |
| `limit` | `int` | No | Max results (default: 100, max: 1000) |
| `interval` | `str` | No | Aggregation interval: `'1m'`, `'5m'`, `'15m'`, `'30m'`, `'1h'`, `'4h'`, `'1d'`. Omit for raw rows: HIP-3, HIP-4 outcome-side OI, and Lighter update at ~10s. |

### Liquidations

Get historical liquidation events. Available for Hyperliquid and HIP-3 (from 2025-12-22), Lighter (`client.lighter.liquidations`, from 2026-06-10) and Lighter on Robinhood Chain (`client.rh_lighter.liquidations`, from 2026-06-26 20:10:26 UTC). The projected forced-liquidation price-level endpoints refresh about every five minutes. This is a measured cadence, not an exact five-minute guarantee.

```python
# Get liquidation history for a coin (Hyperliquid)
liquidations = client.hyperliquid.liquidations.history(
    "BTC",
    start=day_ago,
    end=now,
    limit=100
)

# Paginate through all results
all_liquidations = list(liquidations.data)
while liquidations.has_more:
    liquidations = client.hyperliquid.liquidations.history(
        "BTC",
        start=day_ago,
        end=now,
        cursor=liquidations.next_cursor,
        limit=1000
    )
    all_liquidations.extend(liquidations.data)

# Get liquidations for a specific user (Hyperliquid core; HIP-3 has no per-user route)
user_liquidations = client.hyperliquid.liquidations.by_user(
    "0x1234...",
    start=week_ago,
    end=now,
    symbol="BTC"  # optional filter
)

# HIP-3 liquidations (case-sensitive coins)
hip3_liquidations = client.hyperliquid.hip3.liquidations.history(
    "xyz:TSLA",
    start=week_ago,
    end=now,
    limit=100
)

# HIP-3 liquidation volume
hip3_volume = client.hyperliquid.hip3.liquidations.volume(
    "xyz:TSLA",
    start=week_ago,
    end=now,
    interval="1h"
)

# Lighter liquidations (mainnet and Robinhood Chain). A row keeps both sides'
# account fields; see LighterLiquidation. Pass next_cursor back unchanged.
lighter_liquidations = client.lighter.liquidations.history(
    "BTC",
    start=day_ago,
    end=now,
    limit=1000
)
for liq in lighter_liquidations.data:
    # timestamp is a UTC datetime; timestamp_ms is the same instant in Unix milliseconds
    print(liq.timestamp, liq.price, liq.size, liq.usd_amount, liq.ask_account, liq.bid_account)

# Robinhood Chain liquidations start at the venue launch, 2026-06-26 20:10:26 UTC.
# Rows from before live capture have source == "bucket" and an empty raw_json.
rh_liquidations = client.rh_lighter.liquidations.history("BTC", start=week_ago, end=now)

# Async versions
liquidations = await client.hyperliquid.liquidations.ahistory("BTC", start=..., end=...)
lighter_liquidations = await client.lighter.liquidations.ahistory("BTC", start=..., end=...)
user_liquidations = await client.hyperliquid.liquidations.aby_user("0x...", start=..., end=...)
hip3_liquidations = await client.hyperliquid.hip3.liquidations.ahistory("xyz:TSLA", start=..., end=...)
hip3_volume = await client.hyperliquid.hip3.liquidations.avolume("xyz:TSLA", start=..., end=...)
```

### Liquidation Volume

Get pre-aggregated liquidation volume in time-bucketed intervals. Returns total, long, and short USD volumes per bucket -- 100-1000x less data than individual liquidation records. Available for Hyperliquid and HIP-3, and for both Lighter deployments, where each bucket carries `total_usd` and `count` only (no long/short split).

```python
# Get hourly liquidation volume for the last week (Hyperliquid)
volume = client.hyperliquid.liquidations.volume(
    "BTC",
    start=week_ago,
    end=now,
    interval="1h"  # 1m, 5m, 15m, 30m, 1h, 4h, 1d
)

for bucket in volume.data:
    print(f"{bucket.timestamp}: total=${bucket.total_usd}, long=${bucket.long_usd}, short=${bucket.short_usd}")

# HIP-3 liquidation volume
hip3_volume = client.hyperliquid.hip3.liquidations.volume(
    "xyz:TSLA",
    start=week_ago,
    end=now,
    interval="1d"
)

# Lighter liquidation volume (mainnet and Robinhood Chain): total_usd and count per bucket
lighter_volume = client.lighter.liquidations.volume("BTC", start=..., end=..., interval="1h")
rh_volume = client.rh_lighter.liquidations.volume("BTC", start=..., end=..., interval="1d")

# Convenience method on HyperliquidClient (Hyperliquid only)
volume = client.hyperliquid.get_liquidation_volume("BTC", start=..., end=..., interval="1h")

# Async versions
volume = await client.hyperliquid.liquidations.avolume("BTC", start=..., end=..., interval="1h")
hip3_volume = await client.hyperliquid.hip3.liquidations.avolume("xyz:TSLA", start=..., end=..., interval="1d")
```

### Freshness

Check when each data type was last updated for a specific coin. Useful for verifying data recency before pulling it.

```python
# Hyperliquid
freshness = client.hyperliquid.get_freshness("BTC")
print(f"Orderbook last updated: {freshness.orderbook.last_updated}, lag: {freshness.orderbook.lag_ms}ms")
print(f"Trades last updated: {freshness.trades.last_updated}, lag: {freshness.trades.lag_ms}ms")
print(f"Funding last updated: {freshness.funding.last_updated}")
print(f"OI last updated: {freshness.open_interest.last_updated}")

# Lighter
lighter_freshness = client.lighter.get_freshness("BTC")

# Lighter on Robinhood Chain
rh_freshness = client.rh_lighter.get_freshness("BTC")

# HIP-3 (case-sensitive coins)
hip3_freshness = client.hyperliquid.hip3.get_freshness("xyz:TSLA")

# Async versions
freshness = await client.hyperliquid.aget_freshness("BTC")
lighter_freshness = await client.lighter.aget_freshness("BTC")
hip3_freshness = await client.hyperliquid.hip3.aget_freshness("xyz:TSLA")
```

### Summary

Get a combined market snapshot in a single call -- mark/oracle price, funding rate, open interest, 24h volume, and 24h liquidation volumes.

```python
# Hyperliquid (includes volume + liquidation data)
summary = client.hyperliquid.get_summary("BTC")
print(f"Mark price: {summary.mark_price}")
print(f"Oracle price: {summary.oracle_price}")
print(f"Funding rate: {summary.funding_rate}")
print(f"Open interest: {summary.open_interest}")
print(f"24h volume: {summary.volume_24h}")
print(f"24h liquidation volume: ${summary.liquidation_volume_24h}")
print(f"  Long: ${summary.long_liquidation_volume_24h}")
print(f"  Short: ${summary.short_liquidation_volume_24h}")

# Lighter (price, funding, OI; no volume/liquidation data)
lighter_summary = client.lighter.get_summary("BTC")

# Lighter on Robinhood Chain (same shape as mainnet Lighter)
rh_summary = client.rh_lighter.get_summary("BTC")

# HIP-3 (includes mid_price; case-sensitive coins)
hip3_summary = client.hyperliquid.hip3.get_summary("xyz:TSLA")
print(f"Mid price: {hip3_summary.mid_price}")

# Async versions
summary = await client.hyperliquid.aget_summary("BTC")
lighter_summary = await client.lighter.aget_summary("BTC")
hip3_summary = await client.hyperliquid.hip3.aget_summary("xyz:TSLA")
```

### Price History

Get mark, oracle, and mid price history over time. Supports aggregation intervals. Data projected from open interest records.

```python
# Hyperliquid: from 2023-05-20 02:50 UTC
prices = client.hyperliquid.get_price_history(
    "BTC",
    start=day_ago,
    end=now,
    interval="1h"  # 1m, 5m, 15m, 30m, 1h, 4h, 1d
)

for snapshot in prices.data:
    print(f"{snapshot.timestamp}: mark={snapshot.mark_price}, oracle={snapshot.oracle_price}, mid={snapshot.mid_price}")

# Lighter
lighter_prices = client.lighter.get_price_history("BTC", start=day_ago, end=now, interval="1h")

# Lighter on Robinhood Chain
rh_prices = client.rh_lighter.get_price_history("BTC", start=day_ago, end=now, interval="1h")

# HIP-3 (case-sensitive coins)
hip3_prices = client.hyperliquid.hip3.get_price_history("xyz:TSLA", start=week_ago, end=now, interval="1d")

# Paginate for larger ranges
result = client.hyperliquid.get_price_history("BTC", start=..., end=..., interval="4h", limit=1000)
while result.has_more:
    result = client.hyperliquid.get_price_history(
        "BTC", start=..., end=..., interval="4h",
        cursor=result.next_cursor, limit=1000
    )

# Async versions
prices = await client.hyperliquid.aget_price_history("BTC", start=..., end=..., interval="1h")
lighter_prices = await client.lighter.aget_price_history("BTC", start=..., end=..., interval="1h")
hip3_prices = await client.hyperliquid.hip3.aget_price_history("xyz:TSLA", start=..., end=..., interval="1d")
```

### Candles (OHLCV)

Get historical OHLCV candle data aggregated from trades. Core Hyperliquid, HIP-3, and Lighter candle pages accept up to 10,000 rows; HIP-4 and Hyperliquid Spot candle pages accept up to 1,000 rows. Candles are served from 2025-03-22 12:00 UTC on Hyperliquid core, 2025-12-22 on HIP-3, 2026-05-02 08:00 UTC on HIP-4, 2025-03-22 10:50 UTC on Hyperliquid Spot, 2025-08-01 on Lighter and 2026-06-26 20:10 UTC on Robinhood Chain. Candle pagination cursors are numeric timestamp strings returned as `next_cursor`; pass each one back unchanged.

```python
# Get candle history (start is required)
candles = client.hyperliquid.candles.history(
    "BTC",
    start=day_ago,
    end=now,
    interval="1h",  # 1m, 5m, 15m, 30m, 1h, 4h, 1d, 1w
    limit=100
)

# Iterate through candles
for candle in candles.data:
    print(f"{candle.timestamp}: O={candle.open} H={candle.high} L={candle.low} C={candle.close} V={candle.volume}")

# Cursor-based pagination for large datasets
result = client.hyperliquid.candles.history("BTC", start=..., end=..., interval="1m", limit=1000)
while result.has_more:
    result = client.hyperliquid.candles.history(
        "BTC", start=..., end=..., interval="1m",
        cursor=result.next_cursor, limit=1000
    )

# Lighter candles
lighter_candles = client.lighter.candles.history(
    "BTC",
    start=day_ago,
    end=now,
    interval="15m"
)

# Lighter on Robinhood Chain candles (from 2026-06-26 20:10 UTC)
rh_candles = client.rh_lighter.candles.history("BTC", start=day_ago, end=now, interval="1h")

# HIP-3 candles (case-sensitive coins)
hip3_candles = client.hyperliquid.hip3.candles.history(
    "xyz:TSLA",
    start=day_ago,
    end=now,
    interval="1h"
)

# Hyperliquid Spot candles (dashed canonical symbols; max 1,000 rows)
spot_candles = client.spot.candles.history(
    "HYPE-USDC",
    start=day_ago,
    end=now,
    interval="1h",
    limit=1000,
)

# Async versions
candles = await client.hyperliquid.candles.ahistory("BTC", start=..., end=..., interval="1h")
hip3_candles = await client.hyperliquid.hip3.candles.ahistory("xyz:TSLA", start=..., end=..., interval="1h")
spot_candles = await client.spot.candles.ahistory("HYPE-USDC", start=day_ago, end=now, interval="1h")
```

#### Available Intervals

| Interval | Description |
|----------|-------------|
| `1m` | 1 minute |
| `5m` | 5 minutes |
| `15m` | 15 minutes |
| `30m` | 30 minutes |
| `1h` | 1 hour (default) |
| `4h` | 4 hours |
| `1d` | 1 day |
| `1w` | 1 week |

### Cumulative Volume Delta

Taker buy and sell notional per bucket, their difference, and a running total, for Hyperliquid core and HIP-3. Intervals of `1h` and longer roll up hourly totals; `1m`, `5m`, `15m` and `30m` are summed from taker fills.

```python
# One page. Without start (and without a cursor) the response is the newest
# `limit` buckets of the 24 hours before `end`.
page = client.hyperliquid.cvd.history(
    "BTC",
    start=day_ago,
    end=now,
    interval="1m",  # 1m, 5m, 15m, 30m, 1h (default), 4h, 1d, 1w
    limit=500,      # buckets per page (default 500, max 10000)
)
for bucket in page.data:
    print(bucket.timestamp, bucket.buy_volume, bucket.sell_volume, bucket.delta)

# Follow next_cursor with the same start, end and interval while has_more is
# True. Stop on has_more, not on a short page: below 1h a page can be short
# and still not be the last.
while page.has_more:
    page = client.hyperliquid.cvd.history(
        "BTC",
        start=day_ago,
        end=now,
        interval="1m",
        cursor=page.next_cursor,
    )

# Or let the iterator follow the cursor
running = 0.0
for bucket in client.hyperliquid.cvd.iterate("BTC", start=day_ago, end=now, interval="1m"):
    running += bucket.delta

# HIP-3 (case-sensitive coins)
hip3 = client.hyperliquid.hip3.cvd.history("xyz:TSLA", start=day_ago, interval="1h")

# Async versions
page = await client.hyperliquid.cvd.ahistory("BTC", start=day_ago)
async for bucket in client.hyperliquid.hip3.cvd.aiterate("xyz:TSLA", start=day_ago):
    ...
```

Buckets are labelled by their open time (`timestamp`, a UTC `datetime`; `timestamp_ms` in Unix milliseconds) and omitted when they hold no trades. `4h`, `1d` and `1w` buckets open on UTC epoch boundaries, so `1w` buckets open on Thursdays, and at those widths the first and last bucket of a window can be partial. `cumulative_delta` restarts on every page: to join pages, rebuild the running total from `delta`. A response that is one page of several says so in `meta.notice`.

### L4 Orderbook (Order-Level)

Get L4 order-level orderbook data with user attribution. Available for Hyperliquid core and HIP-3 (from 2026-03-11 01:03 UTC), HIP-4 (`client.hyperliquid.hip4.l4_orderbook`, from 2026-05-02 07:47 UTC) and spot (`client.spot.l4_orderbook`, from 2026-05-05 22:57 UTC; PURR-USDC from 2026-03-11 01:03 UTC).

In a snapshot from `get()`, each resting order's `timestamp` is the time it joined the queue, as an RFC 3339 string, with `timestamp_ms` the same instant in Unix milliseconds. When the queue time is unknown, `timestamp` is `None` and `timestamp_ms` is `0`.

```python
# Get current L4 orderbook snapshot (Hyperliquid)
snapshot = client.hyperliquid.l4_orderbook.get("BTC")
snapshot = client.hyperliquid.l4_orderbook.get("BTC", depth=10)

# Get L4 orderbook at a specific timestamp
historical = client.hyperliquid.l4_orderbook.get("BTC", timestamp=hour_ago)

# Get L4 orderbook diffs (order-level changes)
diffs = client.hyperliquid.l4_orderbook.diffs(
    "BTC",
    start=hour_ago,
    end=now,
    limit=1000
)

# Get L4 orderbook history (full checkpoints over time)
history = client.hyperliquid.l4_orderbook.history(
    "BTC",
    start=hour_ago,
    end=now,
    limit=10
)

# HIP-3 L4 orderbook (case-sensitive coins)
hip3_snapshot = client.hyperliquid.hip3.l4_orderbook.get("xyz:TSLA")
hip3_diffs = client.hyperliquid.hip3.l4_orderbook.diffs("xyz:TSLA", start=..., end=...)
hip3_history = client.hyperliquid.hip3.l4_orderbook.history("xyz:TSLA", start=..., end=...)

# Async versions
snapshot = await client.hyperliquid.l4_orderbook.aget("BTC")
diffs = await client.hyperliquid.l4_orderbook.adiffs("BTC", start=..., end=...)
history = await client.hyperliquid.l4_orderbook.ahistory("BTC", start=..., end=...)
hip3_snapshot = await client.hyperliquid.hip3.l4_orderbook.aget("xyz:TSLA")
```

**Methods:**

| Method | Description |
|--------|-------------|
| `get(symbol, *, timestamp, depth)` | Get L4 orderbook snapshot |
| `diffs(symbol, *, start, end, cursor, limit)` | Get L4 orderbook diffs (order-level changes) |
| `history(symbol, *, start, end, cursor, limit)` | Get L4 orderbook history (full checkpoints; `depth` applies to `get()` only) |

History replays over the WebSocket too, on every product; see [L4 and Full-Depth Replay](#l4-and-full-depth-replay).

### L3 Orderbook (Lighter Only)

Get Lighter L3 individual order-level snapshots from 2026-03-05 03:33 UTC, capped at 250 orders per side.

```python
# Get current L3 orderbook snapshot
snapshot = client.lighter.l3_orderbook.get("BTC")
snapshot = client.lighter.l3_orderbook.get("BTC", depth=20)

# Get L3 orderbook at a specific timestamp
historical = client.lighter.l3_orderbook.get("BTC", timestamp=hour_ago)

# Only one account's resting orders
mine = client.lighter.l3_orderbook.get("BTC", account=281474976710654)

# Get L3 orderbook history
history = client.lighter.l3_orderbook.history(
    "BTC",
    start=hour_ago,
    end=now,
    account=281474976710654,   # optional: one account's orders
    limit=100
)

# Paginate through results
while history.has_more:
    history = client.lighter.l3_orderbook.history(
        "BTC",
        start=hour_ago,
        end=now,
        cursor=history.next_cursor,
        limit=100
    )

# Async versions
snapshot = await client.lighter.l3_orderbook.aget("BTC")
history = await client.lighter.l3_orderbook.ahistory("BTC", start=..., end=...)
```

**Methods:**

| Method | Description |
|--------|-------------|
| `get(symbol, *, timestamp, depth, account)` | Get an L3 snapshot, up to 250 orders per side |
| `history(symbol, *, start, end, cursor, limit, account)` | Get L3 history from 2026-03-05 03:33 UTC, up to 250 orders per side (no `depth` or `granularity`) |

### L2 Orderbook (Full-Depth)

Get L2 full-depth orderbook derived from L4 data. Available for Hyperliquid and HIP-3, from 2026-03-11 01:03 UTC.

```python
# L2 full-depth orderbook
l2 = client.hyperliquid.l2_orderbook.get("BTC")
l2_historical = client.hyperliquid.l2_orderbook.get("BTC", timestamp=hour_ago)

# L2 orderbook history, optionally limited to the top levels of each snapshot
l2_history = client.hyperliquid.l2_orderbook.history("BTC", start=hour_ago, end=now)
l2_top = client.hyperliquid.l2_orderbook.history("BTC", start=hour_ago, end=now, depth=50)

# L2 tick-level diffs
l2_diffs = client.hyperliquid.l2_orderbook.diffs("BTC", start=hour_ago, end=now)

# HIP-3 L2 orderbook
hip3_l2 = client.hyperliquid.hip3.l2_orderbook.get("xyz:TSLA")

# Async versions
l2 = await client.hyperliquid.l2_orderbook.aget("BTC")
l2_history = await client.hyperliquid.l2_orderbook.ahistory("BTC", start=..., end=...)
l2_diffs = await client.hyperliquid.l2_orderbook.adiffs("BTC", start=..., end=...)
```

**Methods:**

| Method | Description |
|--------|-------------|
| `get(symbol, *, timestamp, depth)` | Get L2 full-depth orderbook snapshot |
| `history(symbol, *, start, end, cursor, limit, depth)` | Get L2 orderbook history (every level, or the top `depth` levels per side) |
| `diffs(symbol, *, start, end, cursor, limit)` | Get L2 tick-level diffs |

### Orders (L4 Order History)

Get L4 order history, order flow aggregation, and TP/SL data. Available for Hyperliquid core, HIP-3 and HIP-4; spot serves order history only.

```python
# Get order history
result = client.hyperliquid.orders.history(
    "BTC",
    start=hour_ago,
    end=now,
    limit=1000
)

# Filter by user, status, or order type
result = client.hyperliquid.orders.history(
    "BTC",
    start=hour_ago,
    end=now,
    user="0x1234...",
    status="filled",
    order_type="limit"
)

# Only orders whose trigger fired (triggered=False excludes them)
fired = client.hyperliquid.orders.history("BTC", start=day_ago, end=now, triggered=True)

# Get order flow aggregation: one page of time buckets
flow = client.hyperliquid.orders.flow(
    "BTC",
    start=day_ago,
    end=now,
    interval="1m",  # 1m (default), 5m, 15m, 1h
)
buckets = list(flow.data)
# A page holds up to `limit` buckets (default 1000, max 10000); follow the
# cursor with the same start, end and interval while has_more is True
while flow.has_more:
    flow = client.hyperliquid.orders.flow(
        "BTC",
        start=day_ago,
        end=now,
        interval="1m",
        cursor=flow.next_cursor,
    )
    buckets.extend(flow.data)

# Get TP/SL history
tpsl = client.hyperliquid.orders.tpsl(
    "BTC",
    start=day_ago,
    end=now,
    user="0x1234...",       # optional
    triggered=True          # optional filter
)

# HIP-3 orders (case-sensitive coins)
hip3_orders = client.hyperliquid.hip3.orders.history("xyz:TSLA", start=..., end=...)
hip3_flow = client.hyperliquid.hip3.orders.flow("xyz:TSLA", start=..., end=..., interval="1h")
hip3_tpsl = client.hyperliquid.hip3.orders.tpsl("xyz:TSLA", start=..., end=...)

# Async versions
result = await client.hyperliquid.orders.ahistory("BTC", start=..., end=...)
flow = await client.hyperliquid.orders.aflow("BTC", start=..., end=...)
tpsl = await client.hyperliquid.orders.atpsl("BTC", start=..., end=...)
hip3_orders = await client.hyperliquid.hip3.orders.ahistory("xyz:TSLA", start=..., end=...)
```

**Methods:**

| Method | Description |
|--------|-------------|
| `history(symbol, *, start, end, user, status, order_type, triggered, cursor, limit)` | Get order history |
| `flow(symbol, *, start, end, interval, cursor, limit)` | Get order flow aggregation, one page of buckets |
| `tpsl(symbol, *, start, end, user, triggered, cursor, limit)` | Get TP/SL history |

Hyperliquid core and HIP-3 also have `trigger_levels()` and `trigger_levels_history()`. HIP-4 serves `history()`, `flow()` and `tpsl()`. Spot serves `history(symbol, *, start, end, cursor, limit)` only, without user, status, order-type or triggered filters.

### Account Positions

What an account holds, now or at any instant, plus hourly history, the change log of every fill that moved a position, account summaries, and market-wide listings. Available on four clients with the same method names:

| Client | Account key | Change log from | Hourly history from | Live snapshot |
|--------|-------------|-----------------|---------------------|---------------|
| `client.hyperliquid.positions` | 0x wallet address | 2025-05-25 | 2026-06-07 | every 5 minutes |
| `client.hyperliquid.hip3.positions` | 0x wallet address (optional `dex`) | 2025-10-13 | 2026-06-07 | every 5 minutes |
| `client.lighter.positions` | integer Lighter account index | 2025-01-17 | 2025-01-17 | every 2 minutes |
| `client.rh_lighter.positions` | integer Lighter account index | 2026-06-26 | 2026-06-26 | every 2 minutes |

Lighter positions cover perp markets. On Lighter mainnet, `client.lighter.accounts.by_l1(address)` resolves an L1 address to the account indices it owns.

```python
# Now: the latest live snapshot
current = client.hyperliquid.positions.get("0xabc...")
for p in current.data.positions:
    print(p.symbol, p.side, p.size, p.entry_price, p.unrealized_pnl, p.quality)
print(current.data.account)      # AccountSummary on the first page of a snapshot, or None
print(current.meta.as_of, current.meta.quality, current.meta.stale)

# As of an instant: the state after every event before it. An exact UTC hour
# serves the hourly snapshot; any other instant is reconstructed from the
# change log (meta.source == "reconstructed"; mark fields are at the instant).
then = client.hyperliquid.positions.get("0xabc...", timestamp=day_ago)
print(then.meta.source, then.meta.built_through, then.meta.clamped_to)

# Hourly history and the change log in [start, end), following cursors
for row in client.hyperliquid.positions.iterate_history("0xabc...", start=day_ago, end=now):
    print(row.snapshot_ts, row.symbol, row.size)
for leg in client.hyperliquid.positions.iterate_changes("0xabc...", start=day_ago, end=now, symbol="BTC"):
    print(leg.timestamp, leg.event_type, leg.start_position, "->", leg.end_position, leg.closed_pnl)

# Account summaries: the clearinghouse summary on Hyperliquid and HIP-3,
# position aggregates on Lighter and Robinhood Chain
summary = client.hyperliquid.positions.account("0xabc...")
hourly = client.hyperliquid.positions.account_history("0xabc...", start=day_ago, end=now)
lighter_summary = client.lighter.positions.account(4521)
lighter_hourly = client.rh_lighter.positions.account_history(4521, start=day_ago, end=now)

# HIP-3: dex narrows a wallet to one dex; symbols are case-sensitive
hip3 = client.hyperliquid.hip3.positions.get("0xabc...", dex="xyz")

# Every open position in a market, largest value first; totals on the first page
page = client.hyperliquid.positions.market("BTC", side="long", min_value=1_000_000)
print(page.meta.totals.long_count, page.meta.totals.top10_value_share)
last_hour = now.replace(minute=0, second=0, microsecond=0) - timedelta(hours=1)  # an exact UTC hour
at_hour = client.hyperliquid.positions.market("BTC", hour=last_hour)

# Long/short aggregates: now, or one per hour over [start, end)
now_summary = client.hyperliquid.positions.market_summary("BTC")
series = client.hyperliquid.positions.market_summary("BTC", start=day_ago, end=now)

# Bulk: every open position across markets at one hourly snapshot
for row in client.hyperliquid.positions.iterate_all(last_hour):
    print(row.user_address, row.symbol, row.size)

# Lighter (mainnet and Robinhood Chain): integer account indices
owned = client.lighter.accounts.by_l1("0xabc...")
for account in owned.data.accounts:
    lighter_now = client.lighter.positions.get(int(account.account_index))
    # Without a symbol filter, the first page carries position aggregates
    # (total_position_value, total_unrealized_pnl, long_value, short_value, n_positions).
    print(lighter_now.data.account)
changes = client.lighter.positions.changes(4521, start=day_ago, end=now)
print(changes.meta.finalized_through)  # legs before it are final
market = client.lighter.positions.market("BTC", include_system=True)  # include system accounts
rh_now = client.rh_lighter.positions.get(4521)

# Async versions of every method (aget, ahistory, achanges, amarket, ...)
# and of every iterator (aiterate_history, aiterate_changes, ...)
current = await client.hyperliquid.positions.aget("0xabc...")
async for leg in client.lighter.positions.aiterate_changes(4521, start=..., end=...):
    ...
```

**Methods** (on every positions client unless noted):

| Method | Returns |
|--------|---------|
| `get(key, *, timestamp, symbol, dex, cursor, limit)` | `CursorResponse[WalletPositions]`: `positions`, `account`, `account_seen` |
| `history(key, *, start, end, symbol, dex, cursor, limit)` | Hourly `Position` rows |
| `changes(key, *, start, end, symbol, dex, cursor, limit)` | `PositionChange` legs |
| `market(symbol, *, hour, side, min_value, include_system, cursor, limit)` | `MarketPosition` rows; `meta.totals` on the first page |
| `market_summary(symbol, *, start, end, include_system, cursor, limit)` | `MarketPositionsSummary` (one now, or one per hour) |
| `all(hour, *, include_system, cursor, limit)` | `MarketPosition` rows across every market at one hour |
| `account(key, *, dex)` | `AccountSummary` rows at the latest live snapshot: the clearinghouse summary on Hyperliquid and HIP-3, position aggregates on Lighter |
| `account_history(key, *, start, end, dex, cursor, limit)` | Hourly `AccountSummary` rows (on Lighter, one per hour, at most 744 per page) |
| `iterate_history`, `iterate_changes`, `iterate_market`, `iterate_market_summary`, `iterate_all`, `iterate_account_history` | Iterators that follow `next_cursor` for you |
| `client.lighter.accounts.by_l1(l1_address, *, cursor, limit)` | `LighterL1Accounts`: `l1_address`, `total_accounts`, `accounts` (Lighter mainnet only) |

`key` is a 0x address on Hyperliquid and HIP-3 and an integer account index on Lighter. `dex` applies to HIP-3 and `include_system` to Lighter. Timestamps accept Unix milliseconds, ISO strings, or datetimes, and a time without a time zone is UTC; `hour` must be an exact UTC hour.

Things to know:

- **Numbers are decimal strings.** A flat position is `"0"`. A value is `None` when it is unknown, never a guess.
- **`meta`** carries the context of every response: `as_of` (the instant the state describes), `snapshot_ts`, `source` (`snapshot`, `reconstructed`, or `changes`), `quality`, `stale` (the live snapshot is older than 12 minutes), `built_through` (reads are clamped to it; `clamped_to` and `requested_end` show when they were), `finalized_through` (everything before it is final), and `totals` on market listings.
- **Quality is per row.** `quality` is `complete`, `partial` (for example no mark), or `degraded`; Lighter rows can also be `preliminary`, `unreconciled`, or `incomplete`.
- **Empty results are explained.** When a wallet has no open positions, `account_seen` is `flat`, `never_seen` (no activity recorded in the covered history; see `meta.notice` and `meta.coverage_from`), or `outside_coverage`.
- **Cursors are bound to their request.** Pass `next_cursor` back with every other argument unchanged. If the snapshot a market cursor was paging is replaced, the API answers 409 (`OxArchiveError.code == 409`); restart without a cursor.
- **Billing and limits.** Position rows are billed like trades, 1,000 rows per credit; `account()`, `account_history()`, and `by_l1()` are billed at the per-request minimum. Wallet routes return up to 5,000 rows per page (default 500), market routes up to 2,000 (default 100), bulk `all()` up to 2,000 (default 1,000), and summary series up to 168 hours per page.

### Wallet Classification

Precomputed daily behavior metrics for active wallets on Hyperliquid core and HIP-3: orders, fills, cancel and fill rates, maker ratio, order sizes, cancel speed, fees, realized PnL, TWAP, priority gas and builder usage. Filter and sort server side, and page with `limit` and `offset`.

```python
page = client.hyperliquid.wallets.classify(
    min_orders=1000,
    min_volume_usd=1_000_000,
    sort="total_volume_usd",   # default total_orders
    order="desc",
    limit=100,                 # 1 to 1000 (default 100)
    offset=0,                  # at most 100000
    date=day_ago.date(),       # daily snapshot; default yesterday (UTC)
)
print(f"{page.total} wallets match on {page.date}")
for wallet in page.wallets:
    m = wallet.metrics
    print(wallet.address, m.total_volume_usd, m.maker_ratio, m.cancel_rate)

# HIP-3 wallets, filtered by behavior
hip3 = client.hyperliquid.hip3.wallets.classify(uses_twap=True, min_cancel_rate=0.5)

# Async versions
page = await client.hyperliquid.wallets.aclassify(sort="realized_pnl_usd")
```

`date` accepts a `date`, a `YYYY-MM-DD` string, or a datetime (a datetime without a time zone is UTC). Each request costs 10 credits, with row-based metering on the wallets returned where it applies. Every metric field is optional.

### Symbol Universe

Every public market across the venue families (`hyperliquid`, `hip3`, `hip4`, `spot`, `lighter`, `rh-lighter`), with the data types served for each and coverage dates overall and per data type. Use it to discover symbols before choosing a venue-specific route. The route needs no API key.

```python
symbols = client.symbols.list()
hip3 = [s.symbol for s in symbols if s.exchange == "hip3"]
btc = next(s for s in symbols if s.exchange == "hyperliquid" and s.symbol == "BTC")
print(btc.data_types, btc.coverage_from, btc.coverage_by_type.get("trades"))

# HIP-4 entries also carry the slug, the outcome pair and a display title
outcomes = [s for s in symbols if s.exchange == "hip4" and not s.is_settled]

# Async version
symbols = await client.symbols.alist()
```

The whole universe is returned in one response, so fetch it once and filter locally.

### Data Quality Monitoring

Monitor data coverage, incidents, latency, and SLA compliance across venue APIs. Venue scopes are `hyperliquid`, `hip3`, `hip4`, `spot` (Hyperliquid spot), `lighter` (Lighter mainnet), and `rh-lighter` (Lighter on Robinhood Chain).

```python
# Get overall system health status
status = client.data_quality.status()
print(f"System status: {status.status}")
for exchange, info in status.exchanges.items():
    print(f"  {exchange}: {info.status}")

# Get data coverage summary for venue APIs
coverage = client.data_quality.coverage()
for exchange in coverage.exchanges:
    print(f"{exchange.exchange}:")
    for dtype, info in exchange.data_types.items():
        print(f"  {dtype}: {info.total_records:,} records, {info.completeness}% complete")

# Get symbol-specific coverage with gap detection
btc = client.data_quality.symbol_coverage("hyperliquid", "BTC")
oi = btc.data_types["open_interest"]
print(f"BTC OI completeness: {oi.completeness}%")
print(f"Historical coverage: {oi.historical_coverage}%")  # Hour-level granularity
print(f"Gaps found: {len(oi.gaps)}")
for gap in oi.gaps[:5]:
    print(f"  {gap.duration_minutes} min gap: {gap.start} -> {gap.end}")

# Check empirical data cadence (when available)
ob = btc.data_types["orderbook"]
if ob.cadence:
    print(f"Orderbook cadence: ~{ob.cadence.median_interval_seconds}s median, p95={ob.cadence.p95_interval_seconds}s")

# Time-bounded gap detection (last 7 days)
from datetime import datetime, timedelta, timezone
week_ago = datetime.now(timezone.utc) - timedelta(days=7)
btc_7d = client.data_quality.symbol_coverage("hyperliquid", "BTC", from_time=week_ago)

# List incidents with filtering
result = client.data_quality.list_incidents(status="open")
for incident in result.incidents:
    print(f"[{incident.severity}] {incident.title}")

# Get latency metrics
latency = client.data_quality.latency()
for exchange, metrics in latency.exchanges.items():
    print(f"{exchange}: OB lag {metrics.data_freshness.orderbook_lag_ms}ms")

# Account positions freshness, one row per venue
for venue in client.data_quality.positions_freshness():
    print(venue.venue, venue.product, venue.live_age_seconds, venue.stale, venue.finalized_through)

# Get SLA compliance metrics for a specific month (both default to the current one)
sla = client.data_quality.sla(year=now.year, month=now.month)
print(f"Period: {sla.period}")
print(f"Uptime: {sla.actual.uptime}% ({sla.actual.uptime_status})")
print(f"API P99: {sla.actual.api_latency_p99_ms}ms ({sla.actual.latency_status})")

# Async versions available for all methods
status = await client.data_quality.astatus()
coverage = await client.data_quality.acoverage()
```

#### Data Quality Endpoints

| Method | Description |
|--------|-------------|
| `status()` | Overall system health and per-exchange status |
| `coverage()` | Data coverage summary for venue APIs |
| `status_coverage()` | The same summary from the public `/v1/status/coverage` route |
| `exchange_coverage(exchange)` | Coverage details for a venue scope (`hyperliquid`, `hip3`, `hip4`, `spot`, `lighter`, `rh-lighter`) |
| `symbol_coverage(exchange, symbol, *, from_time, to_time)` | Coverage with gap detection, cadence, and historical coverage. The symbol is sent as given, URL-encoded (`xyz:TSLA`, `HYPE-USDC`, `#0`) |
| `list_incidents(...)` | List incidents with filtering and pagination |
| `get_incident(incident_id)` | Get specific incident details |
| `latency()` | Current latency metrics (WebSocket, REST, data freshness) |
| `sla(year, month)` | SLA compliance metrics for a specific month |
| `positions_freshness()` | Account positions freshness per venue: latest live and hourly snapshots, staleness, `built_through`, `finalized_through` |

**Note:** Data Quality endpoints (`coverage()`, `exchange_coverage()`, `symbol_coverage()`) perform complex aggregation queries and may take 30-60 seconds on first request (results are cached server-side for 5 minutes). If you encounter timeout errors, create a client with a longer timeout:

```python
client = Client(
    api_key="0xa_your_api_key",
    timeout=60.0  # 60 seconds for data quality endpoints
)
```

### Webhooks

Push delivery of market, account and platform events. Instead of polling a route on a timer, register an HTTPS URL and 0xArchive posts to it when something happens.

Three objects, in the order you create them:

1. An **endpoint** is an HTTPS URL 0xArchive posts to. Creating one returns its signing secret, once.
2. A **subscription** is a rule: one event type, on one endpoint, with an optional configuration of filters, parameters and conditions.
3. A **watched address** is a wallet. Event types whose `scope` is `addresses` report only on wallets on this list.

```python
# 1. Somewhere to deliver
endpoint = client.webhooks.create_endpoint(
    "https://example.com/hooks/0xarchive",
    description="Desk alerts",
)
store_secret(endpoint.secret)  # shown once, never returned again

# 2. Size the rule before turning it on
estimate = client.webhooks.estimate(
    "market.liquidation",
    {"venue": "hyperliquid", "min_notional_usd": 250_000},
    lookback_days=7,
)
print(f"median {estimate.per_day_p50:.0f} deliveries a day, busiest day {estimate.per_day_max}")

# 3. Turn it on
sub = client.webhooks.create_subscription(
    endpoint.id,
    "market.liquidation",
    {"venue": "hyperliquid", "min_notional_usd": 250_000},
)

# 4. Send a real signed test delivery to the receiver
client.webhooks.test_endpoint(endpoint.id)
```

#### Plan limits

Webhook delivery needs a paid plan. `client.webhooks.limits()` reports what the plan allows and what is in use: endpoints, subscriptions, watched wallets, today's delivery budget and when it resets, and how many subscriptions are paused.

| Plan | Endpoints | Subscriptions | Watched wallets | Deliveries per day |
| --- | --- | --- | --- | --- |
| Free | 0 | 0 | 0 | 0 |
| Build | 1 | 8 | 2 | 5,000 |
| Pro | 4 | 40 | 15 | 50,000 |
| Scale | 12 | 200 | 50 | 500,000 |
| Enterprise | 100 | 2,000 | 250 | No daily ceiling |

`estimate()` and `dry_run()` are available on every plan, Free included, so a rule can be designed and sized before there is anywhere to deliver it. They are metered like the market data they return, and an account can run six of them a minute, shared between the two. An event type whose `scope` is `addresses` previews against your watched wallets, so it needs at least one on the list.

```python
limits = client.webhooks.limits()
print(limits.plan, limits.included)
print(limits.subscriptions.used, "of", limits.subscriptions.limit)
print(limits.deliveries_per_day.remaining, "deliveries left until", limits.deliveries_per_day.resets_at)
print(limits.paused_subscriptions.count, "paused")
```

#### Paused subscriptions

When an account reaches its daily delivery budget, its subscriptions pause and say so: `status` becomes `"auto_paused"`, `pause_reason` is `"deliveries_per_day_cap"` (or `"plan_no_webhooks"` when the plan has no delivery), and `pause_message` explains what clears it. Nothing is queued while a rule is paused, and a paused rule does not restart when the budget resets. Resume it, then recover the window it missed from the REST routes:

```python
for sub in client.webhooks.list_subscriptions():
    if sub.status == "auto_paused":
        print(sub.id, sub.pause_message, sub.suppressed_count)

# One rule, or every paused rule on the account
result = client.webhooks.resume_subscription(sub.id)
result = client.webhooks.resume_all_subscriptions()
if result.gap:
    window = result.gap.replay_window
    print(f"re-read {window.start} to {window.end}: {result.gap.note}")
```

`gap.suppressed_count` is a lower bound on what matched while paused. It is `None`, with `counted` False, when the rules were address scoped, because their occurrences were never looked at. Resuming while the budget is still spent is refused (`OxArchiveError` with code 409) rather than granted and paused again. Your own `enabled` switch is never changed by a resume.

#### Event types

The catalog is the only place event types are declared. Read the filters, parameters, metrics and operators from it rather than hardcoding them.

```python
for t in client.webhooks.event_types():
    if t.live:
        print(t.type, t.scope, t.latency_class, t.description)

liq = next(t for t in client.webhooks.event_types() if t.type == "market.liquidation")
print(liq.filters)                   # accepted config keys
print(liq.params)                    # tunable parameters, with type, bounds and default
print(liq.metrics)                   # what conditions can be written against
print(liq.operators["number"])       # operators for number metrics
print(liq.cost_floor)                # the smallest occurrence the type reports
```

| Scope | Reports on | Needs |
| --- | --- | --- |
| `public` | Market-wide activity | Nothing extra |
| `addresses` | Your watched wallets | At least one watched wallet |
| `user` | Your own account and platform activity | Nothing extra |

A type whose `live` is `False` is published but does not yet accept subscriptions.

#### Configuration: filters, parameters and conditions

A subscription's configuration is checked against the event type's declaration before anything is stored, so an unknown key, an undeclared parameter, an out of range value or a condition on a metric the event does not carry is refused with the reason, never dropped. Declared parameters left out are stored at their defaults, so the stored configuration comes back more complete than what was sent. Pass the configuration as a dict or as a `WebhookSubscriptionConfig`; the API calls it `filters` on subscriptions and `config` on the previews, and the SDK takes it as `config` everywhere.

```python
from oxarchive import WebhookSubscriptionConfig, WebhookSubscriptionCondition

# Address scoped rules can only name watched wallets: add the wallet first
client.webhooks.add_address("0x6b9e773128f453f5c2c60935ee2de2cbc5390a24", label="Desk 1")

sub = client.webhooks.create_subscription(
    endpoint.id,
    "account.fill",
    WebhookSubscriptionConfig(
        addresses=["0x6b9e773128f453f5c2c60935ee2de2cbc5390a24"],
        conditions=[
            WebhookSubscriptionCondition(metric="notional_usd", op=">=", value=25_000),
            WebhookSubscriptionCondition(metric="taker", op="equal", value=True),
        ],
    ),
)

# Edit in place. A config replaces the stored one, so send the whole object.
client.webhooks.update_subscription(sub.id, config={"addresses": [...], "conditions": [...]})

# Or switch the rule off without losing it
client.webhooks.update_subscription(sub.id, enabled=False)
```

Conditions accept symbol spellings (`>=`, `<`, `!=`) as well as canonical names (`greater_than_or_equal`, `less_than`, `not_equal`), and are stored canonically. `between` and `not_between` take a `[low, high]` pair, `in` and `not_in` a list, and `is_empty` and `is_not_empty` no value. A subscription holds at most 16 conditions, all of which must hold for a delivery.

#### Previewing a rule

`dry_run()` answers "which recent occurrences would this have delivered?". `estimate()` answers "how often would it have fired?". Both validate the configuration exactly as `create_subscription()` does, so a configuration that previews cleanly subscribes cleanly. Neither stores anything or sends a delivery. Not every event type can be previewed; a type that cannot is refused with the list of those that can.

```python
# Which ones, over a recent window (60 s to 24 h, default 1 h)
preview = client.webhooks.dry_run(
    "market.liquidation",
    {"venue": "hyperliquid", "min_notional_usd": 500_000},
    lookback_s=86_400,
    limit=100,  # 1 to 200
)
print(f"{preview.matched} matched between {preview.window.from_} and {preview.window.to}")
for occurrence in preview.occurrences[:5]:
    print(occurrence.observed_at_estimate, occurrence.data)

# How often, over 1 to 30 days (default 7)
est = client.webhooks.estimate("market.liquidation_burst", lookback_days=14)
print(f"{est.total} over {est.days} days, median {est.per_day_p50:.0f} a day ({est.basis.mode})")

# And what a different threshold would have produced
for rung in est.ladder:
    print(f"  at {rung.value:,.0f}: {rung.per_day:.1f} a day")
```

`window.from_` is named with a trailing underscore because `from` is a Python keyword. `window` can start later than requested when a scan reached its row cap; `truncated` says so.

#### Verifying deliveries

Every delivery is signed with HMAC-SHA256. Verify it, or anyone who learns the URL can post to it.

The one rule that matters: **verify the raw request body**, before any JSON parser touches it. The signature covers the exact bytes that were sent, and their key order and spacing need not match what any JSON library produces, so a re-serialised dict will not verify.

```python
import os
from oxarchive import WebhookVerifier, WebhookSignatureError

verifier = WebhookVerifier(os.environ["OXARCHIVE_WEBHOOK_SECRET"])

# Flask
@app.post("/webhooks/0xarchive")
def receive():
    try:
        event = verifier.verify(request.get_data(), request.headers)
    except WebhookSignatureError as e:
        # Answer 4xx. A 5xx asks for a retry of the same unverifiable delivery.
        app.logger.warning("rejected webhook: %s", e.reason)
        return "", 400

    if already_seen(event.id):   # delivery is at-least-once
        return "", 200
    enqueue(event.payload)       # do the work out of band
    return "", 200
```

| Framework | Raw body |
| --- | --- |
| Flask | `request.get_data()` |
| FastAPI / Starlette | `await request.body()` |
| Django | `request.body` |

Not `request.get_json()`, not a parsed Pydantic model, not `request.POST`. A proxy or gateway in front of the receiver that re-encodes JSON also breaks verification: verify before that layer, or turn it off.

Each delivery carries these headers:

| Header | Meaning |
| --- | --- |
| `0xa-signature` | `t=<unix seconds>,v1=<hex>`, and during a secret rotation a second `v1=` |
| `0xa-event-id` | Event identifier. **Deduplicate on this.** Stable across retries and repeat deliveries |
| `0xa-event-type` | The event type, for example `account.fill` |
| `content-type` | `application/json` |

The signed string is the header's timestamp, a full stop, and the raw body. The event id, the event type and the other headers are not signed, so the replay window plus deduplication on `0xa-event-id` is the defence against replays. Serve the receiver over HTTPS.

`WebhookVerifier` accepts every `v1=` in the header, compares signatures in constant time, and enforces a replay window of 5 minutes by default. Every attempt, including retries and repeat deliveries, is signed with a fresh timestamp, so a legitimate delivery is never older than network and clock skew:

```python
verifier = WebhookVerifier(secret, tolerance_seconds=120)  # tighten it if you like
```

A failed check raises `WebhookSignatureError` with a `reason`: `missing_header`, `malformed_header`, `timestamp_out_of_tolerance`, `no_secrets` or `signature_mismatch`. `is_valid()` returns a bool instead. For a one-off check without holding state:

```python
from oxarchive import verify_webhook

event = verify_webhook(raw_body_bytes, headers, secret)
```

#### Rotating a secret

`rotate_secret()` issues a new secret and keeps the previous one verifying for 24 hours. During the overlap every delivery carries **two** `v1=` signatures, one under each secret, so a receiver holding either keeps verifying.

```python
rotated = client.webhooks.rotate_secret(endpoint.id)

verifier.add_secret(rotated.secret)   # now accepts both
deploy()                              # ship the new secret to every replica
verifier.remove_secret(old_secret)    # before the 24 hours are up
```

Only one previous secret is kept: rotating twice inside the window retires the original at once. A verifier written by hand must read **every** `v1=` in the header, not just the first, or it fails for up to 24 hours after each rotation.

#### Retries and failures

| Behaviour | Detail |
| --- | --- |
| Success | HTTP 200 to 299. Redirects are not followed, so a 301 or 302 is a failure |
| Timeout | 10 seconds per attempt. Acknowledge at once and process asynchronously |
| Retry schedule | 5 s, 30 s, 2 min, 10 min, 1 h, then hourly, for up to 24 hours |
| `Retry-After` | Honoured on a failed attempt, between 1 second and 5 minutes. A 429 does not count against the endpoint's health |
| Auto-disable | After 10 consecutive failures spanning at least 6 hours (`status == "auto_disabled"`) |
| Recovery | Fix the receiver, then `client.webhooks.enable_endpoint(endpoint_id)` |

```python
# What happened
for d in client.webhooks.list_deliveries(endpoint.id, limit=100):
    print(d.event_type, d.state, d.attempts, d.last_status_code, d.last_error)

# Send one again after fixing the receiver. The event id is unchanged, so a
# receiver that already processed it can deduplicate it.
client.webhooks.redeliver(delivery_id)
```

A test delivery and a repeat delivery are real signed deliveries: they count against today's budget. A repeat to a switched-off endpoint is refused (code 409), since nothing would be sent; re-enable the endpoint first.

#### Watched addresses

```python
client.webhooks.add_address("0x6b9e773128f453f5c2c60935ee2de2cbc5390a24", label="Desk 1")
watched = client.webhooks.list_addresses()
client.webhooks.delete_address(watched[0].id)
```

Adding a wallet that is already watched changes nothing and does not count against the cap again. Addresses are stored lowercase. Hyperliquid bridge system addresses are refused: such an address is a counterparty to every bridge movement of its token rather than an account. Removing a wallet leaves subscriptions that named it unchanged, so edit those rules too.

#### Every webhook method

| Method | Route |
| --- | --- |
| `event_types()` | `GET /v1/webhooks/event-types` |
| `limits()` | `GET /v1/webhooks/limits` |
| `list_endpoints()` | `GET /v1/webhooks/endpoints` |
| `create_endpoint(url, description="")` | `POST /v1/webhooks/endpoints` |
| `delete_endpoint(endpoint_id)` | `DELETE /v1/webhooks/endpoints/{id}` |
| `enable_endpoint(endpoint_id)` | `POST /v1/webhooks/endpoints/{id}/enable` |
| `rotate_secret(endpoint_id)` | `POST /v1/webhooks/endpoints/{id}/rotate` |
| `test_endpoint(endpoint_id)` | `POST /v1/webhooks/endpoints/{id}/test` |
| `list_deliveries(endpoint_id, limit=None)` | `GET /v1/webhooks/endpoints/{id}/deliveries` |
| `redeliver(delivery_id)` | `POST /v1/webhooks/deliveries/{id}/redeliver` |
| `list_subscriptions()` | `GET /v1/webhooks/subscriptions` |
| `create_subscription(endpoint_id, event_type, config=None)` | `POST /v1/webhooks/subscriptions` |
| `update_subscription(subscription_id, config=None, enabled=None)` | `PATCH /v1/webhooks/subscriptions/{id}` |
| `delete_subscription(subscription_id)` | `DELETE /v1/webhooks/subscriptions/{id}` |
| `resume_subscription(subscription_id)` | `POST /v1/webhooks/subscriptions/{id}/resume` |
| `resume_all_subscriptions()` | `POST /v1/webhooks/subscriptions/resume` |
| `dry_run(event_type, config=None, lookback_s=None, limit=None)` | `POST /v1/webhooks/subscriptions/dry-run` |
| `estimate(event_type, config=None, lookback_days=None)` | `POST /v1/webhooks/subscriptions/estimate` |
| `list_addresses()` | `GET /v1/webhooks/addresses` |
| `add_address(address, label="")` | `POST /v1/webhooks/addresses` |
| `delete_address(address_id)` | `DELETE /v1/webhooks/addresses/{id}` |

Every method has an async version prefixed with `a`: `await client.webhooks.aestimate(...)`, `await client.webhooks.acreate_endpoint(...)`, and so on. Management calls cost no credits; the two previews are metered like market data.

### Web3 Authentication

Get API keys programmatically using an Ethereum wallet. No browser or email required.

Free includes every market, route, schema, and served depth, with history limited to the most recent rolling 30 days and a maximum 30-day span per request or replay. Build and above keep the full retained archive. Plans gate capacity and Free's 30-day history window, not route families, schemas, or served depth. The one exception is the live `mempool` WebSocket channel, included with the Pro, Scale and Enterprise plans. See [Pricing](https://www.0xarchive.io/pricing) for plan capacity.

#### Free Tier (SIWE)

```python
# pip install eth-account
from eth_account import Account
from eth_account.messages import encode_defunct

acct = Account.from_key("0xYOUR_PRIVATE_KEY")

# 1. Get SIWE challenge
challenge = client.web3.challenge(acct.address)

# 2. Sign with personal_sign (EIP-191)
signable = encode_defunct(text=challenge.message)
signed = acct.sign_message(signable)
signature = signed.signature.hex()
if not signature.startswith("0x"):
    signature = "0x" + signature

# 3. Submit → receive API key
result = client.web3.signup(message=challenge.message, signature=signature)
print(result.api_key)  # "0xa_..."
```

#### Paid Tier (x402 USDC on Base)

```python
# pip install eth-account
import json
import time
import base64
import secrets
from eth_account import Account
from eth_account.messages import encode_typed_data

acct = Account.from_key("0xYOUR_PRIVATE_KEY")

USDC_ADDRESS = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"

# 1. Get pricing
quote = client.web3.subscribe_quote("build")
# quote.amount = "49000000" ($49 USDC), quote.pay_to = "0x..."

# 2. Build & sign EIP-3009 transferWithAuthorization
nonce_bytes = secrets.token_bytes(32)
valid_after = 0
valid_before = int(time.time()) + 3600

domain = {
    "name": "USD Coin",
    "version": "2",
    "chainId": 8453,
    "verifyingContract": USDC_ADDRESS,
}
types = {
    "TransferWithAuthorization": [
        {"name": "from", "type": "address"},
        {"name": "to", "type": "address"},
        {"name": "value", "type": "uint256"},
        {"name": "validAfter", "type": "uint256"},
        {"name": "validBefore", "type": "uint256"},
        {"name": "nonce", "type": "bytes32"},
    ],
}
message = {
    "from": acct.address,
    "to": quote.pay_to,
    "value": int(quote.amount),
    "validAfter": valid_after,
    "validBefore": valid_before,
    "nonce": "0x" + nonce_bytes.hex(),
}

signable = encode_typed_data(domain, types, message)
signed = acct.sign_message(signable)
signature = signed.signature.hex()
if not signature.startswith("0x"):
    signature = "0x" + signature

# 3. Build x402 payment envelope and base64-encode
payment_payload = base64.b64encode(json.dumps({
    "x402Version": 2,
    "payload": {
        "signature": signature,
        "authorization": {
            "from": acct.address,
            "to": quote.pay_to,
            "value": quote.amount,
            "validAfter": str(valid_after),
            "validBefore": str(valid_before),
            "nonce": "0x" + nonce_bytes.hex(),
        },
    },
}).encode()).decode()

# 4. Submit payment → receive API key + subscription
sub = client.web3.subscribe("build", payment_signature=payment_payload)
print(sub.api_key, sub.tier, sub.expires_at)
```

#### Key Management

```python
# List and revoke keys (requires a fresh SIWE signature)
keys = client.web3.list_keys(message=challenge.message, signature=signature)
client.web3.revoke_key(message=challenge.message, signature=signature, key_id=keys.keys[0].id)
```

### Legacy API (Deprecated)

The following legacy methods are deprecated and will be removed in v2.0. They default to Hyperliquid data:

```python
# Deprecated - use client.hyperliquid.orderbook.get() instead
orderbook = client.orderbook.get("BTC")

# Deprecated - use client.hyperliquid.trades.list() instead
trades = client.trades.list("BTC", start=..., end=...)
```

## WebSocket Client

The WebSocket client supports live subscriptions for supported Hyperliquid and Lighter channels (mainnet and Robinhood Chain) and historical replay. For file-based historical exports, use the [Data Catalog](https://www.0xarchive.io/data).

> WebSocket bulk streaming has been discontinued. For large dataset downloads, use the S3 Parquet bulk export in the [Data Catalog](https://www.0xarchive.io/data). The `stream()`, `multi_stream()`, and `stream_stop()` methods remain for compatibility but are deprecated: each call emits a `DeprecationWarning`, and the server answers with an error message (a `WsError` on `on_message`) instead of data. The `on_batch`, `on_stream_start`, `on_stream_progress`, and `on_stream_complete` handler setters are deprecated too: setting one emits a `DeprecationWarning`, and the handler is never called.

> Lighter supports live subscriptions on `lighter_orderbook`, `lighter_trades`, `lighter_open_interest`, and `lighter_funding` at `wss://api.0xarchive.io/ws` (the client default). `lighter_candles` and `lighter_l3_orderbook` remain replay-only. All six Lighter channels support historical replay, and replay messages have the same shapes as the live ones.

> Lighter on Robinhood Chain supports live subscriptions on `rh_lighter_orderbook`, `rh_lighter_trades`, `rh_lighter_open_interest`, and `rh_lighter_funding` at `wss://api.0xarchive.io/ws` only, with the same message shapes as the mainnet Lighter channels. `rh_lighter_candles` is replay-only. All five channels support historical replay.

> The `mempool` channel (pending Hyperliquid transactions) is served only at `wss://stream.0xarchive.io/ws` and is included with the Pro, Scale and Enterprise plans. See [Pending Transactions (Mempool)](#pending-transactions-mempool).

Every connection selects API version `2026-10-01` (the `version` connection parameter). Server errors arrive on `on_message` as `WsError` messages with a stable `error_code` (see [Error Handling](#error-handling)): for example `unsupported_for_venue` when a channel does not offer the requested mode, `slow_consumer` when the connection fell behind and messages were dropped, and `endpoint_unsupported` when the endpoint does not serve the channel.

```python
import asyncio
from oxarchive import OxArchiveWs, WsOptions

ws = OxArchiveWs(WsOptions(api_key="0xa_your_api_key"))
```

### Real-time Streaming

Subscribe to live market data from Hyperliquid.

```python
import asyncio
from oxarchive import OxArchiveWs, WsOptions

async def main():
    ws = OxArchiveWs(WsOptions(api_key="0xa_your_api_key"))

    # Set up handlers
    ws.on_open(lambda: print("Connected"))
    ws.on_close(lambda code, reason: print(f"Disconnected: {code}"))
    ws.on_error(lambda e: print(f"Error: {e}"))

    # Connect
    await ws.connect()

    # Subscribe to channels
    ws.subscribe_orderbook("BTC")
    ws.subscribe_orderbook("ETH")
    ws.subscribe_trades("BTC")
    ws.subscribe_all_tickers()

    # Handle real-time data
    ws.on_orderbook(lambda coin, data: print(f"{coin}: {data.mid_price}"))
    ws.on_trades(lambda coin, trades: print(f"{coin}: {len(trades)} trades"))

    # Keep running
    await asyncio.sleep(60)

    # Unsubscribe and disconnect
    ws.unsubscribe_orderbook("ETH")
    await ws.disconnect()

asyncio.run(main())
```

Hyperliquid `open_interest` and `funding` also stream live, in addition to historical replay. Subscribe with `ws.subscribe("open_interest", "BTC")` or `ws.subscribe("funding", "BTC")`. Each update's `data` holds `coin` and a `ctx` object with fields such as `openInterest`, `funding`, `markPx`, and `oraclePx`. These channels have no typed callback, so their updates arrive on `on_message` as `WsData` messages.

### Full-Depth L2 Book

`orderbook_full` (Hyperliquid core) and `hip3_orderbook_full` (HIP-3) stream every price level of the book, not just the top 20, aggregated from the order-level book. A subscription opens with an `l4_snapshot` of the whole book, followed by `l4_batch` messages of changed levels. Receive them with `on_l4_snapshot` and `on_l4_batch`; the `channel` argument tells them apart from the L4 channels. Stored history replays over the same messages (see [L4 and Full-Depth Replay](#l4-and-full-depth-replay)) and is also served over REST by `l2_orderbook.history()` and `l2_orderbook.diffs()`.

```python
book = {"B": {}, "A": {}}

def on_snapshot(channel, coin, message):
    data = message["data"]
    book["B"] = {level["px"]: level for level in data["bids"]}
    book["A"] = {level["px"]: level for level in data["asks"]}
    print(coin, data["bid_count"], data["ask_count"], data["mid_price"])

def on_batch(channel, coin, levels):
    for level in levels:  # apply in the order received
        side = book[level["side"]]
        if level["sz"] == 0:
            side.pop(level["px"], None)  # the level was removed
        else:
            side[level["px"]] = level

ws.on_l4_snapshot(on_snapshot)
ws.on_l4_batch(on_batch)
ws.subscribe_orderbook_full("BTC")
ws.subscribe_hip3_orderbook_full("xyz:TSLA")  # case-sensitive
```

Each level is `{"px", "sz", "n"}` with numeric values; a changed level also carries `side` (`"B"` or `"A"`) and `bn`, the block it was applied in. The snapshot's `data` also holds `bid_count`, `ask_count`, `total_bid_size`, `total_ask_size`, `mid_price`, `spread`, `spread_bps` and `is_crossed`, and `last_block_number` on the message is the block the snapshot reflects.

### Live Lighter Data

Live Lighter messages use the same `data` envelope as Hyperliquid live data. Symbols are the ones returned by `client.lighter.instruments.list()`; they are case-insensitive on subscribe and echoed uppercase. Live Lighter data is served at `wss://api.0xarchive.io/ws`, the client default; `wss://stream.0xarchive.io/ws` does not serve Lighter channels and answers a Lighter subscribe with an error pointing to `wss://api.0xarchive.io/ws`. It is available on every plan and metered per message like Hyperliquid live data, with the same per-plan subscription and connection limits and the limit of 10 subscribe operations per second.

```python
import asyncio
from oxarchive import OxArchiveWs, WsError, WsOptions

def on_book(coin, book):
    print(f"Lighter {coin} mid {book.mid_price} ({len(book.bids)} bids, {len(book.asks)} asks)")

def on_trades(coin, legs):
    # Two legs per trade: count distinct trade ids, not legs
    print(f"Lighter {coin}: {len({leg.trade_id for leg in legs})} trades")

def on_context(channel, coin, ctx):
    print(f"Lighter {coin} OI {ctx.open_interest} funding {ctx.funding_rate} mark {ctx.mark_price}")

def on_message(msg):
    if isinstance(msg, WsError):  # lag notices carry error_code "slow_consumer"
        print(f"Server: {msg.error_code}: {msg.message}")

async def main():
    ws = OxArchiveWs(WsOptions(api_key="0xa_your_api_key"))

    # Dedicated Lighter handlers keep Lighter BTC apart from Hyperliquid BTC
    ws.on_lighter_orderbook(on_book)
    ws.on_lighter_trades(on_trades)
    ws.on_lighter_market_context(on_context)
    ws.on_message(on_message)

    await ws.connect()

    ws.subscribe_lighter_orderbook("BTC")                   # one book per second (default)
    ws.subscribe_lighter_orderbook("ETH", interval_ms=250)  # at most one book every 250 ms
    ws.subscribe_lighter_trades("BTC")
    ws.subscribe_lighter_funding("BTC")                     # same message as lighter_open_interest

    await asyncio.sleep(60)
    await ws.disconnect()

asyncio.run(main())
```

The generic form works too: `ws.subscribe("lighter_orderbook", "BTC", interval_ms=500)`.

**`lighter_orderbook`**: every message is a full top-20 book per side, not a diff. Bids and asks are ordered best first, `px` and `sz` are decimal strings exactly as Lighter publishes them, and `n` is always 1 because Lighter does not publish per-level order counts. The server sends the newest book at most once per interval: once per second by default, or at the `interval_ms` you pass (100 to 5000, `lighter_orderbook` only; the SDK raises `ValueError` otherwise). Each book sent is one metered message. On subscribe, the current book is sent right away when one is available; illiquid markets can go minutes without a change. Books arrive on `on_lighter_orderbook` when it is set, otherwise on `on_orderbook`, as `OrderBook` records.

**`lighter_trades`**: each trade arrives as two legs, one per side, sharing `trade_id`. `side` is `"A"` for the ask side and `"B"` for the bid side, `crossed=True` marks the taker leg, `account_index` is that side's Lighter account index (a string), `order_id` is that side's order id, and `start_position` is that account's signed position before the trade. `fee`, `fee_token`, `closed_pnl`, and `direction` are always `None` in live messages. Count trades by distinct `trade_id`, not by list length, and compute volume from one leg per `trade_id`. Trades arrive on `on_lighter_trades` when it is set, otherwise on `on_trades`, as `Trade` records; the raw legs are modelled by `LighterLiveTrade`. Live trades are preliminary. The finalized record, with fields the live stream does not carry (such as fees), is served by `client.lighter.trades.list()`, which returns reconciled trades only; `client.lighter.trades.recent()` serves the preliminary tier.

**`lighter_open_interest` and `lighter_funding`**: both channels carry the same message, updated as Lighter publishes it (about once per second per market), with the latest values sent on subscribe when available. `on_lighter_market_context` receives `(channel, coin, LighterMarketContext)`:

| Field | Wire key | Meaning |
|-------|----------|---------|
| `open_interest` | `openInterest` | Lighter's reported open interest (same value as `client.lighter.open_interest.current()`) |
| `funding_rate` | `funding` | Current funding rate as a fraction (Lighter publishes percent; divided by 100, same as REST `funding_rate`) |
| `premium` | `premium` | Premium as a fraction |
| `mark_price` | `markPx` | Mark price |
| `oracle_price` | `oraclePx` | Lighter's index price |
| `mid_price` | `midPx` | Mid price |
| `day_ntl_volume` | `dayNtlVlm` | 24h quote volume |
| `day_base_volume` | `dayBaseVlm` | 24h base volume |
| `prev_day_price` | `prevDayPx` | Derived from the last trade price and Lighter's 24h percent change |
| `impact_prices` | `impactPxs` | Always `None` (Lighter has no impact prices) |

**Falling behind**: if your connection falls behind `lighter_trades`, `lighter_open_interest`, or `lighter_funding`, the server sends an error notice with `error_code == "slow_consumer"` (for example `Dropped ~N live lighter_trades messages for BTC: ...`) and continues. If the lag persists, it stops that subscription with `Stopped the lighter_trades stream for BTC: your connection is too slow to keep up. Re-subscribe to resume.`; call the subscribe method again to resume. `lighter_orderbook` always sends the newest book; a book skipped between intervals loses nothing because each book is a full state.

### Live Lighter on Robinhood Chain Data

The Robinhood Chain deployment of Lighter streams live on its own channels: `rh_lighter_orderbook`, `rh_lighter_trades`, `rh_lighter_open_interest`, and `rh_lighter_funding`. Each message has exactly the shape of its mainnet counterpart described above, `rh_lighter_orderbook` accepts `interval_ms` (100 to 5000, default one book per second), and the metering, limits, and lag notices are the same. Symbols are those returned by `client.rh_lighter.instruments.list()`: uppercase perps (`BTC`) and dashed spot markets (`AAPL-USDG`), case-insensitive on subscribe. These channels are served at `wss://api.0xarchive.io/ws`, the client default, and not at `wss://stream.0xarchive.io/ws`.

Robinhood Chain symbols collide with mainnet ones, so these messages have their own handlers: `on_rh_lighter_orderbook`, `on_rh_lighter_trades`, and `on_rh_lighter_market_context`. They never reach the mainnet `on_lighter_*` handlers. Without a dedicated handler, books and trades fall back to `on_orderbook` and `on_trades`; `WsData.channel` on `on_message` always names the channel.

```python
ws.on_rh_lighter_orderbook(lambda coin, book: print(f"Robinhood Chain {coin} mid {book.mid_price}"))
ws.on_rh_lighter_trades(lambda coin, legs: print(f"Robinhood Chain {coin}: {len({l.trade_id for l in legs})} trades"))
ws.on_rh_lighter_market_context(lambda channel, coin, ctx: print(f"{coin} OI {ctx.open_interest}"))

ws.subscribe_rh_lighter_orderbook("AAPL-USDG")                 # one book per second (default)
ws.subscribe_rh_lighter_orderbook("BTC", interval_ms=500)
ws.subscribe_rh_lighter_trades("BTC")
ws.subscribe_rh_lighter_funding("BTC")                         # same message as rh_lighter_open_interest

# Generic form
ws.subscribe("rh_lighter_orderbook", "BTC", interval_ms=250)
```

Live trades are preliminary; `client.rh_lighter.trades.list()` serves the finalized record.

### Pending Transactions (Mempool)

The `mempool` channel streams signed Hyperliquid transactions (orders, cancels, modifies, TWAPs, leverage changes, transfers and every other action type) as our Hyperliquid node receives them from its peers, before they are included in a block. It covers every Hyperliquid product: perps, HIP-3, HIP-4 and spot.

- **Live only.** Pending transactions are never stored. There is no replay, history, REST route or export; `replay()` raises `ValueError` for it before sending.
- **One endpoint.** It is served only at `wss://stream.0xarchive.io/ws` (`oxarchive.websocket.STREAM_WS_URL`), with the same API key and protocol. At `wss://api.0xarchive.io/ws`, the client default, a subscribe is answered with a `WsError` whose `error_code` is `endpoint_unsupported`. Use a separate client for the channels served at the default endpoint.
- **Plans.** It is included with the Pro, Scale and Enterprise plans; on other plans a subscribe is answered with `error_code == "forbidden"`. Every other channel stays on every plan, Free included. Each data message is metered like any other WebSocket message.

```python
import asyncio
from oxarchive import OxArchiveWs, WsError, WsOptions
from oxarchive.websocket import STREAM_WS_URL

async def main():
    ws = OxArchiveWs(WsOptions(api_key="0xa_your_api_key", ws_url=STREAM_WS_URL))

    def on_mempool(symbol, items):
        for item in items:
            print(symbol, item.received_at, item.action["type"], item.symbols)

    def on_message(msg):
        if isinstance(msg, WsError):
            print(msg.error_code, msg.message)

    ws.on_mempool(on_mempool)
    ws.on_message(on_message)
    await ws.connect()

    ws.subscribe_mempool("BTC")       # actions that reference BTC
    ws.subscribe_mempool("xyz:TSLA")  # HIP-3; spot "HYPE-USDC", HIP-4 "#49720"
    # ws.subscribe_mempool()          # pending transactions our node receives (unfiltered)

    await asyncio.sleep(60)
    await ws.disconnect()

asyncio.run(main())
```

`symbol` is optional on this channel only. Without it you receive every pending transaction our Hyperliquid node receives; with it, every action whose asset ids include that market, whole (an order batch that touches `BTC` and `ETH` reaches both subscriptions). Symbols are spelled as everywhere else: perps `BTC`, HIP-3 `xyz:TSLA`, spot `HYPE-USDC` (`HYPE/USDC` is also accepted) and HIP-4 `#49720`. An unknown symbol is answered with `invalid_symbol`. The `subscribed` acknowledgement carries the canonical symbol, or `None` for the unfiltered stream.

The server sends one message per batch of transactions as it arrives. `on_mempool` receives the subscription's symbol (`None` when unfiltered) and one `MempoolItem` per signed action; `on_message` receives the whole message as `WsMempoolData`.

| Field | Description |
|-------|-------------|
| `received_at` | When our node received the transaction: an RFC 3339 UTC string with nanosecond precision. Not a block time. |
| `received_at_ms` | The same time in Unix milliseconds |
| `symbols` | Markets the action's asset ids reference, in first-seen order without repeats. Empty for actions with no market, such as transfers, `noop`, `scheduleCancel` and validator actions |
| `action` | The action exactly as signed, in Hyperliquid's exchange-action format: asset ids (`a` or `asset`) rather than symbols, prices and sizes as strings, keys in the order sent |
| `nonce` | The action's nonce |
| `vault_address` | The vault or subaccount the action acts for, or `None` |
| `expires_after_ms` | The action's `expiresAfter` in Unix milliseconds, or `None` |
| `signature` | `MempoolSignature` with `r`, `s` and `v`. The signer's address is not included |

`action["type"]` names the action, for example `order`, `cancel`, `cancelByCloid`, `modify`, `batchModify`, `scheduleCancel`, `twapOrder`, `twapCancel`, `updateLeverage`, `updateIsolatedMargin`, `noop`, `evmRawTx`, or a transfer such as `usdSend`, `spotSend`, `usdClassTransfer` or `sendAsset`. Hyperliquid adds action types, so handle types you do not recognise.

A pending transaction is not an executed one: it can still be rejected, expire or never land in a block. The same signed action can occasionally arrive twice; deduplicate on `signature` if that matters to you.

**Volume and limits**: the unfiltered stream is several megabytes per second before compression. The client negotiates permessage-deflate compression by default; subscribe with a symbol where you can. Unfiltered subscriptions are limited server-wide, and when they are at capacity a subscribe without a symbol is answered with `rate_limited`; symbol subscriptions are not capped this way. A connection that reads too slowly is disconnected, as on any channel, and the usual per-connection limits apply (subscriptions per plan, 10 subscribe operations per second). If the feed is temporarily unavailable, a subscribe is answered with `upstream_unavailable`.

### Historical Replay

Replay historical data with timing preserved. Perfect for backtesting.

> **Important:** Replay data is delivered via `on_historical_data()`, NOT `on_trades()` or `on_orderbook()`.
> The real-time callbacks only receive live market data from subscriptions.

```python
import asyncio
import time
from oxarchive import OxArchiveWs, WsOptions

async def main():
    ws = OxArchiveWs(WsOptions(api_key="ox_..."))

    # Handle replay data - this is where historical records arrive
    ws.on_historical_data(lambda coin, ts, data:
        print(f"{ts}: {data['mid_price']}")
    )

    # Replay lifecycle events
    ws.on_replay_start(lambda ch, coin, start, end, speed:
        print(f"Starting replay: {ch}/{coin} at {speed}x")
    )

    ws.on_replay_complete(lambda ch, coin, sent:
        print(f"Replay complete: {sent} records")
    )

    await ws.connect()

    # Start replay at 10x speed
    await ws.replay(
        "orderbook", "BTC",
        start=int(time.time() * 1000) - 86400000,  # 24 hours ago
        end=int(time.time() * 1000),                # End of bounded replay window
        speed=10                                     # Optional, defaults to 1x
    )

    # Lighter replay with granularity. Replay messages have the same shapes
    # as the live Lighter messages.
    await ws.replay(
        "lighter_orderbook", "BTC",
        start=int(time.time() * 1000) - 86400000,
        end=int(time.time() * 1000),
        speed=10,
        granularity="10s"  # Options: 'checkpoint', '30s', '10s', '1s', 'tick'
    )

    # Handle tick-level data (granularity='tick')
    ws.on_historical_tick_data(lambda coin, checkpoint, deltas:
        print(f"Checkpoint: {len(checkpoint['bids'])} bids, Deltas: {len(deltas)}")
    )

    # Control playback
    await ws.replay_pause()
    await ws.replay_resume()
    await ws.replay_seek(int(time.time() * 1000) - 43_200_000)  # Jump to 12 hours ago
    await ws.replay_stop()

asyncio.run(main())
```

`on_replay_data` receives every replayed record together with its channel: `(channel, coin, timestamp, record)`. Lighter and Robinhood Chain records are decoded with the same parsers as live messages: an `OrderBook` on `lighter_orderbook`, a `list[Trade]` (one leg per message) on `lighter_trades` and a `LighterMarketContextUpdate` on `lighter_open_interest` and `lighter_funding`, and likewise for the `rh_lighter_*` channels. Other channels' records are passed through as sent. `decode_lighter_payload(channel, coin, data)` applies the same decoding to a `replay_snapshot`.

```python
def on_record(channel, coin, timestamp, record):
    if channel == "lighter_trades":
        for leg in record:  # list[Trade]
            print(timestamp, leg.side, leg.price, leg.size, leg.account_index)
    elif channel == "lighter_orderbook":
        print(timestamp, record.mid_price)  # OrderBook

ws.on_replay_data(on_record)
await ws.replay("lighter_trades", "BTC", start=start_ms, end=end_ms, speed=10)
```

Replay only runs on channels that replay (see [Available Channels](#available-channels)): `replay()` and `multi_replay()` raise `ValueError` before sending for a live-only channel such as `ticker`, `spot_orderbook` or `spot_trades`.

#### L4 and Full-Depth Replay

Every L4 channel replays: `l4_diffs` and `l4_orders` (Hyperliquid core), `hip3_l4_diffs` and `hip3_l4_orders`, `hip4_l4_diffs` and `hip4_l4_orders`, and `spot_l4_diffs` and `spot_l4_orders`. So do the full-depth L2 channels `orderbook_full` and `hip3_orderbook_full`. Replay is available from each product's first L4 checkpoint (`available_from` in `client.capabilities()`; a coin listed later starts at its own first checkpoint).

These replays are bulk. A replay begins with one typed `WsL4Snapshot` from the nearest checkpoint at or before `start` and continues with ordered `WsL4Batch` messages until `end`, as fast as the connection takes them: `speed` is ignored, `replay_seek()` is refused (restart the replay at the new start instead), and each replays on its own, never inside `multi_replay()`. Apply each batch in the order received; use the snapshot's `last_block_number` with each event's block/sequence fields as the checkpoint boundary. Full-depth batches carry changed price levels `{"side", "px", "sz", "n", "bn"}`, exactly like the live channel. The dedicated `on_l4_snapshot` and `on_l4_batch` callbacks keep their raw payload shapes; `on_message` receives the typed envelopes.

```python
from oxarchive import WsL4Batch, WsL4Snapshot


def on_message(message):
    if isinstance(message, WsL4Snapshot):
        rebuild_book_from_snapshot(message.data)
    elif isinstance(message, WsL4Batch):
        for event in message.data:
            apply_l4_event(event)


ws.on_message(on_message)
await ws.replay("l4_diffs", "BTC", start=..., end=...)
await ws.replay("hip3_l4_orders", "xyz:TSLA", start=..., end=...)
await ws.replay("spot_l4_diffs", "PURR-USDC", start=..., end=...)
await ws.replay("orderbook_full", "ETH", start=..., end=...)
```

### Gap Detection

During historical replay, the server automatically detects gaps in the data and notifies the client. This helps identify periods where data may be missing.

```python
import asyncio
from oxarchive import OxArchiveWs, WsOptions

async def main():
    ws = OxArchiveWs(WsOptions(api_key="ox_..."))

    # Handle gap notifications during replay
    def handle_gap(channel, coin, gap_start, gap_end, duration_minutes):
        print(f"Gap detected in {channel}/{coin}:")
        print(f"  From: {gap_start}")
        print(f"  To: {gap_end}")
        print(f"  Duration: {duration_minutes} minutes")

    ws.on_gap(handle_gap)

    await ws.connect()

    # Start replay - gaps will be reported via on_gap callback
    await ws.replay(
        "orderbook", "BTC",
        start=int(time.time() * 1000) - 86400000,
        end=int(time.time() * 1000),
        speed=10
    )

asyncio.run(main())
```

Gap thresholds vary by channel:
- **orderbook**, **candles**, **liquidations**: 2 minutes
- **trades**: 60 minutes (trades can naturally have longer gaps during low activity periods)

### WebSocket Configuration

```python
ws = OxArchiveWs(WsOptions(
    api_key="0xa_your_api_key",
    ws_url="wss://api.0xarchive.io/ws",  # Optional; STREAM_WS_URL for mempool
    auto_reconnect=True,                  # Auto-reconnect on disconnect (default: True)
    reconnect_delay=1.0,                  # Initial reconnect delay in seconds (default: 1.0)
    max_reconnect_attempts=10,            # Max reconnect attempts (default: 10)
    ping_interval=30.0,                   # Keep-alive ping interval in seconds (default: 30.0)
))
```

### Available Channels

The tables below mirror `client.capabilities()`. The same table ships in the SDK as `oxarchive.websocket.WS_CHANNELS`: `subscribe()` raises `ValueError` before sending for a channel without live data, `replay()` for a channel without replay, and `multi_replay()` also for the bulk L4 and full-depth channels, which replay on their own.

```python
from oxarchive.websocket import WS_CHANNELS

spec = WS_CHANNELS["spot_l4_diffs"]
print(spec.venue, spec.live, spec.replay, spec.bulk_replay)  # spot True True True

spec = WS_CHANNELS["mempool"]
print(spec.ws_endpoint, spec.plans)  # wss://stream.0xarchive.io/ws ('pro', 'scale', 'enterprise')
```

#### Hyperliquid Channels

| Channel | Description | Requires Coin | Live Subscription | Historical Replay |
|---------|-------------|---------------|-------------------|-------------------|
| `orderbook` | L2 order book updates | Yes | Yes | Yes |
| `trades` | Trade/fill updates | Yes | Yes | Yes |
| `candles` | OHLCV candle data | Yes | No | Yes |
| `liquidations` | Liquidation events (2025-12-22+) | Yes | Yes | Yes |
| `open_interest` | Open interest snapshots | Yes | Yes | Yes |
| `funding` | Funding rate records | Yes | Yes | Yes |
| `ticker` | Price and 24h volume | Yes | Yes | No |
| `all_tickers` | All market tickers | No | Yes | No |
| `l4_diffs` | L4 orderbook diffs with user attribution | Yes | Yes | Yes (bulk) |
| `l4_orders` | Order lifecycle events with user attribution | Yes | Yes | Yes (bulk) |
| `orderbook_full` | Full-depth L2 order book: every price level, then changed levels | Yes | Yes | Yes (bulk) |
| `mempool` | Pending transactions on every Hyperliquid product, before they are in a block (Pro, Scale and Enterprise plans; served only at `wss://stream.0xarchive.io/ws`) | No (optional filter) | Yes | No |

Bulk replays open with an `l4_snapshot` and continue with ordered `l4_batch` messages; see [L4 and Full-Depth Replay](#l4-and-full-depth-replay).

> **Note:** ``liquidations`` and ``hip3_liquidations`` now stream live. Each item shares the trades wire shape (a fill row with ``is_liquidation: true``). The SDK exposes a typed ``on_liquidations`` callback that decodes them into :class:`Liquidation` records.

#### HIP-3 Builder Perps Channels

| Channel | Description | Requires Coin | Live Subscription | Historical Replay |
|---------|-------------|---------------|-------------------|-------------------|
| `hip3_orderbook` | HIP-3 L2 order book snapshots | Yes | Yes | Yes |
| `hip3_trades` | HIP-3 trade/fill updates | Yes | Yes | Yes |
| `hip3_candles` | HIP-3 OHLCV candle data | Yes | No | Yes |
| `hip3_open_interest` | HIP-3 open interest snapshots | Yes | Yes | Yes |
| `hip3_funding` | HIP-3 funding rate records | Yes | Yes | Yes |
| `hip3_liquidations` | HIP-3 liquidation events (2025-12-22+) | Yes | Yes | Yes |
| `hip3_l4_diffs` | HIP-3 L4 orderbook diffs | Yes | Yes | Yes (bulk) |
| `hip3_l4_orders` | HIP-3 order lifecycle events | Yes | Yes | Yes (bulk) |
| `hip3_orderbook_full` | HIP-3 full-depth L2 order book: every price level, then changed levels | Yes | Yes | Yes (bulk) |

> **Note:** Stored full-depth history is also served over REST by `l2_orderbook.history()` and `l2_orderbook.diffs()`.

> **Note:** HIP-3 coins are case-sensitive (e.g., `xyz:TSLA`, `xyz:XYZ100`). Do not uppercase them.

#### HIP-4 Outcome Market Channels

| Channel | Description | Requires Coin | Live Subscription | Historical Replay |
|---------|-------------|---------------|-------------------|-------------------|
| `hip4_orderbook` | HIP-4 L2 order book snapshots | Yes | No | Yes |
| `hip4_trades` | HIP-4 trade/fill updates | Yes | Yes | Yes |
| `hip4_open_interest` | HIP-4 per-side OI ticks | Yes | No | Yes |
| `hip4_l4_diffs` | HIP-4 L4 orderbook diffs | Yes | Yes | Yes (bulk) |
| `hip4_l4_orders` | HIP-4 order lifecycle events | Yes | Yes | Yes (bulk) |

`hip4_orderbook` and `hip4_open_interest` replay stored history but do not stream live, so `subscribe()` raises `ValueError` for them before sending. For the live book, subscribe to `hip4_l4_diffs`; for the current book and open interest, use `client.hyperliquid.hip4.orderbook` and `client.hyperliquid.hip4.open_interest` over REST.

HIP-4 has no funding or liquidation channels, and no candle channel: HIP-4 candles are served over REST. Subscribe with the raw `#N` coin form (`N = 10 * outcome_id + side`, where side 0 is Yes and 1 is No); the SDK passes it through unmodified in the JSON body. When a market settles, the server pushes a single `outcome_settled` frame and proactively unsubscribes the client from every `hip4_*` channel for that coin. Use `OxArchiveWs.on_outcome_settled()` to handle the event:

```python
# The Yes side of an open BTC price outcome
coin = next(
    s.symbol for s in client.symbols.list()
    if s.exchange == "hip4" and not s.is_settled
    and (s.slug or "").startswith("btc-above-") and "-yes-" in s.slug
)

def on_settled(msg):
    print(f"Outcome {msg.outcome_id} side {msg.side} settled at {msg.settlement_value}")
    # Server has already auto-unsubscribed; the SDK mirrors that locally.

ws.on_outcome_settled(on_settled)
ws.subscribe_hip4_trades(coin)
ws.subscribe_hip4_l4_diffs(coin)
```

#### Hyperliquid Spot Channels

| Channel | Description | Requires Coin | Live Subscription | Historical Replay |
|---------|-------------|---------------|-------------------|-------------------|
| `spot_orderbook` | Spot L2 order book snapshots | Yes | Yes | No |
| `spot_trades` | Spot trade/fill updates | Yes | Yes | No |
| `spot_twap` | Spot TWAP status updates (served over REST only: `client.spot.twap`) | Yes | No | No |
| `spot_l4_diffs` | Spot L4 orderbook diffs | Yes | Yes | Yes (bulk) |
| `spot_l4_orders` | Spot L4 order lifecycle events | Yes | Yes | Yes (bulk) |

> **Note:** Spot symbols are dashed canonical (`HYPE-USDC`, `PURR-USDC`); the server resolves dashed to wire format internally. The existing `on_orderbook` and `on_trades` typed callbacks fire for `spot_orderbook` and `spot_trades`. Spot TWAP statuses do not stream: `subscribe_spot_twap()` raises `ValueError` before sending; read them with `client.spot.twap.history()` or `client.spot.twap.by_user()`.

```python
ws = OxArchiveWs(WsOptions(api_key="ox_..."))
await ws.connect()
ws.on_orderbook(lambda coin, ob: print(f"{coin} mid: {ob.mid_price}"))
ws.subscribe_spot_orderbook("HYPE-USDC")
ws.subscribe_spot_trades("HYPE-USDC")
```

#### Lighter Channels

| Channel | Description | Requires Coin | Live Subscription | Historical Replay |
|---------|-------------|---------------|-------------------|-------------------|
| `lighter_orderbook` | Lighter L2 order book (live: full top-20 book per side, 1 per second by default, `interval_ms` 100 to 5000) | Yes | Yes | Yes |
| `lighter_trades` | Lighter trade/fill updates (live: two legs per trade) | Yes | Yes | Yes |
| `lighter_candles` | Lighter OHLCV candle data | Yes | No | Yes |
| `lighter_open_interest` | Lighter open interest (live: market context, same message as `lighter_funding`) | Yes | Yes | Yes |
| `lighter_funding` | Lighter funding rates (live: market context, same message as `lighter_open_interest`) | Yes | Yes | Yes |
| `lighter_l3_orderbook` | Lighter L3 order-level orderbook | Yes | No | Yes |

Live Lighter subscriptions are served at `wss://api.0xarchive.io/ws`. Replay messages of `lighter_orderbook`, `lighter_trades`, `lighter_open_interest` and `lighter_funding` have the shapes of the live messages described under Live Lighter Data above (a replayed trade message holds one leg); `on_replay_data` decodes them. Current Lighter data is also available through the REST resources, and historical Lighter data through REST, WebSocket replay, or exports.

#### Lighter on Robinhood Chain Channels

| Channel | Description | Requires Coin | Live Subscription | Historical Replay |
|---------|-------------|---------------|-------------------|-------------------|
| `rh_lighter_orderbook` | L2 order book (live: full top-20 book per side, 1 per second by default, `interval_ms` 100 to 5000) | Yes | Yes | Yes (from 2026-08-22) |
| `rh_lighter_trades` | Trade/fill updates (live: two legs per trade) | Yes | Yes | Yes (from 2026-06-26) |
| `rh_lighter_candles` | OHLCV candle data | Yes | No | Yes (from 2026-06-26) |
| `rh_lighter_open_interest` | Open interest (live: market context, same message as `rh_lighter_funding`) | Yes | Yes | Yes (from 2026-08-22) |
| `rh_lighter_funding` | Funding rates (live: market context, same message as `rh_lighter_open_interest`) | Yes | Yes | Yes (from 2026-08-22) |

There is no L3 channel for this deployment. Live Robinhood Chain subscriptions are served at `wss://api.0xarchive.io/ws` only. Replay messages have the live shapes, like mainnet Lighter replay, and a multi-channel replay must stay within the `rh_lighter_*` family.

#### Candle Replay

```python
# Replay candles at 10x speed
await ws.replay(
    "candles", "BTC",
    start=int(time.time() * 1000) - 86400000,
    end=int(time.time() * 1000),
    speed=10,
    interval="15m"  # 1m, 5m, 15m, 30m, 1h, 4h, 1d, 1w
)

# Lighter candles
await ws.replay(
    "lighter_candles", "BTC",
    start=int(time.time() * 1000) - 86400000,
    end=int(time.time() * 1000),
    speed=10,
    interval="5m"
)
```

#### HIP-3 Replay

```python
# Replay HIP-3 orderbook at 50x speed
await ws.replay(
    "hip3_orderbook", "xyz:TSLA",
    start=int(time.time() * 1000) - 3600000,
    end=int(time.time() * 1000),
    speed=50,
)

# HIP-3 candles
await ws.replay(
    "hip3_candles", "xyz:TSLA",
    start=int(time.time() * 1000) - 86400000,
    end=int(time.time() * 1000),
    speed=100,
    interval="1h"
)
```

#### Open Interest / Funding Replay

The Hyperliquid `open_interest` and `funding` channels support both replay and live subscriptions (see Real-time Streaming above), as do `hip3_open_interest` and `hip3_funding`. `lighter_open_interest` and `lighter_funding` support both replay and live subscriptions (see Live Lighter Data above), as do `rh_lighter_open_interest` and `rh_lighter_funding`.

```python
# Replay open interest at 50x speed
await ws.replay(
    "open_interest", "BTC",
    start=int(time.time() * 1000) - 86400000,
    end=int(time.time() * 1000),
    speed=50,
)

# Replay funding rates
await ws.replay(
    "funding", "ETH",
    start=int(time.time() * 1000) - 86400000,
    end=int(time.time() * 1000),
    speed=50,
)

# HIP-3 funding replay
await ws.replay(
    "hip3_funding", "xyz:TSLA",
    start=int(time.time() * 1000) - 86400000,
    end=int(time.time() * 1000),
    speed=100,
)
```

### Multi-Channel Replay

Replay multiple channels in a single synchronized timeline. All data is interleaved by timestamp, preserving the original timing relationships between orderbook updates, trades, funding rates, and open interest. Before the timeline begins, `replay_snapshot` messages provide the initial state for each channel. All channels must belong to one venue, and the bulk L4 and full-depth channels replay on their own, so `multi_replay()` raises `ValueError` for them before sending.

```python
import asyncio
import time
from oxarchive import OxArchiveWs, WsOptions

async def main():
    ws = OxArchiveWs(WsOptions(api_key="ox_..."))

    # Handle initial state snapshots (sent before timeline starts)
    def on_snapshot(channel, coin, timestamp, data):
        print(f"Initial {channel} state at {timestamp}:")
        if channel == "orderbook":
            print(f"  Mid price: {data.get('mid_price')}")
        elif channel == "funding":
            print(f"  Rate: {data.get('funding_rate')}")
        elif channel == "open_interest":
            print(f"  OI: {data.get('open_interest')}")

    # Handle interleaved timeline data, with the channel each record belongs to
    def on_record(channel, coin, timestamp, record):
        print(f"[{channel}] {coin} @ {timestamp}: {record}")

    ws.on_replay_snapshot(on_snapshot)
    ws.on_replay_data(on_record)

    ws.on_replay_start(lambda ch, coin, start, end, speed:
        print(f"Multi-channel replay started at {speed}x")
    )
    ws.on_replay_complete(lambda ch, coin, sent:
        print(f"Replay complete: {sent} total records")
    )

    await ws.connect()

    # Replay orderbook + trades + funding together at 10x speed
    await ws.multi_replay(
        ["orderbook", "trades", "funding"],
        "BTC",
        start=int(time.time() * 1000) - 86400000,
        end=int(time.time() * 1000),
        speed=10,
    )

    await asyncio.sleep(60)
    await ws.disconnect()

asyncio.run(main())
```

**Multi-channel replay examples by exchange:**

```python
# Hyperliquid: orderbook + trades + OI + funding
await ws.multi_replay(
    ["orderbook", "trades", "open_interest", "funding"],
    "BTC",
    start=start_ms,
    end=end_ms,
    speed=10,
)

# Lighter: orderbook + trades + OI + funding
await ws.multi_replay(
    ["lighter_orderbook", "lighter_trades", "lighter_open_interest", "lighter_funding"],
    "BTC",
    start=start_ms,
    end=end_ms,
    speed=10,
)

# Lighter on Robinhood Chain: orderbook + trades + OI + funding
await ws.multi_replay(
    ["rh_lighter_orderbook", "rh_lighter_trades", "rh_lighter_open_interest", "rh_lighter_funding"],
    "BTC",
    start=start_ms,
    end=end_ms,
    speed=10,
)

# HIP-3: orderbook + trades + OI + funding
await ws.multi_replay(
    ["hip3_orderbook", "hip3_trades", "hip3_open_interest", "hip3_funding"],
    "xyz:TSLA",
    start=start_ms,
    end=end_ms,
    speed=10,
)
```

## Timestamp Formats

The SDK accepts timestamps in multiple formats and sends them as Unix milliseconds. A time without a time zone is UTC: a naive `datetime`, an ISO string without an offset (`"2026-10-01T12:00:00"`), and a date alone (`"2026-10-01"`, midnight UTC) mean the same instant on every machine, whatever its local time zone. For the current time, use an aware datetime such as `datetime.now(timezone.utc)`; a naive `datetime.now()` is local wall-clock time and would be read as UTC.

```python
import time
from datetime import datetime, timedelta, timezone

# Unix milliseconds (int): one hour ago
client.hyperliquid.orderbook.get("BTC", timestamp=int(time.time() * 1000) - 3_600_000)

# ISO string: a date alone is midnight UTC; a time without an offset is UTC
day = (datetime.now(timezone.utc) - timedelta(days=2)).date().isoformat()  # for example "2026-10-01"
client.hyperliquid.orderbook.history("BTC", start=day, end=f"{day}T01:00:00")

# datetime object: naive datetimes are UTC, aware ones keep their offset
start = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=2)  # naive, read as UTC
client.hyperliquid.orderbook.history(
    "BTC",
    start=start,
    end=datetime.now(timezone.utc),  # aware
)
```

## Error Handling

Every error the API returns raises `OxArchiveError`. Branch on `error_code`, a stable machine-readable code, rather than on the message:

```python
from datetime import datetime, timedelta, timezone

from oxarchive import Client, OxArchiveError

client = Client(api_key="0xa_your_api_key")
now = datetime.now(timezone.utc)

try:
    trades = client.hyperliquid.trades.history("BTC", start=now - timedelta(hours=1), end=now, side="both")
except OxArchiveError as e:
    print(e.error_code)    # "invalid_parameter"
    print(e.status)        # 400 (also e.code)
    print(e.param)         # "side"
    print(e.valid_values)  # ["buy", "sell"]
    print(e.message)       # "Invalid side 'both'. Use buy or sell."
    print(e.request_id)    # quote it when contacting support
    print(e.details)       # the whole error body, including route-specific fields
```

| `error_code` | Meaning |
|--------------|---------|
| `invalid_parameter` | A parameter failed to parse or validate; `param` and `valid_values` say which and what it accepts |
| `invalid_symbol` | The symbol is not listed on this venue |
| `invalid_interval` | The interval is not one the route accepts |
| `invalid_cursor` | The cursor is malformed, stale, or was issued for other filters |
| `invalid_time_range` | `start` is after `end`, or a time could not be parsed |
| `range_before_coverage` | The whole range ends before the dataset's first served instant |
| `historical_range_exceeded` | The span is longer than the plan allows per request |
| `historical_depth_exceeded` | The request reaches further back than the plan's history window |
| `unsupported_for_venue` | The datatype, or the WebSocket mode, is not offered on this venue; `details["available_on"]` lists where it is |
| `route_not_found` | No route matches the path |
| `not_found` | The route exists but the resource id does not |
| `unauthorized`, `forbidden` | Missing or invalid API key; not allowed on this plan |
| `insufficient_credits`, `rate_limited` | Monthly credits spent; too many requests |
| `conflict` | The request conflicts with current state |
| `upstream_unavailable`, `internal_error` | Retry later; quote `request_id` if it persists |
| `endpoint_unsupported`, `slow_consumer` | WebSocket only (see below) |
| `positions_unavailable`, `api_key_limit_reached`, `oauth_not_permitted` | Route-specific |

The set is exported as `oxarchive.ERROR_CODES` (and the `ErrorCode` type). A server can add a code before an SDK release lists it, so treat an unknown value like a generic error. A request the SDK refuses before sending, such as `client.hyperliquid.trades.recent()`, raises `OxArchiveError` with the code the API would have returned; a network failure raises it with `status` 0 and no `error_code`.

WebSocket errors arrive on `on_message` as `WsError` messages with the same `error_code` and a `message`. Two codes are WebSocket only: `slow_consumer` (the connection fell behind a stream and messages were dropped; re-subscribe or restart the replay to resync) and `endpoint_unsupported` (the endpoint does not serve the channel or operation; the message names the one that does).

```python
from oxarchive import WsError

def on_message(msg):
    if isinstance(msg, WsError):
        if msg.error_code == "slow_consumer":
            ws.subscribe_trades("BTC")  # resync
        else:
            print(msg.error_code, msg.message)

ws.on_message(on_message)
```

## Type Hints

Full type hint support with Pydantic models:

```python
from oxarchive import Client, LighterGranularity
from oxarchive.types import (
    OrderBook, Trade, Instrument, LighterInstrument, FundingRate, OpenInterest, Candle, Liquidation,
    LiquidationVolume, CoinFreshness, CoinSummary, PriceSnapshot,
    WsReplaySnapshot, LighterLiveTrade, LighterMarketContext, LighterMarketContextUpdate,
    LighterLiquidation, LighterLiquidationVolume, ResponseMeta,
    Position, PositionChange, MarketPosition, MarketPositionsSummary, AccountSummary,
    WalletPositions, LighterL1Accounts,
    CvdBucket, Hip3OracleExternalPrice, Hip4Question, WalletClassification, SymbolEntry,
    WebhookSubscription, WebhookEstimate, WebhookLimits,
    Capability, ErrorCode,
)
from oxarchive.resources.trades import CursorResponse

# Orderbook reconstruction types
from oxarchive import (
    OrderBookReconstructor,
    OrderbookDelta,
    TickData,
    ReconstructedOrderBook,
    ReconstructOptions,
)

client = Client(api_key="0xa_your_api_key")

orderbook: OrderBook = client.hyperliquid.orderbook.get("BTC")
result: CursorResponse[list[Trade]] = client.hyperliquid.trades.history("BTC", start=..., end=...)
more: bool = result.has_more
print(result.meta.venue, result.meta.symbol)  # hyperliquid BTC
capabilities: list[Capability] = client.capabilities()

# Lighter current data is available, so recent() is available
recent: list[Trade] = client.lighter.trades.recent("BTC")

# Account positions: typed rows plus the response meta
current: CursorResponse[WalletPositions] = client.hyperliquid.positions.get("0xabc...")
meta: ResponseMeta = current.meta
legs: CursorResponse[list[PositionChange]] = client.rh_lighter.positions.changes(4521, start=..., end=...)

# Cumulative volume delta, wallet classification and webhooks
cvd: CursorResponse[list[CvdBucket]] = client.hyperliquid.cvd.history("BTC", start=...)
wallets: WalletClassification = client.hyperliquid.wallets.classify(limit=10)
rules: list[WebhookSubscription] = client.webhooks.list_subscriptions()

# Lighter granularity type hint
granularity: LighterGranularity = "10s"

# Orderbook reconstruction
tick_data: TickData = client.lighter.orderbook.history_tick("BTC", start=..., end=...)
snapshots: list[ReconstructedOrderBook] = client.lighter.orderbook.history_reconstructed("BTC", start=..., end=...)
```

## Data Catalog

For large-scale data exports (route-specific order books, fill-level trade history, and other retained datasets), use the [Data Catalog](https://www.0xarchive.io/data). It lets you choose markets, datasets, and date ranges, see a live quote, and export zstd-compressed Parquet.

## Links

- [API Docs](https://docs.0xarchive.io)
- [TypeScript SDK](https://npmjs.com/package/@0xarchive/sdk)
- [Rust SDK](https://crates.io/crates/oxarchive)
- [CLI](https://npmjs.com/package/@0xarchive/cli)
- [MCP Server](https://docs.0xarchive.io/mcp-server)
- [0xArchive Skill](https://github.com/0xArchiveIO/0xarchive-skill)
- [Examples](https://github.com/0xArchiveIO/examples)

## Requirements

- Python 3.9+
- httpx
- pydantic

## License

MIT
