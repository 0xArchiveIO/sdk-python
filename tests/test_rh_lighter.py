"""Lighter on Robinhood Chain (REST and WebSocket) and Lighter liquidations."""

from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path
from typing import Any, Callable, cast

import pytest
from _mock_api import envelope, mock_client
from test_websocket_capabilities import (
    LIGHTER_BOOK_FRAME,
    LIGHTER_CTX_FRAME,
    LIGHTER_TRADES_FRAME,
    FakeSocket,
)

from oxarchive import (
    LighterClient,
    LighterLiquidation,
    LighterLiquidationVolume,
    ResponseMeta,
    RhLighterClient,
)
from oxarchive.types import OrderBook, Trade, WsChannel, WsData, WsSubscribed
from oxarchive.websocket import (
    LIGHTER_LIVE_CHANNELS,
    RH_LIGHTER_LIVE_CHANNELS,
    RH_LIGHTER_REPLAY_CHANNELS,
    RH_LIGHTER_REPLAY_ONLY_CHANNELS,
    RH_LIGHTER_SUBSCRIPTION_ERROR,
    OxArchiveWs,
    WsOptions,
)

T_START = 1790251200000
T_END = 1790337600000

# A liquidation row shaped like the API's JSON: Robinhood Chain's first
# liquidation, from before live capture, so backfilled from the venue's
# finalized export (source "bucket", empty raw_json).
RH_LIQUIDATION: dict[str, Any] = {
    "symbol": "BTC",
    "timestamp": 1782602083534,
    "transaction_time_us": 1782602083534123,
    "trade_id": 5501,
    "liquidation_type": "partial",
    "price": 107250.5,
    "size": 0.0125,
    "usd_amount": 1340.63125,
    "ask_account": "281474976710654",
    "bid_account": "4521",
    "ask_order_id": 7001,
    "bid_order_id": 7002,
    "is_maker_ask": False,
    "taker_position_size_before": -0.0125,
    "maker_position_size_before": 3.5,
    "taker_entry_quote_before": 1331.25,
    "maker_entry_quote_before": 371000.0,
    "taker_initial_margin_fraction_before": 500,
    "maker_initial_margin_fraction_before": 200,
    "taker_allocated_margin_usdc_before": 0,
    "taker_allocated_margin_usdc_after": 0,
    "maker_allocated_margin_usdc_before": 0,
    "maker_allocated_margin_usdc_after": 0,
    "taker_fee": 0,
    "maker_fee": 0,
    "taker_position_sign_changed": True,
    "maker_position_sign_changed": False,
    "block_height": 912345,
    "tx_hash": "0x0f",
    "raw_json": "",
    "source": "bucket",
}

# The same shape captured live: source "ws" with the venue's raw JSON.
RH_LIQUIDATION_LIVE: dict[str, Any] = {
    **RH_LIQUIDATION,
    "timestamp": 1788240575923,
    "transaction_time_us": 1788240575923456,
    "trade_id": 324449287,
    "raw_json": '{"trade_id":324449287,"market_id":1,"price":"78963.9"}',
    "source": "ws",
}

LIQUIDATION_VOLUME: dict[str, Any] = {
    "symbol": "BTC",
    "timestamp": 1788220800000,
    "total_usd": 1340.63125,
    "count": 1,
}


def _public(obj: object) -> set[str]:
    return {name for name in vars(obj) if not name.startswith("_")}


# ---------------------------------------------------------------------------
# Client shape
# ---------------------------------------------------------------------------


def test_rh_lighter_has_the_lighter_resources_minus_l3_and_the_l1_resolver() -> None:
    client, _ = mock_client(lambda path, q: envelope([]))

    assert isinstance(client.rh_lighter, RhLighterClient)
    assert isinstance(client.lighter, LighterClient)
    assert not isinstance(client.rh_lighter, LighterClient)
    assert _public(client.lighter) - _public(client.rh_lighter) == {"l3_orderbook", "accounts"}
    assert _public(client.rh_lighter) <= _public(client.lighter)
    assert {"liquidations", "positions"} <= _public(client.lighter)
    for method in ("get_freshness", "get_summary", "get_price_history"):
        assert callable(getattr(client.rh_lighter, method))


