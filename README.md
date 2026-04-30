# oxarchive

Python client for 0xArchive market data in notebooks, research scripts, and data pipelines.

0xArchive is granular market data infrastructure for Hyperliquid and Lighter.xyz. HIP-3 builder perps live under the Hyperliquid namespace at `/v1/hyperliquid/hip3` and `client.hyperliquid.hip3`.

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
from oxarchive import Client

client = Client(api_key="0xa_your_api_key")

# First successful call: Hyperliquid BTC order book
hl_orderbook = client.hyperliquid.orderbook.get("BTC")
print(f"Hyperliquid BTC mid price: {hl_orderbook.mid_price}")

# Lighter.xyz uses its own venue client
lighter_orderbook = client.lighter.orderbook.get("BTC")
print(f"Lighter BTC mid price: {lighter_orderbook.mid_price}")

# Hyperliquid HIP-3 builder perps stay under client.hyperliquid.hip3
hip3_instruments = client.hyperliquid.hip3.instruments.list()
hip3_orderbook = client.hyperliquid.hip3.orderbook.get("km:US500")
hip3_trades = client.hyperliquid.hip3.trades.recent("km:US500")
hip3_funding = client.hyperliquid.hip3.funding.current("xyz:XYZ100")
hip3_oi = client.hyperliquid.hip3.open_interest.current("xyz:XYZ100")

# Get historical order book snapshots
history = client.hyperliquid.orderbook.history(
    "ETH",
    start="2024-01-01",
    end="2024-01-02",
    limit=100
)
```

## Choose Your Next Path

| Need | Link |
| --- | --- |
| First authenticated route | [Quick Start](https://www.0xarchive.io/docs/quick-start) |
| SDK install and route docs | [SDK docs](https://www.0xarchive.io/docs/sdks) |
| Claude Code, GPT Codex, and coding-agent workflows | [AI Clients](https://www.0xarchive.io/docs/ai-clients) |
| File-based historical pulls | [Data Catalog](https://www.0xarchive.io/data) |
| Route contract and machine context | [OpenAPI](https://www.0xarchive.io/openapi.json), [llms.txt](https://www.0xarchive.io/llms.txt) |
| Plans and limits | [Pricing](https://www.0xarchive.io/pricing) |

## Data Coverage

| Venue | Coverage | Notes |
| --- | --- | --- |
| Hyperliquid | April 2023+ | Perpetuals across the full venue |
| Hyperliquid HIP-3 | February 2026+ | Free tier: `km:US500`. Build+: all HIP-3 symbols. Pro+: orderbook history. |
| Lighter.xyz | August 2025+ for fills; January 2026+ for orderbooks, open interest, funding rates | Perpetuals |

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

    # Async get (Lighter.xyz)
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
    api_key="0xa_your_api_key",           # Required
    base_url="https://api.0xarchive.io", # Optional
    timeout=30.0,                         # Optional, request timeout in seconds (default: 30.0)
)
```

## REST API Reference

All examples use `client.hyperliquid.*` but the same methods are available on `client.lighter.*` for Lighter.xyz data.

### Order Book

```python
# Get current order book (Hyperliquid)
orderbook = client.hyperliquid.orderbook.get("BTC")

# Get current order book (Lighter.xyz)
orderbook = client.lighter.orderbook.get("BTC")

# Get order book at specific timestamp
historical = client.hyperliquid.orderbook.get("BTC", timestamp=1704067200000)

# Get with limited depth
shallow = client.hyperliquid.orderbook.get("BTC", depth=10)

# Get historical snapshots (start and end are required)
history = client.hyperliquid.orderbook.history(
    "BTC",
    start="2024-01-01",
    end="2024-01-02",
    limit=1000,
    depth=20  # Price levels per side
)

# HIP-3 order book (case-sensitive coins)
hip3_ob = client.hyperliquid.hip3.orderbook.get("km:US500")
hip3_history = client.hyperliquid.hip3.orderbook.history("km:US500", start="2026-02-01", end="2026-02-02")

# Async versions
orderbook = await client.hyperliquid.orderbook.aget("BTC")
history = await client.hyperliquid.orderbook.ahistory("BTC", start=..., end=...)
hip3_ob = await client.hyperliquid.hip3.orderbook.aget("km:US500")
```

#### Orderbook Depth Limits

The `depth` parameter controls how many price levels are returned per side. Tier-based limits apply:

| Tier | Max Depth |
|------|-----------|
| Free | 20 |
| Build | 200 |
| Pro | Full Depth |
| Enterprise | Full Depth |

**Note:** Hyperliquid L2 source data contains 20 levels. Full-depth L2 (derived from L4) and Lighter.xyz provide full depth on Pro+. Depth limits apply to L2 snapshot endpoints only — L4 and L2 diff endpoints return full data.

