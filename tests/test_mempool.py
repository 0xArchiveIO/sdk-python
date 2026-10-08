"""The ``mempool`` WebSocket channel: pending Hyperliquid transactions."""

from __future__ import annotations

import asyncio
import json
from typing import Any, Optional

import pytest
from _mock_api import envelope, mock_client
from test_websocket_capabilities import FakeSocket

from oxarchive import MempoolItem, MempoolSignature, WsMempoolData
from oxarchive.types import WsChannel, WsData, WsError, WsSubscribed, WsUnsubscribed
from oxarchive.websocket import (
    DEFAULT_WS_URL,
    LIVE_CHANNELS,
    REPLAY_CHANNELS,
    STREAM_WS_URL,
    WS_CHANNELS,
    OxArchiveWs,
    WsOptions,
)

T_START = 1791424000000

# Items shaped as the server sends them: an order on BTC, and a transfer that
# references no market.
ORDER_ITEM: dict[str, Any] = {
    "received_at": "2026-10-08T01:57:23.548737209Z",
    "received_at_ms": 1791424643548,
    "symbols": ["BTC"],
    "action": {
        "type": "order",
        "orders": [
            {
                "a": 0,
                "b": True,
                "p": "83276",
                "s": "0.40011",
                "r": False,
                "t": {"limit": {"tif": "Alo"}},
                "c": "0x7849acc2c6c2f6f0fe4bc80ef13d1504",
            }
        ],
        "grouping": "na",
    },
    "nonce": 1791424643400,
    "vault_address": None,
    "expires_after_ms": None,
    "signature": {"r": "0x5afc", "s": "0x57e2", "v": 28},
}

TRANSFER_ITEM: dict[str, Any] = {
    "received_at": "2026-10-08T01:57:23.548737209Z",
    "received_at_ms": 1791424643548,
    "symbols": [],
    "action": {
        "type": "usdSend",
        "signatureChainId": "0xa4b1",
        "hyperliquidChain": "Mainnet",
        "destination": "0x0000000000000000000000000000000000000001",
        "amount": "10",
        "time": 1791424643400,
    },
    "nonce": 1791424643400,
    "vault_address": None,
    "expires_after_ms": 1791424703400,
    "signature": {"r": "0x01", "s": "0x02", "v": 27},
}


def _mempool_frame(symbol: Optional[str], items: list[dict[str, Any]]) -> str:
    return json.dumps(
        {"type": "data", "channel": "mempool", "coin": symbol, "symbol": symbol, "data": items}
    )


def _connected_client() -> tuple[OxArchiveWs, FakeSocket]:
    ws = OxArchiveWs(WsOptions(api_key="test-key", ws_url=STREAM_WS_URL))
    socket = FakeSocket()
    setattr(ws, "_ws", socket)
    return ws, socket


def test_mempool_is_live_only_on_the_stream_endpoint_for_pro_and_above() -> None:
    spec = WS_CHANNELS["mempool"]

    assert (spec.venue, spec.datatype, spec.live, spec.replay) == (
        "hyperliquid",
        "mempool",
        True,
        False,
    )
    assert spec.bulk_replay is False
    assert spec.ws_endpoint == STREAM_WS_URL == "wss://stream.0xarchive.io/ws"
    assert spec.plans == ("pro", "scale", "enterprise")
    assert "mempool" in LIVE_CHANNELS and "mempool" not in REPLAY_CHANNELS
    assert DEFAULT_WS_URL == "wss://api.0xarchive.io/ws"
    assert OxArchiveWs(WsOptions(api_key="k")).options.ws_url == DEFAULT_WS_URL


def test_subscribe_without_a_symbol_is_the_unfiltered_stream() -> None:
    ws, socket = _connected_client()

    async def run() -> None:
        ws.subscribe_mempool()
        await asyncio.sleep(0)
        ws.unsubscribe_mempool()
        await asyncio.sleep(0)

    asyncio.run(run())

    assert socket.sent == [
        {"op": "subscribe", "channel": "mempool"},
        {"op": "unsubscribe", "channel": "mempool"},
    ]
    assert ws._subscriptions == set()