# ---------------------------------------------------------------------------
# REST routes under /v1/rh-lighter
# ---------------------------------------------------------------------------

INSTRUMENT: dict[str, Any] = {
    "symbol": "AAPL-USDG",
    "market_id": 2049,
    "market_type": "spot",
    "status": "active",
    "taker_fee": 0.0,
    "maker_fee": 0.0,
    "liquidation_fee": 0.0,
    "min_base_amount": 0.01,
    "min_quote_amount": 1.0,
    "size_decimals": 2,
    "price_decimals": 2,
    "quote_decimals": 4,
    "is_active": True,
}
BOOK: dict[str, Any] = {
    "coin": "AAPL-USDG",
    "timestamp": "2026-09-25T12:00:00Z",
    "bids": [{"px": "254.1", "sz": "10", "n": 1}],
    "asks": [{"px": "254.2", "sz": "5", "n": 1}],
}
TRADE: dict[str, Any] = {
    "coin": "BTC",
    "side": "B",
    "price": "107250.5",
    "size": "0.01",
    "timestamp": "2026-09-25T11:59:59Z",
    "trade_id": 5502,
    "account_index": "4521",
}
FUNDING: dict[str, Any] = {
    "coin": "BTC",
    "timestamp": "2026-09-25T12:00:00Z",
    "funding_rate": "0.00001",
}
OI: dict[str, Any] = {"coin": "BTC", "timestamp": "2026-09-25T12:00:00Z", "open_interest": "12.5"}
CANDLE: dict[str, Any] = {
    "timestamp": "2026-09-25T12:00:00Z",
    "open": 1.0,
    "high": 2.0,
    "low": 0.5,
    "close": 1.5,
    "volume": 3.0,
}
FRESHNESS: dict[str, Any] = {
    "coin": "BTC",
    "exchange": "rh-lighter",
    "measured_at": "2026-09-25T12:00:00Z",
    "orderbook": {"last_updated": "2026-09-25T11:59:59Z", "lag_ms": 1000},
    "trades": {"last_updated": "2026-09-25T11:59:59Z", "lag_ms": 1000},
    "funding": {"last_updated": None, "lag_ms": None},
    "open_interest": {"last_updated": None, "lag_ms": None},
}
SUMMARY: dict[str, Any] = {
    "coin": "BTC",
    "timestamp": "2026-09-25T12:00:00Z",
    "mark_price": "107250",
}
PRICE: dict[str, Any] = {"timestamp": "2026-09-25T12:00:00Z", "mark_price": "107250"}


def _rh_responder(path: str, q: dict[str, str]) -> dict[str, Any]:
    rest = path.removeprefix("/v1/rh-lighter/")
    head = rest.split("/", 1)[0]
    if head == "instruments":
        return envelope([INSTRUMENT] if rest == "instruments" else INSTRUMENT)
    if head == "orderbook":
        return envelope([BOOK] if rest.endswith("/history") else BOOK)
    if head == "trades":
        if rest.endswith("/recent"):
            return envelope(
                [TRADE],
                finalized_through="2026-09-24T21:00:00.000Z",
                preliminary_row_count=1,
            )
        return envelope(
            [TRADE],
            next_cursor="1790337599000_5502",
            finalized_through="2026-09-24T21:00:00.000Z",
            requested_end="2026-09-25T12:00:00.000Z",
            clamped_to="2026-09-24T21:00:00.000Z",
        )
    if head == "funding":
        return envelope(FUNDING if rest.endswith("/current") else [FUNDING])
    if head == "openinterest":
        return envelope(OI if rest.endswith("/current") else [OI])
    if head == "candles":
        return envelope([CANDLE])
    if head == "liquidations":
        return envelope([LIQUIDATION_VOLUME] if rest.endswith("/volume") else [RH_LIQUIDATION])
    if head == "freshness":
        return envelope(FRESHNESS)
    if head == "summary":
        return envelope(SUMMARY)
    if head == "prices":
        return envelope([PRICE])
    raise AssertionError(f"unexpected path {path}")