#### Lighter Orderbook Granularity

Lighter.xyz orderbook history supports a `granularity` parameter for different data resolutions. Tier restrictions apply.

| Granularity | Interval | Tier Required | Credit Multiplier |
|-------------|----------|---------------|-------------------|
| `checkpoint` | ~60s | Free+ | 1x |
| `30s` | 30s | Build+ | 2x |
| `10s` | 10s | Build+ | 3x |
| `1s` | 1s | Pro+ | 10x |
| `tick` | tick-level | Enterprise | 20x |

```python
# Get Lighter orderbook history with 10s resolution (Build+ tier)
history = client.lighter.orderbook.history(
    "BTC",
    start="2024-01-01",
    end="2024-01-02",
    granularity="10s"
)

# Get 1-second resolution (Pro+ tier)
history = client.lighter.orderbook.history(
    "BTC",
    start="2024-01-01",
    end="2024-01-02",
    granularity="1s"
)

# Tick-level data (Enterprise tier) - returns checkpoint + raw deltas
history = client.lighter.orderbook.history(
    "BTC",
    start="2024-01-01",
    end="2024-01-02",
    granularity="tick"
)
```

**Note:** The `granularity` parameter is ignored for Hyperliquid orderbook history.

#### Orderbook Reconstruction (Enterprise Tier)

For tick-level data, the SDK provides client-side orderbook reconstruction. This efficiently reconstructs full orderbook state from a checkpoint and incremental deltas.

```python
from datetime import datetime, timedelta
from oxarchive import OrderBookReconstructor

# Option 1: Get fully reconstructed snapshots (simplest)
snapshots = client.lighter.orderbook.history_reconstructed(
    "BTC",
    start=datetime.now() - timedelta(hours=1),
    end=datetime.now()
)

for ob in snapshots:
    print(f"{ob.timestamp}: bid={ob.bids[0].px} ask={ob.asks[0].px}")

# Option 2: Get raw tick data for custom reconstruction
tick_data = client.lighter.orderbook.history_tick(
    "BTC",
    start=datetime.now() - timedelta(hours=1),
    end=datetime.now()
)

print(f"Checkpoint: {len(tick_data.checkpoint.bids)} bids")
print(f"Deltas: {len(tick_data.deltas)} updates")

# Option 3: Auto-paginating iterator (recommended for large time ranges)
# Automatically handles pagination, fetching up to 1,000 deltas per request
for snapshot in client.lighter.orderbook.iterate_tick_history(
    "BTC",
    start=datetime.now() - timedelta(days=1),  # 24 hours of data
    end=datetime.now()
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

The trades API uses cursor-based pagination for efficient retrieval of large datasets.

```python
# Get trade history with cursor-based pagination
result = client.hyperliquid.trades.list("ETH", start="2024-01-01", end="2024-01-02", limit=1000)
trades = result.data

# Paginate through all results
while result.next_cursor:
    result = client.hyperliquid.trades.list(
        "ETH",
        start="2024-01-01",
        end="2024-01-02",
        cursor=result.next_cursor,
        limit=1000
    )
    trades.extend(result.data)

# Filter by side
buys = client.hyperliquid.trades.list("BTC", start=..., end=..., side="buy")

# Get recent trades (Lighter and HIP-3 - have real-time data)
recent = client.lighter.trades.recent("BTC", limit=100)

# HIP-3 recent trades (case-sensitive coins)
hip3_recent = client.hyperliquid.hip3.trades.recent("km:US500", limit=100)

# HIP-3 trade history
hip3_trades = client.hyperliquid.hip3.trades.list("km:US500", start="2026-02-01", end="2026-02-02")

# Async versions
result = await client.hyperliquid.trades.alist("ETH", start=..., end=...)
recent = await client.lighter.trades.arecent("BTC", limit=100)
hip3_recent = await client.hyperliquid.hip3.trades.arecent("km:US500", limit=100)
```

**Note:** The `recent()` method is available for Lighter.xyz and HIP-3 (both have real-time data ingestion). Hyperliquid does not have a recent trades endpoint - use `list()` with a time range instead.

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

#### Lighter.xyz Instruments

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
# List all HIP-3 instruments (no tier restriction)
hip3_instruments = client.hyperliquid.hip3.instruments.list()
for inst in hip3_instruments:
    print(f"{inst.coin} ({inst.namespace}:{inst.ticker}): mark={inst.mark_price}, OI={inst.open_interest}")

# Get specific HIP-3 instrument (case-sensitive)
us500 = client.hyperliquid.hip3.instruments.get("km:US500")
print(f"Mark price: {us500.mark_price}")

# Async versions
hip3_instruments = await client.hyperliquid.hip3.instruments.alist()
us500 = await client.hyperliquid.hip3.instruments.aget("km:US500")
```

