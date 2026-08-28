import asyncio
import re

import pytest

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
