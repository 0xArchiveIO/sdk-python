import asyncio
import json
import re
from datetime import datetime, timezone
from typing import Any, cast

import pytest
from websockets.protocol import State as WsState

from oxarchive.types import (
    LighterLiveTrade,
    LighterMarketContext,
    LighterMarketContextUpdate,
    OrderBook,
    Trade,
    WsChannel,
    WsData,
    WsError,
    WsL4Batch,
    WsL4Snapshot,
    WsSubscribed,
)
from oxarchive.websocket import (
    LIGHTER_LIVE_CHANNELS,
    LIGHTER_REPLAY_CHANNELS,
    LIGHTER_REPLAY_ONLY_CHANNELS,
    LIGHTER_SUBSCRIPTION_ERROR,
    OxArchiveWs,
    WsOptions,
)

# Frames captured from the production WebSocket (orderbook truncated to three
# levels per side; live frames carry up to 20).
LIGHTER_BOOK_FRAME: dict[str, Any] = {
    "coin": "BTC",
    "time": 1790294171459,
    "levels": [
        [
            {"px": "84368.7", "sz": "0.00020", "n": 1},
            {"px": "84368.6", "sz": "0.00020", "n": 1},
            {"px": "84368.3", "sz": "0.00010", "n": 1},
        ],
        [
            {"px": "84368.8", "sz": "0.05720", "n": 1},
            {"px": "84368.9", "sz": "0.14223", "n": 1},
            {"px": "84369.1", "sz": "0.01198", "n": 1},
        ],
    ],
}

LIGHTER_TRADES_FRAME: list[dict[str, Any]] = [
    {
        "coin": "BTC",
        "side": "A",
        "px": "84367.9",
        "sz": "0.00003",
        "time": 1790294182211,
        "hash": "0000001dc8774b28000001a0d5d94943000000000000000000000000000000000000000000000000",
        "tid": 31944180930,
        "oid": 562953419896990,
        "crossed": False,
        "dir": None,
        "fee": None,
        "fee_token": None,
        "closed_pnl": None,
        "start_position": "109.79011",
        "users": ["281474976623827"],
    },
    {
        "coin": "BTC",
        "side": "B",
        "px": "84367.9",
        "sz": "0.00003",
        "time": 1790294182211,
        "hash": "0000001dc8774b28000001a0d5d94943000000000000000000000000000000000000000000000000",
        "tid": 31944180930,
        "oid": 844421425107071,
        "crossed": True,
        "dir": None,
        "fee": None,
        "fee_token": None,
        "closed_pnl": None,
        "start_position": "0.03940",
        "users": ["713845"],
    },
]

LIGHTER_CTX_FRAME: dict[str, Any] = {
    "coin": "BTC",
    "ctx": {
        "openInterest": "172706178.266310",
        "funding": "0.000012",
        "premium": "-0.000327",
        "markPx": "84363.5",
        "oraclePx": "84397.0",
        "midPx": "84368.8",
        "dayNtlVlm": "908611371.550746",
        "dayBaseVlm": "10808.97087",
        "prevDayPx": "84285.9",
        "impactPxs": None,
    },
}


def _data_message(channel: str, payload: Any) -> str:
    return json.dumps(
        {"type": "data", "channel": channel, "coin": "BTC", "symbol": "BTC", "data": payload}
    )


class FakeSocket:
    """Stands in for an open connection and records what the client sends."""

    def __init__(self) -> None:
        self.state = WsState.OPEN
        self.sent: list[dict[str, Any]] = []

    async def send(self, raw: str) -> None:
        self.sent.append(json.loads(raw))


def _connected_client() -> tuple[OxArchiveWs, FakeSocket]:
    ws = OxArchiveWs(WsOptions(api_key="test-key"))
    socket = FakeSocket()
    setattr(ws, "_ws", socket)
    return ws, socket


def test_lighter_channel_sets_split_live_and_replay_only() -> None:
    assert LIGHTER_LIVE_CHANNELS == {
        "lighter_orderbook",
        "lighter_trades",
        "lighter_open_interest",
        "lighter_funding",
    }
    assert LIGHTER_REPLAY_ONLY_CHANNELS == {"lighter_candles", "lighter_l3_orderbook"}
    assert LIGHTER_REPLAY_CHANNELS == LIGHTER_LIVE_CHANNELS | LIGHTER_REPLAY_ONLY_CHANNELS


