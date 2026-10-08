"""Read-only checks of the 2026-10-01 contract against the live API.

Skipped unless ``OXARCHIVE_LIVE_TESTS=1`` and ``OXARCHIVE_API_KEY`` are set.
Every call is a GET or a WebSocket subscribe/replay over a short window; they
use a few credits and change nothing. ``OXARCHIVE_BASE_URL`` and
``OXARCHIVE_WS_URL`` point them at another deployment.
"""

from __future__ import annotations

import asyncio
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Iterator, cast

import pytest

from oxarchive import API_VERSION, API_VERSION_HEADER, Client, OxArchiveError
from oxarchive.types import OrderBook, Trade, WsChannel, WsError, WsL4Batch, WsL4Snapshot, WsSubscribed

pytestmark = pytest.mark.skipif(
    os.getenv("OXARCHIVE_LIVE_TESTS") != "1" or not os.getenv("OXARCHIVE_API_KEY"),
    reason="set OXARCHIVE_LIVE_TESTS=1 and OXARCHIVE_API_KEY to run live checks",
)

BASE_URL = os.getenv("OXARCHIVE_BASE_URL", "https://api.0xarchive.io")
WS_URL = os.getenv("OXARCHIVE_WS_URL", "wss://api.0xarchive.io/ws")

# Recent, settled windows: an hour ending two hours ago for Hyperliquid, and a
# day ending two days ago for Lighter, whose canonical trades trail by a day.
_NOW = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
HL_END = _NOW - timedelta(hours=2)
HL_START = HL_END - timedelta(hours=1)
LIGHTER_END = _NOW - timedelta(days=2)
LIGHTER_START = LIGHTER_END - timedelta(hours=1)


@pytest.fixture(scope="module")
def client() -> Iterator[Client]:
    with Client(base_url=BASE_URL) as c:
        yield c


def test_requests_select_the_contract_version(client: Client) -> None:
    response = client._http.client.get("/v1/hyperliquid/orderbook/BTC", params={"depth": 1})
    assert response.request.headers[API_VERSION_HEADER] == API_VERSION
    assert response.headers[API_VERSION_HEADER] == API_VERSION


def test_records_and_pages_carry_symbol_and_venue(client: Client) -> None:
    book = client.hyperliquid.hip3.orderbook.get("xyz:TSLA", depth=2)
    assert (book.response_meta.symbol, book.response_meta.venue) == ("xyz:TSLA", "hip3")

    page = client.spot.trades.history("HYPE-USDC", start=HL_START, end=HL_END, limit=5)
    assert (page.meta.symbol, page.meta.venue) == ("HYPE-USDC", "spot")
    assert page.has_more is (page.next_cursor is not None)


def test_has_more_pages_to_the_end(client: Client) -> None:
    page = client.hyperliquid.funding.history("BTC", start=HL_START, end=HL_END, limit=20)
    pages = 1
    while page.has_more:
        assert page.next_cursor
        page = client.hyperliquid.funding.history(
            "BTC", start=HL_START, end=HL_END, limit=20, cursor=page.next_cursor
        )
        pages += 1
        assert pages < 20
    assert page.has_more is False and page.next_cursor is None and pages > 1


def test_capabilities_match_the_websocket_channel_table(client: Client) -> None:
    from oxarchive.websocket import WS_CHANNELS

    rows = client.capabilities()
    assert rows and all(row.venue and row.datatype for row in rows)
    served = {}
    by_datatype = {(row.venue, row.datatype): row for row in rows}
    for row in rows:
        for channel in row.ws_channels:
            plans = tuple(row.plans) if row.plans is not None else None
            served[channel] = (row.venue, row.live, row.replay, row.ws_endpoint, plans)
    assert served, "no row names a WebSocket channel"
    for channel, (venue, live, replay, ws_endpoint, plans) in served.items():
        spec = WS_CHANNELS[channel]
        assert (spec.venue, spec.live, spec.replay) == (venue, live, replay), channel
        assert (spec.ws_endpoint, spec.plans) == (ws_endpoint, plans), channel
    # A channel no row names must be one its datatype's row says neither
    # streams nor replays (spot TWAP is served over REST only).
    for channel, spec in WS_CHANNELS.items():
        if channel not in served:
            row = by_datatype[(spec.venue, spec.datatype)]
            assert not (spec.live or spec.replay or row.live or row.replay), channel