def test_every_rh_lighter_route_is_served_under_its_own_root() -> None:
    client, api = mock_client(_rh_responder)
    rh = client.rh_lighter
    window = {"start": T_START, "end": T_END}

    rh.instruments.list()
    rh.instruments.get("aapl-usdg")
    rh.orderbook.get("aapl-usdg")
    rh.orderbook.history("AAPL-USDG", **window)
    rh.trades.list("btc", **window)
    rh.trades.recent("BTC")
    rh.candles.history("BTC", **window)
    rh.open_interest.history("BTC", **window)
    rh.open_interest.current("BTC")
    rh.funding.history("BTC", **window)
    rh.funding.current("BTC")
    rh.liquidations.history("BTC", **window)
    rh.liquidations.volume("BTC", **window)
    rh.get_freshness("BTC")
    rh.get_summary("BTC")
    rh.get_price_history("BTC", **window)

    assert [path for path, _ in api.calls] == [
        "/v1/rh-lighter/instruments",
        "/v1/rh-lighter/instruments/AAPL-USDG",
        "/v1/rh-lighter/orderbook/AAPL-USDG",
        "/v1/rh-lighter/orderbook/AAPL-USDG/history",
        "/v1/rh-lighter/trades/BTC",
        "/v1/rh-lighter/trades/BTC/recent",
        "/v1/rh-lighter/candles/BTC",
        "/v1/rh-lighter/openinterest/BTC",
        "/v1/rh-lighter/openinterest/BTC/current",
        "/v1/rh-lighter/funding/BTC",
        "/v1/rh-lighter/funding/BTC/current",
        "/v1/rh-lighter/liquidations/BTC",
        "/v1/rh-lighter/liquidations/BTC/volume",
        "/v1/rh-lighter/freshness/BTC",
        "/v1/rh-lighter/summary/BTC",
        "/v1/rh-lighter/prices/BTC",
    ]
    assert len({path for path, _ in api.calls}) == 16


def test_lighter_mainnet_routes_are_unchanged_by_the_shared_base() -> None:
    client, api = mock_client(
        lambda path, q: envelope(
            FRESHNESS if "/freshness/" in path else SUMMARY if "/summary/" in path else [PRICE]
        )
    )

    client.lighter.get_freshness("btc")
    client.lighter.get_summary("BTC")
    client.lighter.get_price_history("BTC", start=T_START, end=T_END, interval="1h")

    assert api.calls == [
        ("/v1/lighter/freshness/BTC", {}),
        ("/v1/lighter/summary/BTC", {}),
        ("/v1/lighter/prices/BTC", {"start": str(T_START), "end": str(T_END), "interval": "1h"}),
    ]


def test_rh_trades_expose_the_finalization_meta() -> None:
    client, api = mock_client(_rh_responder)

    page = client.rh_lighter.trades.list("BTC", start=T_START, end=T_END)
    recent = client.rh_lighter.trades.recent("BTC", limit=5)

    assert api.calls[0] == ("/v1/rh-lighter/trades/BTC", {"start": str(T_START), "end": str(T_END)})
    assert api.calls[1] == ("/v1/rh-lighter/trades/BTC/recent", {"limit": "5"})
    assert isinstance(page.meta, ResponseMeta)
    assert page.meta.finalized_through is not None
    assert page.meta.clamped_to == page.meta.finalized_through
    assert page.meta.requested_end is not None
    assert page.next_cursor == "1790337599000_5502"
    assert page.data[0].account_index == "4521"
    assert isinstance(recent, list) and isinstance(recent[0], Trade)