@pytest.mark.parametrize("channel", sorted(LIGHTER_REPLAY_ONLY_CHANNELS))
def test_replay_only_lighter_channels_reject_live_subscription_before_state_change(
    channel: str,
) -> None:
    channel = cast(WsChannel, channel)
    ws = OxArchiveWs(WsOptions(api_key="test-key"))

    with pytest.raises(ValueError, match=re.escape(LIGHTER_SUBSCRIPTION_ERROR)):
        ws.subscribe(channel, "BTC")

    assert ws._subscriptions == set()


@pytest.mark.parametrize("channel", sorted(LIGHTER_REPLAY_ONLY_CHANNELS))
def test_replay_only_lighter_channels_reject_async_live_subscription_before_state_change(
    channel: str,
) -> None:
    channel = cast(WsChannel, channel)
    ws = OxArchiveWs(WsOptions(api_key="test-key"))

    async def run() -> None:
        with pytest.raises(ValueError, match=re.escape(LIGHTER_SUBSCRIPTION_ERROR)):
            await ws.subscribe_async(channel, "BTC")

    asyncio.run(run())
    assert ws._subscriptions == set()


@pytest.mark.parametrize("channel", sorted(LIGHTER_LIVE_CHANNELS))
def test_live_lighter_channels_send_a_plain_subscribe(channel: str) -> None:
    channel = cast(WsChannel, channel)
    ws, socket = _connected_client()

    asyncio.run(ws.subscribe_async(channel, "BTC"))

    assert ws._subscriptions == {f"{channel}:BTC"}
    assert socket.sent == [{"op": "subscribe", "channel": channel, "symbol": "BTC"}]


def test_lighter_convenience_helpers_send_subscribe_and_unsubscribe() -> None:
    ws, socket = _connected_client()

    async def run() -> None:
        ws.subscribe_lighter_orderbook("BTC")
        ws.subscribe_lighter_orderbook("ETH", interval_ms=250)
        ws.subscribe_lighter_trades("BTC")
        ws.subscribe_lighter_open_interest("BTC")
        ws.subscribe_lighter_funding("BTC")
        await asyncio.sleep(0)
        ws.unsubscribe_lighter_orderbook("ETH")
        ws.unsubscribe_lighter_trades("BTC")
        ws.unsubscribe_lighter_open_interest("BTC")
        ws.unsubscribe_lighter_funding("BTC")
        await asyncio.sleep(0)

    asyncio.run(run())

    assert socket.sent == [
        {"op": "subscribe", "channel": "lighter_orderbook", "symbol": "BTC"},
        {"op": "subscribe", "channel": "lighter_orderbook", "symbol": "ETH", "interval_ms": 250},
        {"op": "subscribe", "channel": "lighter_trades", "symbol": "BTC"},
        {"op": "subscribe", "channel": "lighter_open_interest", "symbol": "BTC"},
        {"op": "subscribe", "channel": "lighter_funding", "symbol": "BTC"},
        {"op": "unsubscribe", "channel": "lighter_orderbook", "symbol": "ETH"},
        {"op": "unsubscribe", "channel": "lighter_trades", "symbol": "BTC"},
        {"op": "unsubscribe", "channel": "lighter_open_interest", "symbol": "BTC"},
        {"op": "unsubscribe", "channel": "lighter_funding", "symbol": "BTC"},
    ]
    assert ws._subscriptions == {"lighter_orderbook:BTC"}
    assert ws._subscription_options == {}


@pytest.mark.parametrize("interval_ms", [100, 250, 1000, 5000])
def test_lighter_orderbook_interval_ms_is_sent_on_the_wire(interval_ms: int) -> None:
    ws, socket = _connected_client()

    asyncio.run(ws.subscribe_async("lighter_orderbook", "btc", interval_ms=interval_ms))

    assert socket.sent == [
        {
            "op": "subscribe",
            "channel": "lighter_orderbook",
            "symbol": "btc",
            "interval_ms": interval_ms,
        }
    ]


@pytest.mark.parametrize("interval_ms", [50, 99, 5001, 0, -1])
def test_lighter_orderbook_interval_ms_out_of_range_is_rejected(interval_ms: int) -> None:
    ws, socket = _connected_client()
    expected = (
        f"interval_ms must be between 100 and 5000 for lighter_orderbook (got {interval_ms}). "
        "Leave it out for one book a second."
    )

    with pytest.raises(ValueError, match=re.escape(expected)):
        ws.subscribe_lighter_orderbook("BTC", interval_ms=interval_ms)

    assert ws._subscriptions == set()
    assert socket.sent == []


