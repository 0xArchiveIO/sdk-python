"""Existing methods fixed against the live response shapes.

A trades cursor is an opaque string and goes back to the API unchanged, and
HIP-4 freshness has no funding entry.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

import pytest
from _mock_api import envelope, mock_client

T_START = 1790640000000  # 2026-09-29T00:00:00Z
T_END = 1790726400000  # 2026-09-30T00:00:00Z


TRADE: dict[str, Any] = {
    "coin": "BTC",
    "side": "B",
    "price": "82923.0",
    "size": "0.01",
    "timestamp": "2026-09-29T00:00:00.578Z",
    "trade_id": 218303497631402,
}


@pytest.mark.parametrize(
    "venue, path, cursor",
    [
        ("hyperliquid", "/v1/hyperliquid/trades/BTC", "1790640000578_218303497631402"),
        ("lighter", "/v1/lighter/trades/BTC", "1790540000288_32247366750_1"),
    ],
)
def test_trades_cursor_is_passed_back_unchanged(venue: str, path: str, cursor: str) -> None:
    client, api = mock_client(lambda p, q: envelope([TRADE], next_cursor=cursor))
    trades = getattr(client, venue).trades

    first = trades.list("BTC", start=T_START, end=T_END, limit=1)
    trades.list("BTC", start=T_START, end=T_END, limit=1, cursor=first.next_cursor)
    asyncio.run(trades.alist("BTC", start=T_START, end=T_END, limit=1, cursor=first.next_cursor))

    base = {"start": str(T_START), "end": str(T_END), "limit": "1"}
    assert first.next_cursor == cursor
    assert api.calls == [(path, base), (path, {**base, "cursor": cursor})] + [
        (path, {**base, "cursor": cursor})
    ]


def test_trades_cursor_still_accepts_milliseconds_and_datetimes() -> None:
    client, api = mock_client(lambda p, q: envelope([]))

    client.hyperliquid.trades.list("BTC", start=T_START, end=T_END, cursor=T_START)
    client.hyperliquid.trades.list(
        "BTC", start=T_START, end=T_END, cursor=datetime(2026, 9, 29, tzinfo=timezone.utc)
    )

    assert [q["cursor"] for _, q in api.calls] == [str(T_START), str(T_START)]


def test_hip4_freshness_parses_without_funding() -> None:
    client, api = mock_client(
        lambda p, q: envelope(
            {
                "coin": "#0",
                "symbol": "#0",
                "exchange": "hip4",
                "measured_at": "2026-09-29T02:53:20.018625249Z",
                "orderbook": {},
                "trades": {},
                "open_interest": {},
            }
        )
    )

    freshness = client.hyperliquid.hip4.get_freshness("#0")

    assert api.calls == [("/v1/hyperliquid/hip4/freshness/0", {})]
    assert freshness.funding is None and freshness.exchange == "hip4"