@pytest.mark.parametrize("symbol", ["BTC", "xyz:TSLA", "HYPE-USDC", "#49720"])
def test_subscribe_with_a_symbol_filters_by_market(symbol: str) -> None:
    ws, socket = _connected_client()

    async def run() -> None:
        ws.subscribe_mempool(symbol)
        await asyncio.sleep(0)

    asyncio.run(run())

    assert socket.sent == [{"op": "subscribe", "channel": "mempool", "symbol": symbol}]
    assert ws._subscriptions == {f"mempool:{symbol}"}


def test_unfiltered_and_symbol_subscriptions_are_kept_apart_and_resent_on_reconnect() -> None:
    ws, socket = _connected_client()

    async def run() -> None:
        await ws.subscribe_async("mempool")
        await ws.subscribe_async("mempool", "xyz:TSLA")
        socket.sent.clear()
        await ws._resubscribe()

    asyncio.run(run())

    assert ws._subscriptions == {"mempool", "mempool:xyz:TSLA"}
    assert sorted(socket.sent, key=lambda m: m.get("symbol", "")) == [
        {"op": "subscribe", "channel": "mempool"},
        {"op": "subscribe", "channel": "mempool", "symbol": "xyz:TSLA"},
    ]

    asyncio.run(ws.unsubscribe_async("mempool", "xyz:TSLA"))
    assert ws._subscriptions == {"mempool"}
    assert socket.sent[-1] == {"op": "unsubscribe", "channel": "mempool", "symbol": "xyz:TSLA"}


def test_mempool_does_not_replay() -> None:
    ws, socket = _connected_client()

    with pytest.raises(ValueError, match="does not support historical replay"):
        asyncio.run(ws.replay("mempool", "BTC", start=T_START))
    with pytest.raises(ValueError, match="does not support historical replay"):
        asyncio.run(ws.multi_replay(["trades", "mempool"], "BTC", start=T_START))

    assert socket.sent == []


def test_subscribe_ack_without_a_symbol_is_typed() -> None:
    ws = OxArchiveWs(WsOptions(api_key="test-key"))
    messages: list[object] = []
    ws.on_message(messages.append)

    ws._handle_message(
        json.dumps({"type": "subscribed", "channel": "mempool", "coin": None, "symbol": None})
    )
    ws._handle_message(
        json.dumps({"type": "unsubscribed", "channel": "mempool", "coin": "BTC", "symbol": "BTC"})
    )

    ack, nack = messages
    assert isinstance(ack, WsSubscribed)
    assert (ack.channel, ack.coin, ack.symbol) == ("mempool", None, None)
    assert isinstance(nack, WsUnsubscribed)
    assert (nack.channel, nack.symbol) == ("mempool", "BTC")


def test_unfiltered_frame_decodes_to_items() -> None:
    ws = OxArchiveWs(WsOptions(api_key="test-key"))
    received: list[tuple[Optional[str], list[MempoolItem]]] = []
    messages: list[object] = []
    ws.on_mempool(lambda symbol, items: received.append((symbol, items)))
    ws.on_message(messages.append)

    ws._handle_message(_mempool_frame(None, [ORDER_ITEM, TRANSFER_ITEM]))

    ((symbol, items),) = received
    assert symbol is None
    order, transfer = items
    assert isinstance(order, MempoolItem)
    assert order.received_at == "2026-10-08T01:57:23.548737209Z"
    assert order.received_at_ms == 1791424643548
    assert order.symbols == ["BTC"]
    assert order.action == ORDER_ITEM["action"]
    assert list(order.action) == ["type", "orders", "grouping"]
    assert list(order.action["orders"][0]) == ["a", "b", "p", "s", "r", "t", "c"]
    assert order.nonce == 1791424643400
    assert order.vault_address is None and order.expires_after_ms is None
    assert order.signature == MempoolSignature(r="0x5afc", s="0x57e2", v=28)
    assert transfer.symbols == []
    assert transfer.action["type"] == "usdSend"
    assert transfer.expires_after_ms == 1791424703400

    (message,) = messages
    assert isinstance(message, WsMempoolData)
    assert not isinstance(message, WsData)
    assert (message.channel, message.coin, message.symbol) == ("mempool", None, None)
    assert message.data == items


def test_symbol_frame_carries_the_subscription_symbol() -> None:
    ws = OxArchiveWs(WsOptions(api_key="test-key"))
    received: list[tuple[Optional[str], list[MempoolItem]]] = []
    ws.on_mempool(lambda symbol, items: received.append((symbol, items)))

    ws._handle_message(_mempool_frame("BTC", [ORDER_ITEM]))

    ((symbol, items),) = received
    assert symbol == "BTC"
    assert items[0].symbols == ["BTC"]