@pytest.mark.parametrize("interval_ms", [True, 250.0, "250"])
def test_lighter_orderbook_interval_ms_must_be_an_integer(interval_ms: Any) -> None:
    ws = OxArchiveWs(WsOptions(api_key="test-key"))
    expected = f"interval_ms must be an integer number of milliseconds (got {interval_ms!r})."

    with pytest.raises(ValueError, match=re.escape(expected)):
        ws.subscribe("lighter_orderbook", "BTC", interval_ms=interval_ms)

    assert ws._subscriptions == set()


@pytest.mark.parametrize(
    "channel", ["lighter_trades", "lighter_open_interest", "lighter_funding", "orderbook"]
)
def test_interval_ms_is_only_accepted_on_lighter_orderbook(channel: str) -> None:
    channel = cast(WsChannel, channel)
    ws, socket = _connected_client()

    async def run() -> None:
        with pytest.raises(
            ValueError, match=re.escape("interval_ms is only supported on lighter_orderbook.")
        ):
            await ws.subscribe_async(channel, "BTC", interval_ms=250)

    asyncio.run(run())
    assert ws._subscriptions == set()
    assert socket.sent == []


def test_reconnect_resends_interval_ms_and_a_resubscribe_replaces_it() -> None:
    ws, socket = _connected_client()

    async def run() -> None:
        await ws.subscribe_async("lighter_orderbook", "BTC", interval_ms=250)
        await ws.subscribe_async("lighter_trades", "BTC")
        socket.sent.clear()
        await ws._resubscribe()

    asyncio.run(run())
    assert sorted(socket.sent, key=lambda m: m["channel"]) == [
        {"op": "subscribe", "channel": "lighter_orderbook", "symbol": "BTC", "interval_ms": 250},
        {"op": "subscribe", "channel": "lighter_trades", "symbol": "BTC"},
    ]

    async def resubscribe_without_interval() -> None:
        await ws.subscribe_async("lighter_orderbook", "BTC")
        socket.sent.clear()
        await ws._resubscribe()

    asyncio.run(resubscribe_without_interval())
    assert {"op": "subscribe", "channel": "lighter_orderbook", "symbol": "BTC"} in socket.sent
    assert all("interval_ms" not in message for message in socket.sent)


def test_lighter_symbols_are_tracked_case_insensitively() -> None:
    ws, socket = _connected_client()

    async def run() -> None:
        await ws.subscribe_async("lighter_orderbook", "btc", interval_ms=250)
        await ws.subscribe_async("lighter_trades", "eth")
        await ws.unsubscribe_async("lighter_orderbook", "BTC")
        socket.sent.clear()
        await ws._resubscribe()

    asyncio.run(run())
    assert ws._subscriptions == {"lighter_trades:ETH"}
    assert ws._subscription_options == {}
    assert socket.sent == [{"op": "subscribe", "channel": "lighter_trades", "symbol": "ETH"}]


def test_a_differently_cased_lighter_resubscribe_replaces_the_interval() -> None:
    ws, socket = _connected_client()

    async def run() -> None:
        await ws.subscribe_async("lighter_orderbook", "btc", interval_ms=250)
        await ws.subscribe_async("lighter_orderbook", "BTC")
        socket.sent.clear()
        await ws._resubscribe()

    asyncio.run(run())
    assert ws._subscriptions == {"lighter_orderbook:BTC"}
    assert ws._subscription_options == {}
    assert socket.sent == [{"op": "subscribe", "channel": "lighter_orderbook", "symbol": "BTC"}]


def test_hyperliquid_symbols_keep_their_case() -> None:
    ws, _ = _connected_client()

    asyncio.run(ws.subscribe_async("trades", "kPEPE"))

    assert ws._subscriptions == {"trades:kPEPE"}


@pytest.mark.parametrize("channel", sorted(LIGHTER_REPLAY_CHANNELS))
def test_every_lighter_channel_still_replays(channel: str) -> None:
    channel = cast(WsChannel, channel)
    ws = OxArchiveWs(WsOptions(api_key="test-key"))
    sent: list[dict[str, Any]] = []

    async def fake_send(message: dict[str, Any]) -> None:
        sent.append(message)

    setattr(ws, "_send", fake_send)

    asyncio.run(ws.replay(channel, "BTC", start=1_757_000_000_000, end=1_757_003_600_000))

    assert sent == [
        {
            "op": "replay",
            "channel": channel,
            "symbol": "BTC",
            "start": 1_757_000_000_000,
            "speed": 1.0,
            "end": 1_757_003_600_000,
        }
    ]