@pytest.mark.parametrize(
    "venue, symbol, recent",
    [("hyperliquid", "BTC", False), ("hip3", "xyz:TSLA", True), ("spot", "HYPE-USDC", True)],
)
def test_trades_side_filters_on_hyperliquid_venues(
    client: Client, venue: str, symbol: str, recent: bool
) -> None:
    trades = {"hyperliquid": client.hyperliquid.trades, "hip3": client.hyperliquid.hip3.trades, "spot": client.spot.trades}[venue]
    buys = trades.history(symbol, start=HL_START, end=HL_END, limit=50, side="buy")
    sells = trades.history(symbol, start=HL_START, end=HL_END, limit=50, side="sell")
    assert buys.data and {t.side for t in buys.data} == {"B"}
    assert sells.data and {t.side for t in sells.data} == {"A"}
    if recent:
        assert {t.side for t in trades.recent(symbol, limit=20, side="sell")} <= {"A"}


@pytest.mark.parametrize("deployment", ["lighter", "rh_lighter"])
def test_trades_side_filters_on_lighter(client: Client, deployment: str) -> None:
    trades = getattr(client, deployment).trades
    buys = trades.history("BTC", start=LIGHTER_START, end=LIGHTER_END, limit=20, side="buy")
    assert buys.data and {t.side for t in buys.data} == {"B"}


def test_order_history_triggered_filter(client: Client) -> None:
    fired = client.hyperliquid.orders.history("BTC", start=HL_START, end=HL_END, limit=50, triggered=True)
    others = client.hyperliquid.orders.history("BTC", start=HL_START, end=HL_END, limit=50, triggered=False)
    assert {row["status"] for row in fired.data} <= {"triggered"}
    assert others.data and "triggered" not in {row["status"] for row in others.data}


def test_depth_on_full_depth_and_order_book_history(client: Client) -> None:
    full = client.hyperliquid.l2_orderbook.history("BTC", start=HL_START, end=HL_END, limit=1, depth=3)
    assert len(full.data[0]["bids"]) == 3 and len(full.data[0]["asks"]) == 3
    spot = client.spot.orderbook.history("HYPE-USDC", start=HL_START, end=HL_END, limit=1, depth=2)
    assert len(spot.data[0].bids) == 2


def test_time_fields_are_datetimes_with_ms(client: Client) -> None:
    bucket = client.hyperliquid.cvd.history("BTC", interval="1h", limit=1).data[0]
    assert bucket.timestamp.tzinfo is not None
    assert bucket.timestamp_ms == int(bucket.timestamp.timestamp() * 1000)
    price = client.hyperliquid.hip3.oracle.external_price("xyz:TSLA")
    assert price.timestamp_ms == int(price.timestamp.timestamp() * 1000)
    levels = client.hyperliquid.liquidations.levels("BTC", buckets=10)
    assert levels.snapshot_ts_ms and levels.snapshot_ts.endswith("Z")


def test_data_quality_and_symbols_parse(client: Client) -> None:
    status = client.data_quality.status()
    assert status.status and status.exchanges
    assert client.data_quality.status_coverage().exchanges
    symbols = client.symbols.list()
    assert any(s.exchange == "hip3" for s in symbols)


