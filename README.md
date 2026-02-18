# oxarchive

Official Python SDK for [0xarchive](https://0xarchive.io) - Historical Market Data API.

Supports multiple exchanges:
- **Hyperliquid** - Perpetuals data from April 2023
- **Hyperliquid HIP-3** - Builder-deployed perpetuals (Pro+ only, February 2026+)
- **Lighter.xyz** - Perpetuals data (August 2025+ for fills, Jan 2026+ for OB, OI, Funding Rate)

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

client = Client(api_key="ox_your_api_key")

# Hyperliquid data
hl_orderbook = client.hyperliquid.orderbook.get("BTC")
print(f"Hyperliquid BTC mid price: {hl_orderbook.mid_price}")

# Lighter.xyz data
lighter_orderbook = client.lighter.orderbook.get("BTC")
print(f"Lighter BTC mid price: {lighter_orderbook.mid_price}")

# HIP-3 builder perps (February 2026+)
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

## Async Support

All methods have async versions prefixed with `a`:

```python
import asyncio
from oxarchive import Client

async def main():
    client = Client(api_key="ox_your_api_key")

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
async with Client(api_key="ox_your_api_key") as client:
    orderbook = await client.hyperliquid.orderbook.aget("BTC")
```

## Configuration

```python
client = Client(
    api_key="ox_your_api_key",           # Required
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

# Async versions
orderbook = await client.hyperliquid.orderbook.aget("BTC")
history = await client.hyperliquid.orderbook.ahistory("BTC", start=..., end=...)
```

#### Orderbook Depth Limits

The `depth` parameter controls how many price levels are returned per side. Tier-based limits apply:

| Tier | Max Depth |
|------|-----------|
| Free | 20 |
| Build | 50 |
| Pro | 100 |
| Enterprise | Full Depth |

**Note:** Hyperliquid source data only contains 20 levels. Higher limits apply to Lighter.xyz data.

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

# Get recent trades (Lighter only - has real-time data)
recent = client.lighter.trades.recent("BTC", limit=100)

# Async versions
result = await client.hyperliquid.trades.alist("ETH", start=..., end=...)
recent = await client.lighter.trades.arecent("BTC", limit=100)
```

**Note:** The `recent()` method is only available for Lighter.xyz (`client.lighter.trades.recent()`). Hyperliquid does not have a recent trades endpoint - use `list()` with a time range instead.

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

# Async versions
current = await client.hyperliquid.funding.acurrent("BTC")
history = await client.hyperliquid.funding.ahistory("ETH", start=..., end=...)
```

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

# Async versions
current = await client.hyperliquid.open_interest.acurrent("BTC")
history = await client.hyperliquid.open_interest.ahistory("ETH", start=..., end=...)
```

### Liquidations (Hyperliquid only)

Get historical liquidation events. Data available from May 2025 onwards.

```python
# Get liquidation history for a coin
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
    coin="BTC"  # optional filter
)

# Async versions
liquidations = await client.hyperliquid.liquidations.ahistory("BTC", start=..., end=...)
user_liquidations = await client.hyperliquid.liquidations.aby_user("0x...", start=..., end=...)
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

# Async versions
candles = await client.hyperliquid.candles.ahistory("BTC", start=..., end=..., interval="1h")
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

### Data Quality Monitoring

Monitor data coverage, incidents, latency, and SLA compliance across all exchanges.

```python
# Get overall system health status
status = client.data_quality.status()
print(f"System status: {status.status}")
for exchange, info in status.exchanges.items():
    print(f"  {exchange}: {info.status}")

# Get data coverage summary for all exchanges
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
| `coverage()` | Data coverage summary for all exchanges |
| `exchange_coverage(exchange)` | Coverage details for a specific exchange |
| `symbol_coverage(exchange, symbol, *, from_time, to_time)` | Coverage with gap detection, cadence, and historical coverage |
| `list_incidents(...)` | List incidents with filtering and pagination |
| `get_incident(incident_id)` | Get specific incident details |
| `latency()` | Current latency metrics (WebSocket, REST, data freshness) |
| `sla(year, month)` | SLA compliance metrics for a specific month |

**Note:** Data Quality endpoints (`coverage()`, `exchange_coverage()`, `symbol_coverage()`) perform complex aggregation queries and may take 30-60 seconds on first request (results are cached server-side for 5 minutes). If you encounter timeout errors, create a client with a longer timeout:

```python
client = Client(
    api_key="ox_your_api_key",
    timeout=60.0  # 60 seconds for data quality endpoints
)
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

The WebSocket client supports three modes: real-time streaming, historical replay, and bulk streaming.

```python
import asyncio
from oxarchive import OxArchiveWs, WsOptions

ws = OxArchiveWs(WsOptions(api_key="ox_your_api_key"))
```

### Real-time Streaming

Subscribe to live market data from Hyperliquid.