**Available HIP-3 Coins:**
| Builder | Coins |
|---------|-------|
| xyz (Hyperliquid) | `xyz:XYZ100` |
| km (Kinetiq Markets) | `km:US500`, `km:SMALL2000`, `km:GOOGL`, `km:USBOND`, `km:GOLD`, `km:USTECH`, `km:NVDA`, `km:SILVER`, `km:BABA` |

### Funding Rates

```python
# Get current funding rate
current = client.hyperliquid.funding.current("BTC")

# Get funding rate history (start is required)
history = client.hyperliquid.funding.history(
    "ETH",
    start="2024-01-01",
    end="2024-01-07"
)

# Get funding rate history with aggregation interval
history = client.hyperliquid.funding.history(
    "BTC",
    start="2024-01-01",
    end="2024-01-07",
    interval="1h"
)

# HIP-3 funding (case-sensitive coins)
hip3_current = client.hyperliquid.hip3.funding.current("km:US500")
hip3_history = client.hyperliquid.hip3.funding.history("km:US500", start="2026-02-01", end="2026-02-07")

# Async versions
current = await client.hyperliquid.funding.acurrent("BTC")
history = await client.hyperliquid.funding.ahistory("ETH", start=..., end=...)
hip3_current = await client.hyperliquid.hip3.funding.acurrent("km:US500")
```

#### Funding History Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `coin` | `str` | Yes | Coin symbol (e.g., `'BTC'`, `'ETH'`) |
| `start` | `Timestamp` | Yes | Start timestamp |
| `end` | `Timestamp` | Yes | End timestamp |
| `cursor` | `Timestamp` | No | Cursor from previous response for pagination |
| `limit` | `int` | No | Max results (default: 100, max: 1000) |
| `interval` | `str` | No | Aggregation interval: `'5m'`, `'15m'`, `'30m'`, `'1h'`, `'4h'`, `'1d'`. When omitted, raw ~1 min data is returned. |

### Open Interest

```python
# Get current open interest
current = client.hyperliquid.open_interest.current("BTC")

# Get open interest history (start is required)
history = client.hyperliquid.open_interest.history(
    "ETH",
    start="2024-01-01",
    end="2024-01-07"
)

# Get open interest history with aggregation interval
oi = client.hyperliquid.open_interest.history(
    "BTC",
    start="2024-01-01",
    end="2024-01-07",
    interval="1h"
)

# HIP-3 open interest (case-sensitive coins)
hip3_current = client.hyperliquid.hip3.open_interest.current("km:US500")
hip3_history = client.hyperliquid.hip3.open_interest.history("km:US500", start="2026-02-01", end="2026-02-07")

# Async versions
current = await client.hyperliquid.open_interest.acurrent("BTC")
history = await client.hyperliquid.open_interest.ahistory("ETH", start=..., end=...)
hip3_current = await client.hyperliquid.hip3.open_interest.acurrent("km:US500")
```

#### Open Interest History Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `coin` | `str` | Yes | Coin symbol (e.g., `'BTC'`, `'ETH'`) |
| `start` | `Timestamp` | Yes | Start timestamp |
| `end` | `Timestamp` | Yes | End timestamp |
| `cursor` | `Timestamp` | No | Cursor from previous response for pagination |
| `limit` | `int` | No | Max results (default: 100, max: 1000) |
| `interval` | `str` | No | Aggregation interval: `'5m'`, `'15m'`, `'30m'`, `'1h'`, `'4h'`, `'1d'`. When omitted, raw ~1 min data is returned. |

### Liquidations

Get historical liquidation events. Available for Hyperliquid (May 2025+) and HIP-3.

```python
# Get liquidation history for a coin (Hyperliquid)
liquidations = client.hyperliquid.liquidations.history(
    "BTC",
    start="2025-06-01",
    end="2025-06-02",
    limit=100
)

# Paginate through all results
all_liquidations = list(liquidations.data)
while liquidations.next_cursor:
    liquidations = client.hyperliquid.liquidations.history(
        "BTC",
        start="2025-06-01",
        end="2025-06-02",
        cursor=liquidations.next_cursor,
        limit=1000
    )
    all_liquidations.extend(liquidations.data)

# Get liquidations for a specific user
user_liquidations = client.hyperliquid.liquidations.by_user(
    "0x1234...",
    start="2025-06-01",
    end="2025-06-07",
    symbol="BTC"  # optional filter
)

# HIP-3 liquidations (case-sensitive coins)
hip3_liquidations = client.hyperliquid.hip3.liquidations.history(
    "km:US500",
    start="2026-02-01",
    end="2026-02-02",
    limit=100
)

# HIP-3 liquidation volume
hip3_volume = client.hyperliquid.hip3.liquidations.volume(
    "km:US500",
    start="2026-02-01",
    end="2026-02-08",
    interval="1h"
)

# Async versions
liquidations = await client.hyperliquid.liquidations.ahistory("BTC", start=..., end=...)
user_liquidations = await client.hyperliquid.liquidations.aby_user("0x...", start=..., end=...)
hip3_liquidations = await client.hyperliquid.hip3.liquidations.ahistory("km:US500", start=..., end=...)
hip3_volume = await client.hyperliquid.hip3.liquidations.avolume("km:US500", start=..., end=...)
```

