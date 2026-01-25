# oxarchive

Official Python SDK for [0xarchive](https://0xarchive.io) - Hyperliquid Historical Data API.

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

# Get current order book
orderbook = client.orderbook.get("BTC")
print(f"BTC mid price: {orderbook.mid_price}")

# Get historical order book snapshots
history = client.orderbook.history(
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

    # Async get
    orderbook = await client.orderbook.aget("BTC")
    print(f"BTC mid price: {orderbook.mid_price}")

    # Don't forget to close the client
    await client.aclose()

asyncio.run(main())
```

Or use as async context manager:

```python
async with Client(api_key="ox_your_api_key") as client:
    orderbook = await client.orderbook.aget("BTC")
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

### Order Book

```python
# Get current order book
orderbook = client.orderbook.get("BTC")

# Get order book at specific timestamp
historical = client.orderbook.get("BTC", timestamp=1704067200000)

# Get with limited depth
shallow = client.orderbook.get("BTC", depth=10)

# Get historical snapshots (start and end are required)
history = client.orderbook.history(
    "BTC",
    start="2024-01-01",
    end="2024-01-02",
    limit=1000,
    depth=20  # Price levels per side
)

# Async versions
orderbook = await client.orderbook.aget("BTC")
history = await client.orderbook.ahistory("BTC", start=..., end=...)
```

### Trades

The trades API uses cursor-based pagination for efficient retrieval of large datasets.

```python
# Get recent trades
recent = client.trades.recent("BTC", limit=100)

# Get trade history with cursor-based pagination
result = client.trades.list("ETH", start="2024-01-01", end="2024-01-02", limit=1000)
trades = result.data

# Paginate through all results
while result.next_cursor:
    result = client.trades.list(
        "ETH",
        start="2024-01-01",
        end="2024-01-02",
        cursor=result.next_cursor,
        limit=1000
    )
    trades.extend(result.data)

# Filter by side
buys = client.trades.list("BTC", start=..., end=..., side="buy")

# Async versions
recent = await client.trades.arecent("BTC")
result = await client.trades.alist("ETH", start=..., end=...)
```

### Instruments

```python
# List all trading instruments
instruments = client.instruments.list()

# Get specific instrument details
btc = client.instruments.get("BTC")

# Async versions
instruments = await client.instruments.alist()
btc = await client.instruments.aget("BTC")
```

### Funding Rates

```python
# Get current funding rate
current = client.funding.current("BTC")

# Get funding rate history (start is required)
history = client.funding.history(
    "ETH",
    start="2024-01-01",
    end="2024-01-07"
)

# Async versions
current = await client.funding.acurrent("BTC")
history = await client.funding.ahistory("ETH", start=..., end=...)
```

### Open Interest

```python
# Get current open interest
current = client.open_interest.current("BTC")

# Get open interest history (start is required)
history = client.open_interest.history(
    "ETH",
    start="2024-01-01",
    end="2024-01-07"
)

# Async versions
current = await client.open_interest.acurrent("BTC")
history = await client.open_interest.ahistory("ETH", start=..., end=...)
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

| Channel | Description | Requires Coin |
|---------|-------------|---------------|
| `orderbook` | L2 order book updates | Yes |
| `trades` | Trade/fill updates | Yes |
| `ticker` | Price and 24h volume | Yes |
| `all_tickers` | All market tickers | No |

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
from oxarchive import Client
from oxarchive.types import OrderBook, Trade, Instrument, FundingRate, OpenInterest
from oxarchive.resources.trades import CursorResponse

client = Client(api_key="ox_your_api_key")

orderbook: OrderBook = client.orderbook.get("BTC")
trades: list[Trade] = client.trades.recent("BTC")
result: CursorResponse = client.trades.list("BTC", start=..., end=...)
```

## Requirements

- Python 3.9+
- httpx
- pydantic

## License

MIT