def test_spot_symbols_are_uppercased_and_path_encoded() -> None:
    client, api = mock_client(_rh_responder)

    client.rh_lighter.orderbook.get("aapl-usdg")

    assert api.raw_paths == ["/v1/rh-lighter/orderbook/AAPL-USDG"]


# ---------------------------------------------------------------------------
# Lighter liquidations (both deployments)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "venue, root", [("lighter", "/v1/lighter"), ("rh_lighter", "/v1/rh-lighter")]
)
def test_lighter_liquidations_history_and_volume(venue: str, root: str) -> None:
    def respond(path: str, q: dict[str, str]) -> dict[str, Any]:
        if path.endswith("/volume"):
            return envelope([LIQUIDATION_VOLUME], next_cursor="1788220800000")
        return envelope(
            [RH_LIQUIDATION, RH_LIQUIDATION_LIVE], next_cursor="1788240575923_324449287"
        )

    client, api = mock_client(respond)
    liquidations = getattr(client, venue).liquidations

    history = liquidations.history(
        "btc", start="2026-06-26T20:10:26Z", end=T_END, cursor="1782602083534_5501", limit=500
    )
    volume = liquidations.volume("BTC", start=T_START, end=T_END, interval="4h", limit=10)

    assert api.calls == [
        (
            f"{root}/liquidations/BTC",
            {
                "start": "1782504626000",
                "end": str(T_END),
                "cursor": "1782602083534_5501",
                "limit": "500",
            },
        ),
        (
            f"{root}/liquidations/BTC/volume",
            {"start": str(T_START), "end": str(T_END), "interval": "4h", "limit": "10"},
        ),
    ]
    row = history.data[0]
    assert isinstance(row, LighterLiquidation)
    assert row.timestamp == 1782602083534 and row.trade_id == 5501
    assert row.source == "bucket" and row.raw_json == ""
    live = history.data[1]
    assert live.source == "ws" and live.raw_json and live.raw_json.startswith("{")
    assert row.ask_account == "281474976710654" and row.is_maker_ask is False
    assert row.taker_position_sign_changed is True
    assert history.next_cursor == "1788240575923_324449287"
    assert isinstance(history.meta, ResponseMeta)
    bucket = volume.data[0]
    assert isinstance(bucket, LighterLiquidationVolume)
    assert bucket.total_usd == pytest.approx(1340.63125) and bucket.count == 1
    assert volume.next_cursor == "1788220800000"


def test_lighter_liquidations_async() -> None:
    client, api = mock_client(
        lambda path, q: envelope(
            [LIQUIDATION_VOLUME] if path.endswith("/volume") else [RH_LIQUIDATION]
        )
    )

    async def run() -> tuple[Any, Any]:
        history = await client.rh_lighter.liquidations.ahistory("BTC", start=T_START, end=T_END)
        volume = await client.lighter.liquidations.avolume("BTC")
        await client.aclose()
        return history, volume

    history, volume = asyncio.run(run())

    assert [path for path, _ in api.calls] == [
        "/v1/rh-lighter/liquidations/BTC",
        "/v1/lighter/liquidations/BTC/volume",
    ]
    assert history.data[0].source == "bucket"
    assert volume.data[0].count == 1


def test_rh_liquidations_copy_uses_the_venue_launch_floor() -> None:
    # Robinhood Chain liquidations share the trades floor (venue launch); only
    # order book, open interest and funding start at live capture.
    root = Path(__file__).resolve().parents[1]
    copy = {
        name: (root / name).read_text()
        for name in (
            "README.md",
            "CHANGELOG.md",
            "oxarchive/__init__.py",
            "oxarchive/client.py",
            "oxarchive/exchanges.py",
            "oxarchive/resources/lighter_liquidations.py",
        )
    }
    readme = " ".join(copy["README.md"].split())
    assert "Trades and liquidations from 2026-06-26 20:10:26 UTC (venue launch)" in readme
    assert "trades and liquidations from the venue launch, 2026-06-26 20:10:26 UTC" in readme
    for name, text in copy.items():
        flat = " ".join(text.split())
        assert "funding, and liquidations from 2026-08-22" not in flat, name
        assert "funding and liquidations from 2026-08-22" not in flat, name
        assert "liquidations start 2026-08-22" not in flat, name