def test_mempool_frames_never_reach_the_trade_or_book_handlers() -> None:
    ws = OxArchiveWs(WsOptions(api_key="test-key"))
    other: list[object] = []
    ws.on_trades(lambda coin, trades: other.append(trades))
    ws.on_orderbook(lambda coin, book: other.append(book))

    ws._handle_message(_mempool_frame("BTC", [ORDER_ITEM]))

    assert other == []


def test_item_tolerates_nulls_and_new_fields() -> None:
    item = MempoolItem.model_validate(
        {
            "received_at": None,
            "received_at_ms": None,
            "symbols": [],
            "action": {"type": "someFutureAction", "x": 1},
            "nonce": None,
            "vault_address": "0x00000000000000000000000000000000000000aa",
            "expires_after_ms": None,
            "signature": None,
            "new_field": "kept",
        }
    )

    assert item.received_at is None and item.nonce is None and item.signature is None
    assert item.action["type"] == "someFutureAction"
    assert item.vault_address == "0x00000000000000000000000000000000000000aa"
    assert item.model_extra == {"new_field": "kept"}


@pytest.mark.parametrize(
    "frame",
    [
        {
            "type": "error",
            "message": "The mempool channel is included with the Pro, Scale and Enterprise "
            "plans. Upgrade at https://0xarchive.io/pricing.",
            "error_code": "forbidden",
        },
        {
            "type": "error",
            "message": "The 'mempool' channel is live only and served on "
            "wss://stream.0xarchive.io/ws. Subscribe to it there.",
            "error_code": "endpoint_unsupported",
        },
        {
            "type": "error",
            "message": "The unfiltered mempool stream is at capacity. Subscribe with a "
            "symbol, or try again later.",
            "error_code": "rate_limited",
        },
        {
            "type": "error",
            "message": "The mempool channel is temporarily unavailable. Please try again "
            "shortly.",
            "error_code": "upstream_unavailable",
        },
        {"type": "error", "message": "Unknown symbol 'NOPE'.", "error_code": "invalid_symbol"},
    ],
)
def test_mempool_refusals_reach_on_message_with_their_error_code(frame: dict[str, Any]) -> None:
    ws = OxArchiveWs(WsOptions(api_key="test-key"))
    messages: list[object] = []
    ws.on_message(messages.append)

    ws._handle_message(json.dumps(frame))

    (error,) = messages
    assert isinstance(error, WsError)
    assert (error.error_code, error.message) == (frame["error_code"], frame["message"])


def test_capabilities_parse_the_endpoint_and_plans_of_the_mempool_row() -> None:
    rows = [
        {
            "venue": "hyperliquid",
            "datatype": "mempool",
            "rest_routes": [],
            "ws_channels": ["mempool"],
            "live": True,
            "replay": False,
            "available_from": None,
            "cadence": "event",
            "page_limit": None,
            "intervals": [],
            "notes": "Live only, on wss://stream.0xarchive.io/ws.",
            "ws_endpoint": "wss://stream.0xarchive.io/ws",
            "plans": ["pro", "scale", "enterprise"],
        },
        {
            "venue": "hyperliquid",
            "datatype": "trades",
            "rest_routes": ["/v1/hyperliquid/trades/{symbol}"],
            "ws_channels": ["trades"],
            "live": True,
            "replay": True,
            "available_from": None,
            "cadence": "event",
            "page_limit": 1000,
            "intervals": [],
            "notes": None,
        },
    ]
    client, _ = mock_client(lambda p, q: envelope(rows))

    mempool, trades = client.capabilities()

    assert mempool.ws_endpoint == "wss://stream.0xarchive.io/ws"
    assert mempool.plans == ["pro", "scale", "enterprise"]
    assert trades.ws_endpoint is None and trades.plans is None
    spec = WS_CHANNELS[mempool.ws_channels[0]]
    assert (spec.ws_endpoint, list(spec.plans or ())) == (mempool.ws_endpoint, mempool.plans)


def test_mempool_is_a_typed_channel_name() -> None:
    channel: WsChannel = "mempool"
    assert WsSubscribed(type="subscribed", channel=channel).channel == "mempool"
