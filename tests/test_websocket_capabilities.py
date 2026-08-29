import asyncio
import json
import re

import pytest

from oxarchive.types import WsL4Batch, WsL4Snapshot
from oxarchive.websocket import (
    LIGHTER_REPLAY_CHANNELS,
    LIGHTER_SUBSCRIPTION_ERROR,
    OxArchiveWs,
    WsOptions,
)


@pytest.mark.parametrize("channel", sorted(LIGHTER_REPLAY_CHANNELS))
def test_lighter_channels_reject_live_subscription_before_state_change(channel: str) -> None:
    ws = OxArchiveWs(WsOptions(api_key="test-key"))

    with pytest.raises(ValueError, match=re.escape(LIGHTER_SUBSCRIPTION_ERROR)):
        ws.subscribe(channel, "BTC")

    assert ws._subscriptions == set()


@pytest.mark.parametrize("channel", sorted(LIGHTER_REPLAY_CHANNELS))
def test_lighter_channels_reject_async_live_subscription_before_state_change(channel: str) -> None:
    ws = OxArchiveWs(WsOptions(api_key="test-key"))

    async def run() -> None:
        with pytest.raises(ValueError, match=re.escape(LIGHTER_SUBSCRIPTION_ERROR)):
            await ws.subscribe_async(channel, "BTC")

    asyncio.run(run())
    assert ws._subscriptions == set()


def test_lighter_channels_are_allowed_for_bounded_replay() -> None:
    ws = OxArchiveWs(WsOptions(api_key="test-key"))
    sent: list[dict] = []

    async def fake_send(message: dict) -> None:
        sent.append(message)

    ws._send = fake_send  # type: ignore[method-assign]

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
    ws = OxArchiveWs(WsOptions(api_key="test-key"))
    sent: list[dict] = []

    async def fake_send(message: dict) -> None:
        sent.append(message)

    ws._send = fake_send  # type: ignore[method-assign]

    with pytest.raises(ValueError, match="live subscriptions only"):
        asyncio.run(ws.replay(channel, "BTC", start=1_757_000_000_000))

    assert sent == []


@pytest.mark.parametrize("channel", ["hip3_l4_diffs", "hip4_l4_orders", "spot_l4_diffs"])
def test_non_core_l4_channels_remain_live_only_for_multi_replay(channel: str) -> None:
    ws = OxArchiveWs(WsOptions(api_key="test-key"))
    sent: list[dict] = []

    async def fake_send(message: dict) -> None:
        sent.append(message)

    ws._send = fake_send  # type: ignore[method-assign]

    with pytest.raises(ValueError, match="live subscriptions only"):
        asyncio.run(ws.multi_replay(["orderbook", channel], "BTC", start=1_757_000_000_000))

    assert sent == []


def test_core_l4_replay_command_remains_allowed() -> None:
    ws = OxArchiveWs(WsOptions(api_key="test-key"))
    sent: list[dict] = []

    async def fake_send(message: dict) -> None:
        sent.append(message)

    ws._send = fake_send  # type: ignore[method-assign]

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
    snapshots: list[dict] = []
    batches: list[list[dict]] = []
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