### Liquidation Volume

Get pre-aggregated liquidation volume in time-bucketed intervals. Returns total, long, and short USD volumes per bucket -- 100-1000x less data than individual liquidation records. Available for Hyperliquid and HIP-3.

```python
# Get hourly liquidation volume for the last week (Hyperliquid)
volume = client.hyperliquid.liquidations.volume(
    "BTC",
    start="2026-01-01",
    end="2026-01-08",
    interval="1h"  # 5m, 15m, 30m, 1h, 4h, 1d
)

for bucket in volume.data:
    print(f"{bucket.timestamp}: total=${bucket.total_usd}, long=${bucket.long_usd}, short=${bucket.short_usd}")

# HIP-3 liquidation volume
hip3_volume = client.hyperliquid.hip3.liquidations.volume(
    "km:US500",
    start="2026-02-01",
    end="2026-02-08",
    interval="1d"
)

# Convenience method on HyperliquidClient (Hyperliquid only)
volume = client.hyperliquid.get_liquidation_volume("BTC", start=..., end=..., interval="1h")

# Async versions
volume = await client.hyperliquid.liquidations.avolume("BTC", start=..., end=..., interval="1h")
hip3_volume = await client.hyperliquid.hip3.liquidations.avolume("km:US500", start=..., end=..., interval="1d")
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

# Lighter.xyz
lighter_freshness = client.lighter.get_freshness("BTC")

# HIP-3 (case-sensitive coins)
hip3_freshness = client.hyperliquid.hip3.get_freshness("km:US500")

# Async versions
freshness = await client.hyperliquid.aget_freshness("BTC")
lighter_freshness = await client.lighter.aget_freshness("BTC")
hip3_freshness = await client.hyperliquid.hip3.aget_freshness("km:US500")
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

# Lighter.xyz (price, funding, OI — no volume/liquidation data)
lighter_summary = client.lighter.get_summary("BTC")

# HIP-3 (includes mid_price — case-sensitive coins)
hip3_summary = client.hyperliquid.hip3.get_summary("km:US500")
print(f"Mid price: {hip3_summary.mid_price}")

# Async versions
summary = await client.hyperliquid.aget_summary("BTC")
lighter_summary = await client.lighter.aget_summary("BTC")
hip3_summary = await client.hyperliquid.hip3.aget_summary("km:US500")
```

### Price History

Get mark, oracle, and mid price history over time. Supports aggregation intervals. Data projected from open interest records.

```python
# Hyperliquid — available from May 2023
prices = client.hyperliquid.get_price_history(
    "BTC",
    start="2026-01-01",
    end="2026-01-02",
    interval="1h"  # 5m, 15m, 30m, 1h, 4h, 1d
)

for snapshot in prices.data:
    print(f"{snapshot.timestamp}: mark={snapshot.mark_price}, oracle={snapshot.oracle_price}, mid={snapshot.mid_price}")

# Lighter.xyz
lighter_prices = client.lighter.get_price_history("BTC", start="2026-01-01", end="2026-01-02", interval="1h")

# HIP-3 (case-sensitive coins)
hip3_prices = client.hyperliquid.hip3.get_price_history("km:US500", start="2026-02-01", end="2026-02-02", interval="1d")

# Paginate for larger ranges
result = client.hyperliquid.get_price_history("BTC", start=..., end=..., interval="4h", limit=1000)
while result.next_cursor:
    result = client.hyperliquid.get_price_history(
        "BTC", start=..., end=..., interval="4h",
        cursor=result.next_cursor, limit=1000
    )

# Async versions
prices = await client.hyperliquid.aget_price_history("BTC", start=..., end=..., interval="1h")
lighter_prices = await client.lighter.aget_price_history("BTC", start=..., end=..., interval="1h")
hip3_prices = await client.hyperliquid.hip3.aget_price_history("km:US500", start=..., end=..., interval="1d")
```

### Candles (OHLCV)

Get historical OHLCV candle data aggregated from trades.