# ---------------------------------------------------------------------------
# WebSocket
# ---------------------------------------------------------------------------


def _connected() -> tuple[OxArchiveWs, FakeSocket]:
    ws = OxArchiveWs(WsOptions(api_key="test-key"))
    socket = FakeSocket()
    setattr(ws, "_ws", socket)
    return ws, socket


def _data(channel: str, payload: Any, coin: str = "BTC") -> str:
    return json.dumps(
        {"type": "data", "channel": channel, "coin": coin, "symbol": coin, "data": payload}
    )


def test_rh_channel_sets() -> None:
    assert RH_LIGHTER_LIVE_CHANNELS == {
        "rh_lighter_orderbook",
        "rh_lighter_trades",
        "rh_lighter_open_interest",
        "rh_lighter_funding",
    }
    assert RH_LIGHTER_REPLAY_ONLY_CHANNELS == {"rh_lighter_candles"}
    assert RH_LIGHTER_REPLAY_CHANNELS == RH_LIGHTER_LIVE_CHANNELS | {"rh_lighter_candles"}
    assert not RH_LIGHTER_REPLAY_CHANNELS & LIGHTER_LIVE_CHANNELS
    channels = set(WsChannel.__args__)  # type: ignore[attr-defined]
    assert RH_LIGHTER_REPLAY_CHANNELS <= channels


def test_rh_lighter_candles_is_replay_only() -> None:
    ws, socket = _connected()

    with pytest.raises(ValueError, match=re.escape(RH_LIGHTER_SUBSCRIPTION_ERROR)):
        ws.subscribe("rh_lighter_candles", "BTC")

    async def run() -> None:
        with pytest.raises(ValueError, match=re.escape(RH_LIGHTER_SUBSCRIPTION_ERROR)):
            await ws.subscribe_async("rh_lighter_candles", "BTC")

    asyncio.run(run())
    assert ws._subscriptions == set()
    assert socket.sent == []


@pytest.mark.parametrize("channel", sorted(RH_LIGHTER_LIVE_CHANNELS))
def test_rh_live_channels_send_a_plain_subscribe(channel: str) -> None:
    ws, socket = _connected()

    asyncio.run(ws.subscribe_async(cast(WsChannel, channel), "btc"))

    assert ws._subscriptions == {f"{channel}:BTC"}
    assert socket.sent == [{"op": "subscribe", "channel": channel, "symbol": "btc"}]


def test_rh_convenience_helpers_send_subscribe_and_unsubscribe() -> None:
    ws, socket = _connected()

    async def run() -> None:
        ws.subscribe_rh_lighter_orderbook("AAPL-USDG")
        ws.subscribe_rh_lighter_orderbook("BTC", interval_ms=500)
        ws.subscribe_rh_lighter_trades("BTC")
        ws.subscribe_rh_lighter_open_interest("BTC")
        ws.subscribe_rh_lighter_funding("BTC")
        await asyncio.sleep(0)
        ws.unsubscribe_rh_lighter_orderbook("BTC")
        ws.unsubscribe_rh_lighter_trades("BTC")
        ws.unsubscribe_rh_lighter_open_interest("BTC")
        ws.unsubscribe_rh_lighter_funding("BTC")
        await asyncio.sleep(0)

    asyncio.run(run())

    assert socket.sent == [
        {"op": "subscribe", "channel": "rh_lighter_orderbook", "symbol": "AAPL-USDG"},
        {"op": "subscribe", "channel": "rh_lighter_orderbook", "symbol": "BTC", "interval_ms": 500},
        {"op": "subscribe", "channel": "rh_lighter_trades", "symbol": "BTC"},
        {"op": "subscribe", "channel": "rh_lighter_open_interest", "symbol": "BTC"},
        {"op": "subscribe", "channel": "rh_lighter_funding", "symbol": "BTC"},
        {"op": "unsubscribe", "channel": "rh_lighter_orderbook", "symbol": "BTC"},
        {"op": "unsubscribe", "channel": "rh_lighter_trades", "symbol": "BTC"},
        {"op": "unsubscribe", "channel": "rh_lighter_open_interest", "symbol": "BTC"},
        {"op": "unsubscribe", "channel": "rh_lighter_funding", "symbol": "BTC"},
    ]
    assert ws._subscriptions == {"rh_lighter_orderbook:AAPL-USDG"}


