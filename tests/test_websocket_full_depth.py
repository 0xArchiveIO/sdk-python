"""Full-depth L2 WebSocket channels: ``orderbook_full`` and ``hip3_orderbook_full``.

The frames below were captured from the production WebSocket (books truncated
to two levels per side).
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, cast, get_args

import pytest
from websockets.protocol import State as WsState

from oxarchive.types import WsChannel, WsL4Batch, WsL4Snapshot, WsSubscribed
from oxarchive.websocket import (
    FULL_DEPTH_L2_CHANNELS,
    FULL_DEPTH_LIVE_ONLY_ERROR,
    OxArchiveWs,
    WsOptions,
)

SUBSCRIBED: dict[str, Any] = {
    "type": "subscribed",
    "channel": "orderbook_full",
    "coin": "BTC",
    "symbol": "BTC",
}

SNAPSHOT: dict[str, Any] = {
    "type": "l4_snapshot",
    "channel": "orderbook_full",
    "coin": "BTC",
    "symbol": "BTC",
    "last_block_number": 1164900082,
    "timestamp": 1790649779818,
    "data": {
        "bids": [{"n": 31, "px": 82922.0, "sz": 9.1}, {"n": 4, "px": 82921.0, "sz": 0.52}],
        "asks": [{"n": 104, "px": 82923.0, "sz": 18.14181}, {"n": 23, "px": 82924.0, "sz": 2.91}],
        "bid_count": 7021,
        "ask_count": 6929,
        "total_bid_size": 1812.4,
        "total_ask_size": 1633.9,
        "mid_price": 82922.5,
        "spread": 1.0,
        "spread_bps": 0.12,
        "is_crossed": False,
    },
}

BATCH: dict[str, Any] = {
    "type": "l4_batch",
    "channel": "hip3_orderbook_full",
    "coin": "xyz:XYZ100",
    "symbol": "xyz:XYZ100",
    "data": [
        {"bn": 1164900660, "n": 6, "px": 30202.0, "side": "A", "sz": 2.0656},
        {"bn": 1164900660, "n": 0, "px": 30204.0, "side": "A", "sz": 0.0},
        {"bn": 1164900660, "n": 2, "px": 30041.0, "side": "B", "sz": 0.7954},
    ],
}


class FakeSocket:
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


def test_both_full_depth_channels_are_ws_channels() -> None:
    channels = set(get_args(WsChannel))

    assert {"orderbook_full", "hip3_orderbook_full"} <= channels
    assert FULL_DEPTH_L2_CHANNELS == {"orderbook_full", "hip3_orderbook_full"}


@pytest.mark.parametrize("channel", sorted(FULL_DEPTH_L2_CHANNELS))
def test_full_depth_channels_subscribe_live(channel: str) -> None:
    channel = cast(WsChannel, channel)
    ws, socket = _connected_client()

    asyncio.run(ws.subscribe_async(channel, "BTC"))

    assert ws._subscriptions == {f"{channel}:BTC"}
    assert socket.sent == [{"op": "subscribe", "channel": channel, "symbol": "BTC"}]


def test_full_depth_helpers_send_subscribe_and_unsubscribe() -> None:
    ws, socket = _connected_client()

    async def run() -> None:
        ws.subscribe_orderbook_full("BTC")
        ws.subscribe_hip3_orderbook_full("xyz:XYZ100")
        await asyncio.sleep(0)
        ws.unsubscribe_orderbook_full("BTC")
        await asyncio.sleep(0)

    asyncio.run(run())

    assert socket.sent == [
        {"op": "subscribe", "channel": "orderbook_full", "symbol": "BTC"},
        {"op": "subscribe", "channel": "hip3_orderbook_full", "symbol": "xyz:XYZ100"},
        {"op": "unsubscribe", "channel": "orderbook_full", "symbol": "BTC"},
    ]
    assert ws._subscriptions == {"hip3_orderbook_full:xyz:XYZ100"}


def test_hip3_full_depth_unsubscribe_helper() -> None:
    ws, socket = _connected_client()

    async def run() -> None:
        ws.subscribe_hip3_orderbook_full("km:US500")
        ws.unsubscribe_hip3_orderbook_full("km:US500")
        await asyncio.sleep(0)

    asyncio.run(run())

    assert socket.sent[-1] == {
        "op": "unsubscribe",
        "channel": "hip3_orderbook_full",
        "symbol": "km:US500",
    }
    assert ws._subscriptions == set()


def test_full_depth_frames_are_typed_and_reach_the_l4_handlers() -> None:
    ws = OxArchiveWs(WsOptions(api_key="test-key"))
    messages: list[object] = []
    snapshots: list[tuple[str, str, dict[str, Any]]] = []
    batches: list[tuple[str, str, list[dict[str, Any]]]] = []
    ws.on_message(messages.append)
    ws.on_l4_snapshot(lambda channel, coin, message: snapshots.append((channel, coin, message)))
    ws.on_l4_batch(lambda channel, coin, records: batches.append((channel, coin, records)))

    for frame in (SUBSCRIBED, SNAPSHOT, BATCH):
        ws._handle_message(json.dumps(frame))

    ack, snapshot, batch = messages
    assert isinstance(ack, WsSubscribed) and ack.channel == "orderbook_full"
    assert isinstance(snapshot, WsL4Snapshot) and snapshot.channel == "orderbook_full"
    assert snapshot.last_block_number == 1164900082
    assert snapshot.data["ask_count"] == 6929
    assert isinstance(batch, WsL4Batch) and batch.channel == "hip3_orderbook_full"
    assert snapshots[0][0:2] == ("orderbook_full", "BTC")
    assert snapshots[0][2]["data"]["bids"][0] == {"n": 31, "px": 82922.0, "sz": 9.1}
    channel, coin, records = batches[0]
    assert (channel, coin) == ("hip3_orderbook_full", "xyz:XYZ100")
    assert [r["px"] for r in records] == [30202.0, 30204.0, 30041.0]
    assert records[1]["sz"] == 0.0  # a removed level


def _offline_client() -> tuple[OxArchiveWs, list[dict[str, Any]]]:
    ws = OxArchiveWs(WsOptions(api_key="test-key"))
    sent: list[dict[str, Any]] = []

    async def fake_send(message: dict[str, Any]) -> None:
        sent.append(message)

    setattr(ws, "_send", fake_send)
    return ws, sent


@pytest.mark.parametrize("channel", sorted(FULL_DEPTH_L2_CHANNELS))
def test_full_depth_channels_are_live_only_for_replay(channel: str) -> None:
    channel = cast(WsChannel, channel)
    ws, sent = _offline_client()

    with pytest.raises(ValueError) as caught:
        asyncio.run(ws.replay(channel, "BTC", start=1_757_000_000_000, speed=10))

    assert str(caught.value) == FULL_DEPTH_LIVE_ONLY_ERROR
    assert "l2_orderbook.history()" in FULL_DEPTH_LIVE_ONLY_ERROR
    assert sent == []


@pytest.mark.parametrize("channel", sorted(FULL_DEPTH_L2_CHANNELS))
def test_full_depth_channels_are_live_only_for_multi_replay(channel: str) -> None:
    channel = cast(WsChannel, channel)
    ws, sent = _offline_client()

    with pytest.raises(ValueError, match="live subscriptions only"):
        asyncio.run(ws.multi_replay(["orderbook", channel], "BTC", start=1_757_000_000_000))

    assert sent == []


def test_the_top_of_book_orderbook_still_replays() -> None:
    ws, sent = _offline_client()

    asyncio.run(ws.replay("orderbook", "BTC", start=1_757_000_000_000, speed=10))

    assert sent == [
        {
            "op": "replay",
            "channel": "orderbook",
            "symbol": "BTC",
            "start": 1_757_000_000_000,
            "speed": 10,
        }
    ]