```python
# Get candle history (start is required)
candles = client.hyperliquid.candles.history(
    "BTC",
    start="2024-01-01",
    end="2024-01-02",
    interval="1h",  # 1m, 5m, 15m, 30m, 1h, 4h, 1d, 1w
    limit=100
)

# Iterate through candles
for candle in candles.data:
    print(f"{candle.timestamp}: O={candle.open} H={candle.high} L={candle.low} C={candle.close} V={candle.volume}")

# Cursor-based pagination for large datasets
result = client.hyperliquid.candles.history("BTC", start=..., end=..., interval="1m", limit=1000)
while result.next_cursor:
    result = client.hyperliquid.candles.history(
        "BTC", start=..., end=..., interval="1m",
        cursor=result.next_cursor, limit=1000
    )

# Lighter.xyz candles
lighter_candles = client.lighter.candles.history(
    "BTC",
    start="2024-01-01",
    end="2024-01-02",
    interval="15m"
)

# HIP-3 candles (case-sensitive coins)
hip3_candles = client.hyperliquid.hip3.candles.history(
    "km:US500",
    start="2026-02-01",
    end="2026-02-02",
    interval="1h"
)

# Async versions
candles = await client.hyperliquid.candles.ahistory("BTC", start=..., end=..., interval="1h")
hip3_candles = await client.hyperliquid.hip3.candles.ahistory("km:US500", start=..., end=..., interval="1h")
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

### L4 Orderbook (Order-Level)

Get L4 order-level orderbook data with user attribution. Available for Hyperliquid and HIP-3.

```python
# Get current L4 orderbook snapshot (Hyperliquid)
snapshot = client.hyperliquid.l4_orderbook.get("BTC")
snapshot = client.hyperliquid.l4_orderbook.get("BTC", depth=10)

# Get L4 orderbook at a specific timestamp
historical = client.hyperliquid.l4_orderbook.get("BTC", timestamp=1704067200000)

# Get L4 orderbook diffs (order-level changes)
diffs = client.hyperliquid.l4_orderbook.diffs(
    "BTC",
    start="2024-01-01",
    end="2024-01-02",
    limit=1000
)

# Get L4 orderbook history (full snapshots over time)
history = client.hyperliquid.l4_orderbook.history(
    "BTC",
    start="2024-01-01",
    end="2024-01-02",
    depth=20,
    limit=100
)

# HIP-3 L4 orderbook (case-sensitive coins)
hip3_snapshot = client.hyperliquid.hip3.l4_orderbook.get("km:US500")
hip3_diffs = client.hyperliquid.hip3.l4_orderbook.diffs("km:US500", start=..., end=...)
hip3_history = client.hyperliquid.hip3.l4_orderbook.history("km:US500", start=..., end=...)

# Async versions
snapshot = await client.hyperliquid.l4_orderbook.aget("BTC")
diffs = await client.hyperliquid.l4_orderbook.adiffs("BTC", start=..., end=...)
history = await client.hyperliquid.l4_orderbook.ahistory("BTC", start=..., end=...)
hip3_snapshot = await client.hyperliquid.hip3.l4_orderbook.aget("km:US500")
```

**Methods:**

| Method | Description |
|--------|-------------|
| `get(symbol, *, timestamp, depth)` | Get L4 orderbook snapshot |
| `diffs(symbol, *, start, end, cursor, limit)` | Get L4 orderbook diffs (order-level changes) |
| `history(symbol, *, start, end, cursor, limit, depth)` | Get L4 orderbook history (full snapshots) |

### L3 Orderbook (Lighter.xyz Only)

Get L3 individual order-level orderbook data. Available for Lighter.xyz only.

```python
# Get current L3 orderbook snapshot
snapshot = client.lighter.l3_orderbook.get("BTC")
snapshot = client.lighter.l3_orderbook.get("BTC", depth=20)

# Get L3 orderbook at a specific timestamp
historical = client.lighter.l3_orderbook.get("BTC", timestamp=1704067200000)

# Get L3 orderbook history
history = client.lighter.l3_orderbook.history(
    "BTC",
    start="2024-01-01",
    end="2024-01-02",
    depth=20,
    limit=100
)