def test_rh_interval_ms_rules_match_the_server() -> None:
    ws, socket = _connected()

    with pytest.raises(
        ValueError, match=re.escape("interval_ms is only supported on rh_lighter_orderbook.")
    ):
        ws.subscribe("rh_lighter_trades", "BTC", interval_ms=250)
    with pytest.raises(
        ValueError,
        match=re.escape(
            "interval_ms must be between 100 and 5000 for rh_lighter_orderbook (got 99). "
            "Leave it out for one book a second."
        ),
    ):
        ws.subscribe_rh_lighter_orderbook("BTC", interval_ms=99)
    with pytest.raises(ValueError, match="integer"):
        ws.subscribe_rh_lighter_orderbook("BTC", interval_ms=cast(int, 250.0))
    # Mainnet wording is unchanged for mainnet and Hyperliquid channels.
    with pytest.raises(
        ValueError, match=re.escape("interval_ms is only supported on lighter_orderbook.")
    ):
        ws.subscribe("lighter_trades", "BTC", interval_ms=250)

    assert ws._subscriptions == set()
    assert socket.sent == []


def test_rh_subscriptions_are_case_insensitive_and_survive_reconnect() -> None:
    ws, socket = _connected()

    async def run() -> None:
        await ws.subscribe_async("rh_lighter_orderbook", "aapl-usdg", interval_ms=250)
        await ws.subscribe_async("rh_lighter_trades", "btc")
        await ws.unsubscribe_async("rh_lighter_trades", "BTC")
        socket.sent.clear()
        await ws._resubscribe()

    asyncio.run(run())
    assert ws._subscriptions == {"rh_lighter_orderbook:AAPL-USDG"}
    assert socket.sent == [
        {
            "op": "subscribe",
            "channel": "rh_lighter_orderbook",
            "symbol": "AAPL-USDG",
            "interval_ms": 250,
        }
    ]


def test_rh_messages_reach_their_own_handlers_not_the_mainnet_ones() -> None:
    ws = OxArchiveWs(WsOptions(api_key="test-key"))
    got: dict[str, list[Any]] = {"rh_book": [], "rh_trades": [], "rh_ctx": [], "mainnet": []}
    mainnet: Callable[..., None] = lambda *args: got["mainnet"].append(args)  # noqa: E731
    ws.on_lighter_orderbook(mainnet)
    ws.on_lighter_trades(mainnet)
    ws.on_lighter_market_context(mainnet)
    ws.on_orderbook(mainnet)
    ws.on_trades(mainnet)
    ws.on_rh_lighter_orderbook(lambda coin, book: got["rh_book"].append((coin, book)))
    ws.on_rh_lighter_trades(lambda coin, legs: got["rh_trades"].append((coin, legs)))
    ws.on_rh_lighter_market_context(lambda ch, coin, ctx: got["rh_ctx"].append((ch, coin, ctx)))

    ws._handle_message(_data("rh_lighter_orderbook", LIGHTER_BOOK_FRAME))
    ws._handle_message(_data("rh_lighter_trades", LIGHTER_TRADES_FRAME))
    ws._handle_message(_data("rh_lighter_open_interest", LIGHTER_CTX_FRAME))
    ws._handle_message(_data("rh_lighter_funding", LIGHTER_CTX_FRAME))

    assert got["mainnet"] == []
    coin, book = got["rh_book"][0]
    assert coin == "BTC" and isinstance(book, OrderBook)
    assert book.bids[0].px == "84368.7" and book.asks[0].px == "84368.8"
    legs = got["rh_trades"][0][1]
    assert [leg.account_index for leg in legs] == ["281474976623827", "713845"]
    assert {leg.trade_id for leg in legs} == {31944180930}
    assert [entry[0] for entry in got["rh_ctx"]] == [
        "rh_lighter_open_interest",
        "rh_lighter_funding",
    ]
    assert got["rh_ctx"][0][2].open_interest == "172706178.266310"