def test_lighter_channels_are_allowed_for_bounded_replay() -> None:
    ws = OxArchiveWs(WsOptions(api_key="test-key"))
    sent: list[dict[str, Any]] = []

    async def fake_send(message: dict[str, Any]) -> None:
        sent.append(message)

    setattr(ws, "_send", fake_send)

    asyncio.run(
        ws.replay(
            "lighter_orderbook",
            "BTC",
            start=1_757_000_000_000,
            end=1_757_003_600_000,
        )
    )

    assert sent == [
        {
            "op": "replay",
            "channel": "lighter_orderbook",
            "symbol": "BTC",
            "start": 1_757_000_000_000,
            "speed": 1.0,
            "end": 1_757_003_600_000,
        }
    ]


def test_lighter_subscribe_ack_and_data_envelope_are_typed() -> None:
    ws = OxArchiveWs(WsOptions(api_key="test-key"))
    messages: list[object] = []
    ws.on_message(messages.append)

    ws._handle_message(
        json.dumps(
            {"type": "subscribed", "channel": "lighter_orderbook", "coin": "BTC", "symbol": "BTC"}
        )
    )
    ws._handle_message(_data_message("lighter_orderbook", LIGHTER_BOOK_FRAME))

    ack, data = messages
    assert isinstance(ack, WsSubscribed)
    assert ack.channel == "lighter_orderbook"
    assert ack.symbol == "BTC"
    assert isinstance(data, WsData)
    assert data.channel == "lighter_orderbook"
    assert data.symbol == "BTC"
    assert isinstance(data.data, dict)
    assert data.data["levels"][0][0] == {"px": "84368.7", "sz": "0.00020", "n": 1}


def test_lighter_orderbook_frame_decodes_to_orderbook() -> None:
    ws = OxArchiveWs(WsOptions(api_key="test-key"))
    lighter_books: list[tuple[str, OrderBook]] = []
    generic_books: list[tuple[str, OrderBook]] = []
    ws.on_lighter_orderbook(lambda coin, book: lighter_books.append((coin, book)))
    ws.on_orderbook(lambda coin, book: generic_books.append((coin, book)))

    ws._handle_message(_data_message("lighter_orderbook", LIGHTER_BOOK_FRAME))

    assert generic_books == []
    ((coin, book),) = lighter_books
    assert coin == "BTC"
    assert [level.px for level in book.bids] == ["84368.7", "84368.6", "84368.3"]
    assert [level.px for level in book.asks] == ["84368.8", "84368.9", "84369.1"]
    assert book.bids[0].sz == "0.00020"
    assert {level.n for level in book.bids + book.asks} == {1}
    assert book.timestamp == datetime.fromtimestamp(1790294171459 / 1000, tz=timezone.utc)
    assert book.mid_price is not None
    assert float(book.mid_price) == pytest.approx(84368.75)


def test_lighter_orderbook_falls_back_to_on_orderbook() -> None:
    ws = OxArchiveWs(WsOptions(api_key="test-key"))
    books: list[tuple[str, OrderBook]] = []
    ws.on_orderbook(lambda coin, book: books.append((coin, book)))

    ws._handle_message(_data_message("lighter_orderbook", LIGHTER_BOOK_FRAME))

    assert len(books) == 1
    assert books[0][1].asks[0].px == "84368.8"