# Paginate through results
while history.next_cursor:
    history = client.lighter.l3_orderbook.history(
        "BTC",
        start="2024-01-01",
        end="2024-01-02",
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
| `get(symbol, *, timestamp, depth)` | Get L3 orderbook snapshot |
| `history(symbol, *, start, end, cursor, limit, depth)` | Get L3 orderbook history |

### L2 Orderbook (Full-Depth)

Get L2 full-depth orderbook derived from L4 data. Available for Hyperliquid and HIP-3.

```python
# L2 full-depth orderbook (Build+ tier)
l2 = client.hyperliquid.l2_orderbook.get("BTC")
l2_historical = client.hyperliquid.l2_orderbook.get("BTC", timestamp=1711900800000)

# L2 orderbook history (Build+ tier)
l2_history = client.hyperliquid.l2_orderbook.history("BTC", start=start, end=end)

# L2 tick-level diffs (Pro+ tier)
l2_diffs = client.hyperliquid.l2_orderbook.diffs("BTC", start=start, end=end)

# HIP-3 L2 orderbook
hip3_l2 = client.hyperliquid.hip3.l2_orderbook.get("km:US500")

# Async versions
l2 = await client.hyperliquid.l2_orderbook.aget("BTC")
l2_history = await client.hyperliquid.l2_orderbook.ahistory("BTC", start=..., end=...)
l2_diffs = await client.hyperliquid.l2_orderbook.adiffs("BTC", start=..., end=...)
```

**Methods:**

| Method | Description |
|--------|-------------|
| `get(symbol, *, timestamp, depth)` | Get L2 full-depth orderbook snapshot |
| `history(symbol, *, start, end, cursor, limit, depth)` | Get L2 orderbook history |
| `diffs(symbol, *, start, end, cursor, limit)` | Get L2 tick-level diffs |

### Orders (L4 Order History)

Get L4 order history, order flow aggregation, and TP/SL data. Available for Hyperliquid and HIP-3.

```python
# Get order history (Build+ tier)
result = client.hyperliquid.orders.history(
    "BTC",
    start="2024-01-01",
    end="2024-01-02",
    limit=1000
)

# Filter by user, status, or order type
result = client.hyperliquid.orders.history(
    "BTC",
    start="2024-01-01",
    end="2024-01-02",
    user="0x1234...",
    status="filled",
    order_type="limit"
)

# Get order flow aggregation (Build+ tier)
flow = client.hyperliquid.orders.flow(
    "BTC",
    start="2024-01-01",
    end="2024-01-02",
    interval="1h"
)

# Get TP/SL history (Pro+ tier)
tpsl = client.hyperliquid.orders.tpsl(
    "BTC",
    start="2024-01-01",
    end="2024-01-02",
    user="0x1234...",       # optional
    triggered=True          # optional filter
)

# HIP-3 orders (case-sensitive coins)
hip3_orders = client.hyperliquid.hip3.orders.history("km:US500", start=..., end=...)
hip3_flow = client.hyperliquid.hip3.orders.flow("km:US500", start=..., end=..., interval="1h")
hip3_tpsl = client.hyperliquid.hip3.orders.tpsl("km:US500", start=..., end=...)

# Async versions
result = await client.hyperliquid.orders.ahistory("BTC", start=..., end=...)
flow = await client.hyperliquid.orders.aflow("BTC", start=..., end=...)
tpsl = await client.hyperliquid.orders.atpsl("BTC", start=..., end=...)
hip3_orders = await client.hyperliquid.hip3.orders.ahistory("km:US500", start=..., end=...)
```

**Methods:**

| Method | Description | Tier |
|--------|-------------|------|
| `history(symbol, *, start, end, user, status, order_type, cursor, limit)` | Get order history | Build+ |
| `flow(symbol, *, start, end, interval, limit)` | Get order flow aggregation | Build+ |
| `tpsl(symbol, *, start, end, user, triggered, cursor, limit)` | Get TP/SL history | Pro+ |

### Data Quality Monitoring

Monitor data coverage, incidents, latency, and SLA compliance across venue APIs.

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

# Get SLA compliance metrics for a specific month
sla = client.data_quality.sla(year=2026, month=1)
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
| `exchange_coverage(exchange)` | Coverage details for a specific exchange |
| `symbol_coverage(exchange, symbol, *, from_time, to_time)` | Coverage with gap detection, cadence, and historical coverage |
| `list_incidents(...)` | List incidents with filtering and pagination |
| `get_incident(incident_id)` | Get specific incident details |
| `latency()` | Current latency metrics (WebSocket, REST, data freshness) |
| `sla(year, month)` | SLA compliance metrics for a specific month |

**Note:** Data Quality endpoints (`coverage()`, `exchange_coverage()`, `symbol_coverage()`) perform complex aggregation queries and may take 30-60 seconds on first request (results are cached server-side for 5 minutes). If you encounter timeout errors, create a client with a longer timeout:

```python
client = Client(
    api_key="0xa_your_api_key",
    timeout=60.0  # 60 seconds for data quality endpoints
)
```

### Web3 Authentication

Get API keys programmatically using an Ethereum wallet — no browser or email required.

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

The WebSocket client supports two modes: real-time streaming and historical replay. For file-based historical exports, use the [Data Catalog](https://www.0xarchive.io/data).

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
        end=int(time.time() * 1000),                # Optional
        speed=10                                     # Optional, defaults to 1x
    )

    # Lighter.xyz replay with granularity (tier restrictions apply)
    await ws.replay(
        "orderbook", "BTC",
        start=int(time.time() * 1000) - 86400000,
        speed=10,
        granularity="10s"  # Options: 'checkpoint', '30s', '10s', '1s', 'tick'
    )

    # Handle tick-level data (granularity='tick', Enterprise tier)
    ws.on_historical_tick_data(lambda coin, checkpoint, deltas:
        print(f"Checkpoint: {len(checkpoint['bids'])} bids, Deltas: {len(deltas)}")
    )

    # Control playback
    await ws.replay_pause()
    await ws.replay_resume()
    await ws.replay_seek(1704067200000)  # Jump to timestamp
    await ws.replay_stop()

asyncio.run(main())
```

### Gap Detection

During historical replay, the server automatically detects gaps in the data and notifies the client. This helps identify periods where data may be missing.

```python
import asyncio
from oxarchive import OxArchiveWs, WsOptions

async def main():
    ws = OxArchiveWs(WsOptions(api_key="ox_..."))

    # Handle gap notifications during replay/stream
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
    ws_url="wss://api.0xarchive.io/ws",  # Optional
    auto_reconnect=True,                  # Auto-reconnect on disconnect (default: True)
    reconnect_delay=1.0,                  # Initial reconnect delay in seconds (default: 1.0)
    max_reconnect_attempts=10,            # Max reconnect attempts (default: 10)
    ping_interval=30.0,                   # Keep-alive ping interval in seconds (default: 30.0)
))
```

### Available Channels

#### Hyperliquid Channels

| Channel | Description | Requires Coin | Historical Support |
|---------|-------------|---------------|-------------------|
| `orderbook` | L2 order book updates | Yes | Yes |
| `trades` | Trade/fill updates | Yes | Yes |
| `candles` | OHLCV candle data | Yes | Yes (replay only) |
| `liquidations` | Liquidation events (May 2025+) | Yes | Yes (replay only) |
| `open_interest` | Open interest snapshots | Yes | Yes (replay only) |
| `funding` | Funding rate records | Yes | Yes (replay only) |
| `ticker` | Price and 24h volume | Yes | Real-time only |
| `all_tickers` | All market tickers | No | Real-time only |
| `l4_diffs` | L4 orderbook diffs with user attribution (Pro+) | Yes | Real-time only |
| `l4_orders` | Order lifecycle events with user attribution (Pro+) | Yes | Real-time only |

#### HIP-3 Builder Perps Channels

| Channel | Description | Requires Coin | Historical Support |
|---------|-------------|---------------|-------------------|
| `hip3_orderbook` | HIP-3 L2 order book snapshots | Yes | Yes |
| `hip3_trades` | HIP-3 trade/fill updates | Yes | Yes |
| `hip3_candles` | HIP-3 OHLCV candle data | Yes | Yes |
| `hip3_open_interest` | HIP-3 open interest snapshots | Yes | Yes (replay only) |
| `hip3_funding` | HIP-3 funding rate records | Yes | Yes (replay only) |
| `hip3_liquidations` | HIP-3 liquidation events (Feb 2026+) | Yes | Yes (replay only) |
| `hip3_l4_diffs` | HIP-3 L4 orderbook diffs (Pro+) | Yes | Real-time only |
| `hip3_l4_orders` | HIP-3 order lifecycle events (Pro+) | Yes | Real-time only |

> **Note:** HIP-3 coins are case-sensitive (e.g., `km:US500`, `xyz:XYZ100`). Do not uppercase them.

#### Lighter.xyz Channels

| Channel | Description | Requires Coin | Historical Support |
|---------|-------------|---------------|-------------------|
| `lighter_orderbook` | Lighter L2 order book (reconstructed) | Yes | Yes |
| `lighter_trades` | Lighter trade/fill updates | Yes | Yes |
| `lighter_candles` | Lighter OHLCV candle data | Yes | Yes |
| `lighter_open_interest` | Lighter open interest snapshots | Yes | Yes (replay only) |
| `lighter_funding` | Lighter funding rate records | Yes | Yes (replay only) |
| `lighter_l3_orderbook` | Lighter L3 order-level orderbook (Pro+) | Yes | Yes |

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

# Lighter.xyz candles
await ws.replay(
    "lighter_candles", "BTC",
    start=...,
    speed=10,
    interval="5m"
)
```

