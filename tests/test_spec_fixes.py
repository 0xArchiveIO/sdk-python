"""Existing methods reconciled with the routes and shapes the API serves.

A trades cursor is an opaque string and goes back to the API unchanged; HIP-4
freshness has no funding entry; methods for routes the API does not serve are
gone; parameters it never applied are refused; symbol coverage encodes the
symbol; spot freshness parses its datasets; L3 takes account.
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


# ---------------------------------------------------------------------------
# Methods whose routes the API does not serve are gone
# ---------------------------------------------------------------------------


def test_methods_for_unserved_routes_are_removed() -> None:
    client, _ = mock_client(lambda p, q: envelope([]))
    hl, hip3, hip4, spot = (
        client.hyperliquid,
        client.hyperliquid.hip3,
        client.hyperliquid.hip4,
        client.spot,
    )

    assert not hasattr(hip4, "l2_orderbook")
    for name in ("trigger_levels", "trigger_levels_history"):
        assert not hasattr(hip4.orders, name) and not hasattr(hip4.orders, "a" + name)
    for name in ("flow", "tpsl", "trigger_levels", "trigger_levels_history"):
        assert not hasattr(spot.orders, name) and not hasattr(spot.orders, "a" + name)
    assert not hasattr(hip3.liquidations, "by_user")
    assert not hasattr(hip3.liquidations, "aby_user")

    # The routes the API does serve keep their methods.
    assert hasattr(hl, "l2_orderbook") and hasattr(hip3, "l2_orderbook")
    assert hasattr(hl.orders, "trigger_levels") and hasattr(hip3.orders, "trigger_levels")
    assert hasattr(hip4.orders, "flow") and hasattr(hip4.orders, "tpsl")
    assert hasattr(spot.orders, "history") and hasattr(spot.orders, "ahistory")
    assert hasattr(hl.liquidations, "by_user") and hasattr(hip3.liquidations, "volume")


def test_hip4_flow_and_tpsl_still_reach_their_routes() -> None:
    client, api = mock_client(lambda p, q: envelope([]))

    client.hyperliquid.hip4.orders.flow("#0", start=T_START, end=T_END)
    client.hyperliquid.hip4.orders.tpsl("#0", start=T_START, end=T_END)
    asyncio.run(client.hyperliquid.hip4.orders.ahistory("#0", start=T_START, end=T_END))

    assert [path for path, _ in api.calls] == [
        "/v1/hyperliquid/hip4/orders/0/flow",
        "/v1/hyperliquid/hip4/orders/0/tpsl",
        "/v1/hyperliquid/hip4/orders/0/history",
    ]


# ---------------------------------------------------------------------------
# Parameters the API never applied are refused before sending
# ---------------------------------------------------------------------------


def test_trades_side_is_refused_before_sending() -> None:
    client, api = mock_client(lambda p, q: envelope([]))

    with pytest.raises(TypeError, match="does not take 'side'.*Trade.side"):
        client.hyperliquid.trades.list("BTC", start=T_START, end=T_END, side="buy")
    with pytest.raises(TypeError, match="does not take 'side'"):
        asyncio.run(client.lighter.trades.alist("BTC", start=T_START, end=T_END, side="sell"))

    assert api.requests == []


@pytest.mark.parametrize("name", ["user", "status", "order_type"])
def test_spot_order_history_filters_are_refused_before_sending(name: str) -> None:
    client, api = mock_client(lambda p, q: envelope([]))

    with pytest.raises(TypeError, match=f"does not take '{name}'"):
        client.spot.orders.history("HYPE-USDC", start=T_START, end=T_END, **{name: "x"})
    with pytest.raises(TypeError, match=f"does not take '{name}'"):
        asyncio.run(
            client.spot.orders.ahistory("HYPE-USDC", start=T_START, end=T_END, **{name: "x"})
        )

    assert api.requests == []


def test_spot_order_history_sends_only_the_window_and_paging() -> None:
    client, api = mock_client(lambda p, q: envelope([], next_cursor="c2"))

    page = client.spot.orders.history("HYPE-USDC", start=T_START, end=T_END, cursor="c1", limit=5)

    assert api.calls == [
        (
            "/v1/hyperliquid/spot/orders/HYPE-USDC/history",
            {"start": str(T_START), "end": str(T_END), "cursor": "c1", "limit": "5"},
        )
    ]
    assert page.next_cursor == "c2"


def test_core_order_history_keeps_its_filters() -> None:
    client, api = mock_client(lambda p, q: envelope([]))

    client.hyperliquid.orders.history(
        "BTC", start=T_START, end=T_END, user="0xabc", status="filled", order_type="limit"
    )

    assert api.calls[0][1] == {
        "start": str(T_START),
        "end": str(T_END),
        "user": "0xabc",
        "status": "filled",
        "order_type": "limit",
    }


@pytest.mark.parametrize(
    "resource",
    [
        lambda c: c.hyperliquid.l2_orderbook,
        lambda c: c.hyperliquid.hip3.l2_orderbook,
        lambda c: c.hyperliquid.l4_orderbook,
        lambda c: c.spot.l4_orderbook,
        lambda c: c.lighter.l3_orderbook,
    ],
    ids=["l2", "hip3-l2", "l4", "spot-l4", "l3"],
)
def test_depth_on_history_is_refused_before_sending(resource: Any) -> None:
    client, api = mock_client(lambda p, q: envelope([]))
    book = resource(client)

    with pytest.raises(TypeError, match="does not take 'depth'.*get\\(\\) only"):
        book.history("BTC", start=T_START, end=T_END, depth=20)
    with pytest.raises(TypeError, match="does not take 'depth'"):
        asyncio.run(book.ahistory("BTC", start=T_START, end=T_END, depth=20))

    assert api.requests == []


def test_depth_still_applies_to_get() -> None:
    client, api = mock_client(lambda p, q: envelope({"bids": [], "asks": []}))

    client.hyperliquid.l2_orderbook.get("BTC", depth=10)
    client.hyperliquid.l4_orderbook.get("BTC", depth=10)

    assert [q for _, q in api.calls] == [{"depth": "10"}, {"depth": "10"}]


# ---------------------------------------------------------------------------
# L3 account
# ---------------------------------------------------------------------------


def test_l3_get_sends_account() -> None:
    client, api = mock_client(lambda p, q: envelope({"orders": []}))

    client.lighter.l3_orderbook.get("btc", depth=20, account=702384)
    asyncio.run(client.lighter.l3_orderbook.aget("BTC", account=702384))

    assert api.calls == [
        ("/v1/lighter/l3orderbook/BTC", {"depth": "20", "account": "702384"}),
        ("/v1/lighter/l3orderbook/BTC", {"account": "702384"}),
    ]


def test_l3_history_sends_account() -> None:
    client, api = mock_client(lambda p, q: envelope([], next_cursor="1790640373586"))

    page = client.lighter.l3_orderbook.history(
        "BTC", start=T_START, end=T_END, limit=2, account=702384
    )
    asyncio.run(client.lighter.l3_orderbook.ahistory("BTC", start=T_START, end=T_END))

    base = {"start": str(T_START), "end": str(T_END)}
    assert api.calls == [
        ("/v1/lighter/l3orderbook/BTC/history", {**base, "limit": "2", "account": "702384"}),
        ("/v1/lighter/l3orderbook/BTC/history", base),
    ]
    assert page.next_cursor == "1790640373586"


# ---------------------------------------------------------------------------
# Symbol coverage and spot freshness
# ---------------------------------------------------------------------------

COVERAGE: dict[str, Any] = {
    "exchange": "hip3",
    "symbol": "km:US500",
    "data_types": {},
}


@pytest.mark.parametrize(
    "exchange, symbol, raw_path",
    [
        ("hip3", "km:US500", "/v1/data-quality/coverage/hip3/km%3AUS500"),
        ("spot", "HYPE-USDC", "/v1/data-quality/coverage/spot/HYPE-USDC"),
        ("hip4", "#0", "/v1/data-quality/coverage/hip4/%230"),
        ("rh-lighter", "AAPL-USDG", "/v1/data-quality/coverage/rh-lighter/AAPL-USDG"),
        ("Hyperliquid", "BTC", "/v1/data-quality/coverage/hyperliquid/BTC"),
    ],
)
def test_symbol_coverage_sends_the_symbol_as_one_encoded_segment(
    exchange: str, symbol: str, raw_path: str
) -> None:
    client, api = mock_client(lambda p, q: {**COVERAGE, "symbol": symbol})

    result = client.data_quality.symbol_coverage(exchange, symbol)
    asyncio.run(client.data_quality.asymbol_coverage(exchange, symbol))

    assert api.raw_paths == [raw_path, raw_path]
    assert result.symbol == symbol


def test_symbol_coverage_keeps_the_symbol_case() -> None:
    client, api = mock_client(lambda p, q: COVERAGE)

    client.data_quality.symbol_coverage("hip3", "xyz:XYZ100")

    assert api.calls[0][0] == "/v1/data-quality/coverage/hip3/xyz:XYZ100"


SPOT_FRESHNESS: dict[str, Any] = {
    "coin": "HYPE-USDC",
    "exchange": "spot",
    "l4_checkpoints": {"lag_ms": 82358, "last_updated": "2026-09-29T03:16:29.346Z"},
    "l4_diffs": {"lag_ms": 1614, "last_updated": "2026-09-29T03:17:50.090Z"},
    "measured_at": "2026-09-29T03:17:51.704462628Z",
    "orderbook": {"lag_ms": 4936, "last_updated": "2026-09-29T03:17:46.768Z"},
    "orders": {"lag_ms": 7589, "last_updated": "2026-09-29T03:17:44.115Z"},
    "symbol": "HYPE-USDC",
    "trades": {"lag_ms": 6660, "last_updated": "2026-09-29T03:17:45.044Z"},
    "twap": {"lag_ms": 207694, "last_updated": "2026-09-29T03:14:24.010Z"},
}


def test_spot_freshness_parses_the_datasets_the_api_returns() -> None:
    client, api = mock_client(lambda p, q: envelope(SPOT_FRESHNESS))

    fresh = client.spot.get_freshness("HYPE-USDC")
    afresh = asyncio.run(client.spot.aget_freshness("HYPE-USDC"))

    assert api.calls == [("/v1/hyperliquid/spot/freshness/HYPE-USDC", {})] * 2
    assert fresh == afresh
    assert fresh.symbol == "HYPE-USDC" and fresh.exchange == "spot"
    assert fresh.orderbook is not None and fresh.orderbook.lag_ms == 4936
    assert fresh.twap is not None
    assert fresh.twap.last_updated == datetime(2026, 9, 29, 3, 14, 24, 10000, tzinfo=timezone.utc)
    assert fresh.model_extra == {}
    assert sorted(fresh.tables) == [
        "l4_checkpoints",
        "l4_diffs",
        "orderbook",
        "orders",
        "trades",
        "twap",
    ]
    assert fresh.tables["l4_diffs"].lag_ms == 1614


def test_spot_freshness_tables_skip_missing_datasets() -> None:
    client, _ = mock_client(
        lambda p, q: envelope(
            {"symbol": "PURR-USDC", "coin": "PURR-USDC", "exchange": "spot",
             "measured_at": "2026-09-29T03:17:51Z", "trades": {"lag_ms": None}}
        )
    )

    fresh = client.spot.get_freshness("PURR-USDC")

    assert list(fresh.tables) == ["trades"]
    assert fresh.orderbook is None and fresh.tables["trades"].lag_ms is None