def test_lighter_trades_frame_decodes_to_two_legs_per_trade() -> None:
    ws = OxArchiveWs(WsOptions(api_key="test-key"))
    lighter_trades: list[tuple[str, list[Trade]]] = []
    generic_trades: list[tuple[str, list[Trade]]] = []
    ws.on_lighter_trades(lambda coin, trades: lighter_trades.append((coin, trades)))
    ws.on_trades(lambda coin, trades: generic_trades.append((coin, trades)))

    ws._handle_message(_data_message("lighter_trades", LIGHTER_TRADES_FRAME))

    assert generic_trades == []
    ((coin, (ask_leg, bid_leg)),) = lighter_trades
    assert coin == "BTC"
    assert ask_leg.trade_id == bid_leg.trade_id == 31944180930
    assert (ask_leg.side, ask_leg.crossed, ask_leg.account_index) == ("A", False, "281474976623827")
    assert (bid_leg.side, bid_leg.crossed, bid_leg.account_index) == ("B", True, "713845")
    assert ask_leg.order_id == 562953419896990
    assert bid_leg.order_id == 844421425107071
    assert ask_leg.start_position == "109.79011"
    assert bid_leg.start_position == "0.03940"
    assert ask_leg.price == bid_leg.price == "84367.9"
    assert ask_leg.size == "0.00003"
    assert ask_leg.tx_hash == LIGHTER_TRADES_FRAME[0]["hash"]
    assert ask_leg.timestamp == datetime.fromtimestamp(1790294182211 / 1000, tz=timezone.utc)
    for leg in (ask_leg, bid_leg):
        assert leg.fee is None
        assert leg.fee_token is None
        assert leg.closed_pnl is None
        assert leg.direction is None
        assert leg.user_address is None
        assert leg.maker_address is None
        assert leg.taker_address is None
    assert len({leg.trade_id for leg in (ask_leg, bid_leg)}) == 1


def test_lighter_trades_fall_back_to_on_trades() -> None:
    ws = OxArchiveWs(WsOptions(api_key="test-key"))
    received: list[list[Trade]] = []
    ws.on_trades(lambda _coin, trades: received.append(trades))

    ws._handle_message(_data_message("lighter_trades", LIGHTER_TRADES_FRAME))

    assert [leg.account_index for leg in received[0]] == ["281474976623827", "713845"]


def test_lighter_live_trade_model_parses_the_wire_leg() -> None:
    legs = [LighterLiveTrade.model_validate(raw) for raw in LIGHTER_TRADES_FRAME]

    assert [leg.account_index for leg in legs] == ["281474976623827", "713845"]
    assert [leg.crossed for leg in legs] == [False, True]
    assert all(leg.fee is None and leg.dir is None for leg in legs)
    assert LighterLiveTrade.model_validate({**LIGHTER_TRADES_FRAME[0], "users": []}).account_index is None


@pytest.mark.parametrize("channel", ["lighter_open_interest", "lighter_funding"])
def test_lighter_market_context_frame_decodes_on_both_channels(channel: str) -> None:
    ws = OxArchiveWs(WsOptions(api_key="test-key"))
    received: list[tuple[str, str, LighterMarketContext]] = []
    ws.on_lighter_market_context(lambda ch, coin, ctx: received.append((ch, coin, ctx)))

    ws._handle_message(_data_message(channel, LIGHTER_CTX_FRAME))

    ((received_channel, coin, ctx),) = received
    assert received_channel == channel
    assert coin == "BTC"
    assert ctx.open_interest == "172706178.266310"
    assert ctx.funding_rate == "0.000012"
    assert ctx.premium == "-0.000327"
    assert ctx.mark_price == "84363.5"
    assert ctx.oracle_price == "84397.0"
    assert ctx.mid_price == "84368.8"
    assert ctx.day_ntl_volume == "908611371.550746"
    assert ctx.day_base_volume == "10808.97087"
    assert ctx.prev_day_price == "84285.9"
    assert ctx.impact_prices is None


def test_lighter_market_context_round_trips_wire_keys() -> None:
    update = LighterMarketContextUpdate.model_validate(LIGHTER_CTX_FRAME)

    assert update.coin == "BTC"
    assert update.ctx.model_dump(by_alias=True) == LIGHTER_CTX_FRAME["ctx"]
    assert LighterMarketContext.model_validate({"funding_rate": "0.0001"}).funding_rate == "0.0001"
    assert LighterMarketContext.model_validate({}).open_interest is None


def test_lighter_lag_notices_reach_on_message_as_errors() -> None:
    ws = OxArchiveWs(WsOptions(api_key="test-key"))
    messages: list[object] = []
    ws.on_message(messages.append)
    notice = (
        "Dropped ~12 live lighter_trades messages for BTC: your connection fell behind "
        "the Lighter stream, and those trades were not delivered."
    )

    ws._handle_message(json.dumps({"type": "error", "message": notice}))

    assert isinstance(messages[0], WsError)
    assert messages[0].message == notice