#### HIP-3 Replay

```python
# Replay HIP-3 orderbook at 50x speed
await ws.replay(
    "hip3_orderbook", "km:US500",
    start=int(time.time() * 1000) - 3600000,
    end=int(time.time() * 1000),
    speed=50,
)

# HIP-3 candles
await ws.replay(
    "hip3_candles", "km:US500",
    start=int(time.time() * 1000) - 86400000,
    end=int(time.time() * 1000),
    speed=100,
    interval="1h"
)
```

#### Open Interest / Funding Replay

The `open_interest`, `funding`, `lighter_open_interest`, `lighter_funding`, `hip3_open_interest`, and `hip3_funding` channels are **historical only** (replay). They do not support real-time subscriptions.

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
    speed=50,
)

# HIP-3 funding replay
await ws.replay(
    "hip3_funding", "km:US500",
    start=int(time.time() * 1000) - 86400000,
    speed=100,
)
```

### Multi-Channel Replay

Replay multiple channels in a single synchronized timeline. All data is interleaved by timestamp, preserving the original timing relationships between orderbook updates, trades, funding rates, and open interest. Before the timeline begins, `replay_snapshot` messages provide the initial state for each channel.

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

    # Handle interleaved timeline data
    def on_data(coin, timestamp, data):
        # The 'channel' field on the raw message tells you which channel
        # this record belongs to. Use on_message() for full access.
        print(f"  {timestamp}: {data}")

    # Full message handler to see the channel field
    def on_message(msg):
        if hasattr(msg, 'type') and msg.type == "historical_data":
            channel = msg.channel
            print(f"[{channel}] {msg.coin} @ {msg.timestamp}")

    ws.on_replay_snapshot(on_snapshot)
    ws.on_historical_data(on_data)
    ws.on_message(on_message)

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
    start=start_ms, speed=10,
)

# Lighter.xyz: orderbook + trades + OI + funding
await ws.multi_replay(
    ["lighter_orderbook", "lighter_trades", "lighter_open_interest", "lighter_funding"],
    "BTC",
    start=start_ms, speed=10,
)

# HIP-3: orderbook + trades + OI + funding
await ws.multi_replay(
    ["hip3_orderbook", "hip3_trades", "hip3_open_interest", "hip3_funding"],
    "km:US500",
    start=start_ms, speed=10,
)
```

