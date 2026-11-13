"""Times that describe market data can be null when the time of the data is unknown.

Covers ``CoinSummary.timestamp``, ``TriggerLevels.as_of`` and ``as_of_block``,
and ``WsL4Snapshot.timestamp``. Each accepts a value, ``null`` and a missing
field, so responses with or without these fields parse.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Callable

import pytest
from _mock_api import envelope, mock_client

from oxarchive import Client
from oxarchive.types import CoinSummary, TriggerLevels, WsL4Snapshot
from oxarchive.websocket import OxArchiveWs, WsOptions

SUMMARY: dict[str, Any] = {
    "coin": "BTC",
    "timestamp": "2026-11-13T22:21:00Z",
    "mark_price": "98123.5",
    "oracle_price": "98120.0",
    "funding_rate": "0.0000125",
    "open_interest": "31234.5",
}

TRIGGER_LEVELS: dict[str, Any] = {
    "mid_price": 98123.5,
    "as_of": "2026-11-13T22:21:05.695Z",
    "as_of_block": 1220113000,
    "total_bid_size": 1.5,
    "total_ask_size": 4.0,
    "levels": [
        {"price_bucket": 97000.0, "bid_count": 1, "bid_size": 1.5, "ask_count": 0, "ask_size": 0.0},
        {"price_bucket": 99000.0, "bid_count": 0, "bid_size": 0.0, "ask_count": 2, "ask_size": 4.0},
    ],
}

L4_SNAPSHOT: dict[str, Any] = {
    "type": "l4_snapshot",
    "channel": "l4_diffs",
    "coin": "BTC",
    "symbol": "BTC",
    "last_block_number": 1220113000,
    "timestamp": 1794608465695,
    "data": {"bids": [], "asks": []},
}


def _without(record: dict[str, Any], *keys: str) -> dict[str, Any]:
    return {k: v for k, v in record.items() if k not in keys}


def _with(record: dict[str, Any], **values: Any) -> dict[str, Any]:
    return {**record, **values}


# ---------------------------------------------------------------------------
# Market summary
# ---------------------------------------------------------------------------

SummaryCall = Callable[[Client], CoinSummary]

SUMMARY_ROUTES: list[tuple[str, SummaryCall, str]] = [
    ("hyperliquid", lambda c: c.hyperliquid.get_summary("BTC"), "/v1/hyperliquid/summary/BTC"),
    (
        "hip3",
        lambda c: c.hyperliquid.hip3.get_summary("xyz:TSLA"),
        "/v1/hyperliquid/hip3/summary/xyz:TSLA",
    ),
    ("hip4", lambda c: c.hyperliquid.hip4.get_summary("0"), "/v1/hyperliquid/hip4/summary/0"),
    ("lighter", lambda c: c.lighter.get_summary("BTC"), "/v1/lighter/summary/BTC"),
    ("rh_lighter", lambda c: c.rh_lighter.get_summary("BTC"), "/v1/rh-lighter/summary/BTC"),
]


@pytest.mark.parametrize(
    "body, expected",
    [
        (SUMMARY, datetime(2026, 11, 13, 22, 21, tzinfo=timezone.utc)),
        (_with(SUMMARY, timestamp=None), None),
        (_without(SUMMARY, "timestamp"), None),
    ],
    ids=["value", "null", "missing"],
)
@pytest.mark.parametrize("venue, call, path", SUMMARY_ROUTES, ids=[r[0] for r in SUMMARY_ROUTES])
def test_summary_timestamp_is_optional(
    venue: str, call: SummaryCall, path: str, body: dict[str, Any], expected: Any
) -> None:
    client, api = mock_client(lambda _path, _query: envelope(body))
    summary = call(client)
    assert isinstance(summary, CoinSummary)
    assert summary.timestamp == expected
    assert summary.mark_price == "98123.5"
    assert api.calls[0][0] == path


# ---------------------------------------------------------------------------
# Trigger levels
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "body, as_of, as_of_block",
    [
        (TRIGGER_LEVELS, "2026-11-13T22:21:05.695Z", 1220113000),
        (_with(TRIGGER_LEVELS, as_of=None, as_of_block=None), None, None),
        (_without(TRIGGER_LEVELS, "as_of", "as_of_block"), None, None),
        # An answer that predates as_of_block: a whole-second as_of and no block.
        (
            _without(_with(TRIGGER_LEVELS, as_of="2026-11-13T22:21:05Z"), "as_of_block"),
            "2026-11-13T22:21:05Z",
            None,
        ),
    ],
    ids=["value", "null", "missing", "without-block"],
)
@pytest.mark.parametrize("product", ["hyperliquid", "hip3"])
def test_trigger_levels_as_of_is_optional(
    product: str, body: dict[str, Any], as_of: Any, as_of_block: Any
) -> None:
    client, api = mock_client(lambda _path, _query: envelope(body))
    if product == "hyperliquid":
        levels = client.hyperliquid.orders.trigger_levels("BTC")
        path = "/v1/hyperliquid/orders/BTC/trigger-levels"
    else:
        levels = client.hyperliquid.hip3.orders.trigger_levels("xyz:TSLA")
        path = "/v1/hyperliquid/hip3/orders/xyz:TSLA/trigger-levels"
    assert isinstance(levels, TriggerLevels)
    assert levels.as_of == as_of
    assert levels.as_of_block == as_of_block
    assert levels.mid_price == 98123.5
    assert [b.price_bucket for b in levels.levels] == [97000.0, 99000.0]
    assert api.calls[0][0] == path


async def test_async_trigger_levels_accept_null_as_of() -> None:
    body = _with(TRIGGER_LEVELS, as_of=None, as_of_block=None)
    client, _ = mock_client(lambda _path, _query: envelope(body))
    levels = await client.hyperliquid.orders.atrigger_levels("BTC")
    assert levels.as_of is None and levels.as_of_block is None


# ---------------------------------------------------------------------------
# WebSocket l4_snapshot
# ---------------------------------------------------------------------------

L4_SNAPSHOT_CHANNELS = [
    "l4_diffs",
    "hip3_l4_diffs",
    "spot_l4_diffs",
    "hip4_l4_diffs",
    "orderbook_full",
    "hip3_orderbook_full",
]


@pytest.mark.parametrize(
    "timestamp, present",
    [(1794608465695, True), (None, True), (None, False)],
    ids=["value", "null", "missing"],
)
@pytest.mark.parametrize("channel", L4_SNAPSHOT_CHANNELS)
def test_l4_snapshot_timestamp_is_optional_and_reaches_the_handlers(
    channel: str, timestamp: Any, present: bool
) -> None:
    frame = _with(L4_SNAPSHOT, channel=channel, timestamp=timestamp)
    if not present:
        frame = _without(frame, "timestamp")

    ws = OxArchiveWs(WsOptions(api_key="test-key"))
    messages: list[object] = []
    snapshots: list[tuple[str, str, dict[str, Any]]] = []
    ws.on_message(messages.append)
    ws.on_l4_snapshot(lambda ch, coin, message: snapshots.append((ch, coin, message)))

    # A frame that fails validation is logged and dropped, so both handlers
    # receiving it is the proof that it parsed.
    ws._handle_message(json.dumps(frame))

    assert len(messages) == 1
    snapshot = messages[0]
    assert isinstance(snapshot, WsL4Snapshot)
    assert snapshot.channel == channel
    assert snapshot.timestamp == timestamp
    assert snapshot.last_block_number == 1220113000
    assert snapshots == [(channel, "BTC", frame)]


def test_models_accept_null_and_missing_times_directly() -> None:
    assert CoinSummary.model_validate(_with(SUMMARY, timestamp=None)).timestamp is None
    assert CoinSummary.model_validate(_without(SUMMARY, "timestamp")).timestamp is None
    assert TriggerLevels.model_validate(_with(TRIGGER_LEVELS, as_of=None)).as_of is None
    assert TriggerLevels.model_validate(_without(TRIGGER_LEVELS, "as_of_block")).as_of_block is None
    assert WsL4Snapshot.model_validate(_with(L4_SNAPSHOT, timestamp=None)).timestamp is None
    assert WsL4Snapshot.model_validate(_without(L4_SNAPSHOT, "timestamp")).timestamp is None