def test_trade_model_accepts_rest_lighter_account_index() -> None:
    trade = Trade.model_validate(
        {
            "coin": "BTC",
            "side": "B",
            "price": "84367.9",
            "size": "0.00003",
            "timestamp": "2026-09-24T21:56:22.211Z",
            "trade_id": 31944180930,
            "crossed": True,
            "account_index": "713845",
        }
    )

    assert trade.account_index == "713845"
    assert trade.user_address is None


def test_hyperliquid_live_subscription_remains_allowed() -> None:
    ws = OxArchiveWs(WsOptions(api_key="test-key"))

    ws.subscribe("orderbook", "BTC")

    assert ws._subscriptions == {"orderbook:BTC"}


@pytest.mark.parametrize(
    "channel",
    [
        "hip3_l4_diffs",
        "hip3_l4_orders",
        "hip4_l4_diffs",
        "hip4_l4_orders",
        "spot_l4_diffs",
        "spot_l4_orders",
    ],
)
def test_non_core_l4_channels_remain_live_only_for_replay(channel: str) -> None:
    channel = cast(WsChannel, channel)
    ws = OxArchiveWs(WsOptions(api_key="test-key"))
    sent: list[dict[str, Any]] = []

    async def fake_send(message: dict[str, Any]) -> None:
        sent.append(message)

    setattr(ws, "_send", fake_send)

    with pytest.raises(ValueError, match="live subscriptions only"):
        asyncio.run(ws.replay(channel, "BTC", start=1_757_000_000_000))

    assert sent == []


@pytest.mark.parametrize("channel", ["hip3_l4_diffs", "hip4_l4_orders", "spot_l4_diffs"])
def test_non_core_l4_channels_remain_live_only_for_multi_replay(channel: str) -> None:
    channel = cast(WsChannel, channel)
    ws = OxArchiveWs(WsOptions(api_key="test-key"))
    sent: list[dict[str, Any]] = []

    async def fake_send(message: dict[str, Any]) -> None:
        sent.append(message)

    setattr(ws, "_send", fake_send)

    with pytest.raises(ValueError, match="live subscriptions only"):
        asyncio.run(ws.multi_replay(["orderbook", channel], "BTC", start=1_757_000_000_000))

    assert sent == []


def test_core_l4_replay_command_remains_allowed() -> None:
    ws = OxArchiveWs(WsOptions(api_key="test-key"))
    sent: list[dict[str, Any]] = []

    async def fake_send(message: dict[str, Any]) -> None:
        sent.append(message)

    setattr(ws, "_send", fake_send)

    asyncio.run(
        ws.replay(
            "l4_orders",
            "BTC",
            start=1_757_000_000_000,
            end=1_757_003_600_000,
        )
    )

    assert sent == [
        {
            "op": "replay",
            "channel": "l4_orders",
            "symbol": "BTC",
            "start": 1_757_000_000_000,
            "speed": 1.0,
            "end": 1_757_003_600_000,
        }
    ]


def test_l4_replay_frames_are_typed_and_batch_order_is_preserved() -> None:
    ws = OxArchiveWs(WsOptions(api_key="test-key"))
    messages: list[object] = []
    snapshots: list[dict[str, Any]] = []
    batches: list[list[dict[str, Any]]] = []
    ws.on_message(messages.append)
    ws.on_l4_snapshot(lambda _channel, _coin, message: snapshots.append(message))
    ws.on_l4_batch(lambda _channel, _coin, records: batches.append(records))

    ws._handle_message(
        json.dumps(
            {
                "type": "l4_snapshot",
                "channel": "l4_diffs",
                "coin": "BTC",
                "symbol": "BTC",
                "last_block_number": 100,
                "timestamp": 1_757_000_000_000,
                "data": {"bids": [], "asks": []},
            }
        )
    )
    ws._handle_message(
        json.dumps(
            {
                "type": "l4_batch",
                "channel": "l4_diffs",
                "coin": "BTC",
                "symbol": "BTC",
                "data": [
                    {"block_number": 101, "seq": 1, "side": "B"},
                    {"block_number": 101, "seq": 2, "side": "A"},
                ],
            }
        )
    )

    assert isinstance(messages[0], WsL4Snapshot)
    assert isinstance(messages[1], WsL4Batch)
    assert messages[0].symbol == "BTC"
    assert messages[1].data[0]["seq"] == 1
    assert messages[1].data[1]["seq"] == 2
    assert snapshots[0]["last_block_number"] == 100
    assert [record["seq"] for record in batches[0]] == [1, 2]