def test_errors_carry_the_contract_fields(client: Client) -> None:
    with pytest.raises(OxArchiveError) as caught:
        client.hyperliquid.trades.history("BTC", start=HL_START, end=HL_END, side=cast(Any, "both"))
    error = caught.value
    assert (error.status, error.error_code, error.param) == (400, "invalid_parameter", "side")
    assert error.valid_values == ["buy", "sell"] and error.request_id

    with pytest.raises(OxArchiveError) as caught:
        client._http.get("/v1/hyperliquid/spot/orders/HYPE-USDC/flow")
    assert caught.value.error_code == "unsupported_for_venue"
    assert caught.value.details["available_on"]

    with pytest.raises(OxArchiveError) as caught:
        client._http.get("/v1/hyperliquid/no-such-route/BTC")
    assert caught.value.error_code == "route_not_found"


# ---------------------------------------------------------------------------
# WebSocket
# ---------------------------------------------------------------------------


async def _session(run: Any, until: Any, timeout: float = 45.0) -> list[Any]:
    from oxarchive.websocket import OxArchiveWs, WsOptions

    ws = OxArchiveWs(
        WsOptions(api_key=os.environ["OXARCHIVE_API_KEY"], ws_url=WS_URL, auto_reconnect=False)
    )
    seen: list[Any] = []
    done = asyncio.Event()

    def record(item: Any) -> None:
        seen.append(item)
        if until(seen):
            done.set()

    ws.on_message(record)
    ws.on_replay_data(lambda channel, coin, ts, rec: record(("replay", channel, rec)))
    ws.on_replay_complete(lambda channel, coin, sent: record(("complete", channel, sent)))
    await ws.connect()
    try:
        await run(ws)
        await asyncio.wait_for(done.wait(), timeout)
    finally:
        await ws.disconnect()
    return seen


def test_websocket_acks_carry_the_version_and_errors_carry_codes() -> None:
    async def run(ws: Any) -> None:
        await ws.subscribe_async("trades", "BTC")
        await ws._send({"op": "subscribe", "channel": "no_such_channel", "symbol": "BTC"})

    seen = asyncio.run(
        _session(run, lambda s: any(isinstance(m, WsError) for m in s) and any(isinstance(m, WsSubscribed) for m in s))
    )
    ack = next(m for m in seen if isinstance(m, WsSubscribed))
    assert ack.version == API_VERSION
    error = next(m for m in seen if isinstance(m, WsError))
    assert error.error_code == "invalid_parameter"


def test_spot_l4_replay_is_bulk_and_typed() -> None:
    start = int((HL_END - timedelta(minutes=30)).timestamp() * 1000)

    async def run(ws: Any) -> None:
        await ws.replay(cast(WsChannel, "spot_l4_diffs"), "PURR-USDC", start=start, end=start + 20_000)

    seen = asyncio.run(_session(run, lambda s: any(isinstance(m, tuple) and m[0] == "complete" for m in s)))
    assert any(isinstance(m, WsL4Snapshot) and m.channel == "spot_l4_diffs" for m in seen)
    assert all(m.channel == "spot_l4_diffs" for m in seen if isinstance(m, WsL4Batch))


def test_lighter_replay_uses_the_live_shapes() -> None:
    start = int(LIGHTER_START.timestamp() * 1000)

    async def run(ws: Any) -> None:
        await ws.replay(cast(WsChannel, "lighter_trades"), "BTC", start=start, end=start + 60_000, speed=1000)

    seen = asyncio.run(_session(run, lambda s: any(isinstance(m, tuple) and m[0] == "complete" for m in s)))
    records = [m[2] for m in seen if isinstance(m, tuple) and m[0] == "replay"]
    assert records, "no Lighter trades in the window"
    legs = records[0]
    assert isinstance(legs, list) and isinstance(legs[0], Trade) and legs[0].account_index

    async def run_book(ws: Any) -> None:
        await ws.replay(cast(WsChannel, "lighter_orderbook"), "BTC", start=start, end=start + 120_000, speed=1000)

    seen = asyncio.run(_session(run_book, lambda s: any(isinstance(m, tuple) and m[0] == "complete" for m in s)))
    books = [m[2] for m in seen if isinstance(m, tuple) and m[0] == "replay"]
    assert books and isinstance(books[0], OrderBook) and books[0].bids
