# oxarchive

Official Python SDK for [0xarchive](https://0xarchive.io) - Historical Market Data API.

Supports multiple exchanges:
- **Hyperliquid** - Perpetuals data from April 2023
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

# Async version
result = await client.hyperliquid.trades.alist("ETH", start=..., end=...)
```

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

| Channel | Description | Requires Coin | Historical Support |
|---------|-------------|---------------|-------------------|
| `orderbook` | L2 order book updates | Yes | Yes |
| `trades` | Trade/fill updates | Yes | Yes |
| `candles` | OHLCV candle data | Yes | Yes (replay/stream only) |
| `ticker` | Price and 24h volume | Yes | Real-time only |
| `all_tickers` | All market tickers | No | Real-time only |

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
from oxarchive.types import OrderBook, Trade, Instrument, LighterInstrument, FundingRate, OpenInterest
from oxarchive.resources.trades import CursorResponse

client = Client(api_key="ox_your_api_key")

orderbook: OrderBook = client.hyperliquid.orderbook.get("BTC")
result: CursorResponse = client.hyperliquid.trades.list("BTC", start=..., end=...)

# Lighter has real-time data, so recent() is available
recent: list[Trade] = client.lighter.trades.recent("BTC")

# Lighter granularity type hint
granularity: LighterGranularity = "10s"
```

## Requirements

- Python 3.9+
- httpx
- pydantic

## License

MIT