## Timestamp Formats

The SDK accepts timestamps in multiple formats:

```python
from datetime import datetime

# Unix milliseconds (int)
client.hyperliquid.orderbook.get("BTC", timestamp=1704067200000)

# ISO string
client.hyperliquid.orderbook.history("BTC", start="2024-01-01", end="2024-01-02")

# datetime object
client.hyperliquid.orderbook.history(
    "BTC",
    start=datetime(2024, 1, 1),
    end=datetime(2024, 1, 2)
)
```

## Error Handling

```python
from oxarchive import Client, OxArchiveError

client = Client(api_key="0xa_your_api_key")

try:
    orderbook = client.orderbook.get("INVALID")
except OxArchiveError as e:
    print(f"API Error: {e.message}")
    print(f"Status Code: {e.code}")
    print(f"Request ID: {e.request_id}")
```

## Type Hints

Full type hint support with Pydantic models:

```python
from oxarchive import Client, LighterGranularity
from oxarchive.types import (
    OrderBook, Trade, Instrument, LighterInstrument, FundingRate, OpenInterest, Candle, Liquidation,
    LiquidationVolume, CoinFreshness, CoinSummary, PriceSnapshot,
    WsReplaySnapshot,
)
from oxarchive.resources.trades import CursorResponse

# Orderbook reconstruction types (Enterprise)
from oxarchive import (
    OrderBookReconstructor,
    OrderbookDelta,
    TickData,
    ReconstructedOrderBook,
    ReconstructOptions,
)

client = Client(api_key="0xa_your_api_key")

orderbook: OrderBook = client.hyperliquid.orderbook.get("BTC")
result: CursorResponse = client.hyperliquid.trades.list("BTC", start=..., end=...)

# Lighter has real-time data, so recent() is available
recent: list[Trade] = client.lighter.trades.recent("BTC")

# Lighter granularity type hint
granularity: LighterGranularity = "10s"

# Orderbook reconstruction (Enterprise)
tick_data: TickData = client.lighter.orderbook.history_tick("BTC", start=..., end=...)
snapshots: list[ReconstructedOrderBook] = client.lighter.orderbook.history_reconstructed("BTC", start=..., end=...)
```

## Data Catalog

For large-scale data exports (full order books, complete trade history, etc.), use the [Data Catalog](https://www.0xarchive.io/data). It lets you choose markets, datasets, and date ranges, see a live quote, and export zstd-compressed Parquet.

## Requirements

- Python 3.9+
- httpx
- pydantic

## License

MIT