def test_rh_books_and_trades_fall_back_to_the_generic_handlers() -> None:
    ws = OxArchiveWs(WsOptions(api_key="test-key"))
    books: list[Any] = []
    trades: list[Any] = []
    lighter_only: list[Any] = []
    ws.on_orderbook(lambda coin, book: books.append(book))
    ws.on_trades(lambda coin, legs: trades.extend(legs))
    ws.on_lighter_orderbook(lambda coin, book: lighter_only.append(book))

    ws._handle_message(_data("rh_lighter_orderbook", LIGHTER_BOOK_FRAME))
    ws._handle_message(_data("rh_lighter_trades", LIGHTER_TRADES_FRAME))

    assert len(books) == 1 and isinstance(books[0], OrderBook)
    assert len(trades) == 2 and trades[0].account_index == "281474976623827"
    assert lighter_only == []


def test_rh_subscribe_ack_and_data_envelope_are_typed() -> None:
    ws = OxArchiveWs(WsOptions(api_key="test-key"))
    messages: list[object] = []
    ws.on_message(messages.append)

    ws._handle_message(
        json.dumps(
            {"type": "subscribed", "channel": "rh_lighter_trades", "coin": "BTC", "symbol": "BTC"}
        )
    )
    ws._handle_message(_data("rh_lighter_trades", LIGHTER_TRADES_FRAME))

    assert isinstance(messages[0], WsSubscribed) and messages[0].channel == "rh_lighter_trades"
    assert isinstance(messages[1], WsData) and messages[1].channel == "rh_lighter_trades"


@pytest.mark.parametrize("channel", sorted(RH_LIGHTER_REPLAY_CHANNELS))
def test_every_rh_channel_replays(channel: str) -> None:
    ws = OxArchiveWs(WsOptions(api_key="test-key"))
    sent: list[dict[str, Any]] = []

    async def fake_send(message: dict[str, Any]) -> None:
        sent.append(message)

    setattr(ws, "_send", fake_send)

    asyncio.run(
        ws.replay(cast(WsChannel, channel), "BTC", start=1_788_000_000_000, end=1_788_003_600_000)
    )

    assert sent == [
        {
            "op": "replay",
            "channel": channel,
            "symbol": "BTC",
            "start": 1_788_000_000_000,
            "speed": 1.0,
            "end": 1_788_003_600_000,
        }
    ]


def test_rh_multi_replay_sends_the_rh_channel_family() -> None:
    ws = OxArchiveWs(WsOptions(api_key="test-key"))
    sent: list[dict[str, Any]] = []

    async def fake_send(message: dict[str, Any]) -> None:
        sent.append(message)

    setattr(ws, "_send", fake_send)
    channels = cast(
        list[WsChannel],
        [
            "rh_lighter_orderbook",
            "rh_lighter_trades",
            "rh_lighter_open_interest",
            "rh_lighter_funding",
        ],
    )

    asyncio.run(
        ws.multi_replay(channels, "BTC", start=1_788_000_000_000, end=1_788_003_600_000, speed=10)
    )

    assert sent[0]["op"] == "replay" and sent[0]["channels"] == channels