```python
import asyncio
from oxarchive import OxArchiveWs, WsOptions

async def main():
    ws = OxArchiveWs(WsOptions(api_key="ox_your_api_key"))

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

### Bulk Streaming

Fast bulk download for data pipelines. Data arrives in batches without timing delays.

```python
import asyncio
import time
from oxarchive import OxArchiveWs, WsOptions

async def main():
    ws = OxArchiveWs(WsOptions(api_key="ox_..."))
    all_data = []

    # Handle batched data
    ws.on_batch(lambda coin, records:
        all_data.extend([r.data for r in records])
    )

    ws.on_stream_progress(lambda snapshots_sent:
        print(f"Progress: {snapshots_sent} snapshots")
    )

    ws.on_stream_complete(lambda ch, coin, sent:
        print(f"Downloaded {sent} records")
    )

    await ws.connect()

    # Start bulk stream
    await ws.stream(
        "orderbook", "ETH",
        start=int(time.time() * 1000) - 3600000,  # 1 hour ago
        end=int(time.time() * 1000),
        batch_size=1000                            # Optional, defaults to 1000
    )

    # Lighter.xyz stream with granularity (tier restrictions apply)
    await ws.stream(
        "orderbook", "BTC",
        start=int(time.time() * 1000) - 3600000,
        end=int(time.time() * 1000),
        granularity="10s"  # Options: 'checkpoint', '30s', '10s', '1s', 'tick'
    )

    # Stop if needed
    await ws.stream_stop()

asyncio.run(main())
```

### Gap Detection

During historical replay and bulk streaming, the server automatically detects gaps in the data and notifies the client. This helps identify periods where data may be missing.

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
    api_key="ox_your_api_key",
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
| `candles` | OHLCV candle data | Yes | Yes (replay/stream only) |
| `liquidations` | Liquidation events (May 2025+) | Yes | Yes (replay/stream only) |
| `ticker` | Price and 24h volume | Yes | Real-time only |
| `all_tickers` | All market tickers | No | Real-time only |

#### HIP-3 Builder Perps Channels

| Channel | Description | Requires Coin | Historical Support |
|---------|-------------|---------------|-------------------|
| `hip3_orderbook` | HIP-3 L2 order book snapshots | Yes | Yes |
| `hip3_trades` | HIP-3 trade/fill updates | Yes | Yes |

> **Note:** HIP-3 coins are case-sensitive (e.g., `km:US500`, `xyz:XYZ100`). Do not uppercase them.

#### Lighter.xyz Channels

| Channel | Description | Requires Coin | Historical Support |
|---------|-------------|---------------|-------------------|
| `lighter_orderbook` | Lighter L2 order book (reconstructed) | Yes | Yes |
| `lighter_trades` | Lighter trade/fill updates | Yes | Yes |
| `lighter_candles` | Lighter OHLCV candle data | Yes | Yes |

#### Candle Replay/Stream

```python
# Replay candles at 10x speed
await ws.replay(
    "candles", "BTC",
    start=int(time.time() * 1000) - 86400000,
    end=int(time.time() * 1000),
    speed=10,
    interval="15m"  # 1m, 5m, 15m, 30m, 1h, 4h, 1d, 1w
)

# Bulk stream candles
await ws.stream(
    "candles", "ETH",
    start=int(time.time() * 1000) - 3600000,
    end=int(time.time() * 1000),
    batch_size=1000,
    interval="1h"
)

# Lighter.xyz candles
await ws.replay(
    "lighter_candles", "BTC",
    start=...,
    speed=10,
    interval="5m"
)
```

#### HIP-3 Replay/Stream

```python
# Replay HIP-3 orderbook at 50x speed
await ws.replay(
    "hip3_orderbook", "km:US500",
    start=int(time.time() * 1000) - 3600000,
    end=int(time.time() * 1000),
    speed=50,
)

# Bulk stream HIP-3 trades
await ws.stream(
    "hip3_trades", "xyz:XYZ100",
    start=int(time.time() * 1000) - 86400000,
    end=int(time.time() * 1000),
    batch_size=1000,
)
```

## Timestamp Formats

The SDK accepts timestamps in multiple formats:

```python
from datetime import datetime

# Unix milliseconds (int)
client.orderbook.get("BTC", timestamp=1704067200000)

# ISO string
client.orderbook.history("BTC", start="2024-01-01", end="2024-01-02")

# datetime object
client.orderbook.history(
    "BTC",
    start=datetime(2024, 1, 1),
    end=datetime(2024, 1, 2)
)
```

## Error Handling

```python
from oxarchive import Client, OxArchiveError

client = Client(api_key="ox_your_api_key")

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
from oxarchive.types import OrderBook, Trade, Instrument, LighterInstrument, FundingRate, OpenInterest, Candle, Liquidation
from oxarchive.resources.trades import CursorResponse

# Orderbook reconstruction types (Enterprise)
from oxarchive import (
    OrderBookReconstructor,
    OrderbookDelta,
    TickData,
    ReconstructedOrderBook,
    ReconstructOptions,
)

client = Client(api_key="ox_your_api_key")

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

## Requirements

- Python 3.9+
- httpx
- pydantic

## License

MIT
