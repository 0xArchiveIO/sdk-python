"""Account positions: paths, query parameters, cursor following and models.

Response bodies are shaped exactly like the API's JSON: optional fields the
server leaves out are left out here too.
"""

from __future__ import annotations

import asyncio
import copy
from datetime import datetime, timezone
from typing import Any

import httpx
import pytest
from _mock_api import envelope, mock_client

from oxarchive import (
    AccountSummary,
    CursorResponse,
    LighterL1Accounts,
    MarketPosition,
    MarketPositionsSummary,
    OxArchiveError,
    Position,
    PositionChange,
    ResponseMeta,
    WalletPositions,
)

ADDRESS = "0x1111111111111111111111111111111111111111"
LIGHTER_ACCOUNT = 281474976623827
T_HOUR = 1790337600000  # 2026-09-25T12:00:00Z, an exact UTC hour
T_START = 1790251200000  # 2026-09-24T12:00:00Z
T_END = 1790337600000

# ---------------------------------------------------------------------------
# Fixtures shaped like the API's JSON
# ---------------------------------------------------------------------------

HL_POSITION: dict[str, Any] = {
    "symbol": "BTC",
    "coin": "BTC",
    "size": "-1.25",
    "side": "short",
    "entry_price": "64000.5",
    "mark_price": "63500",
    "mark_time": "2026-09-25T12:00:00Z",
    "position_value": "79375",
    "unrealized_pnl": "625.625",
    "return_on_equity": "0.078203",
    "leverage": {"type": "cross", "value": "10"},
    "max_leverage": 40,
    "margin_used": "7937.5",
    "liquidation_price": "70123.4",
    "liquidation_price_status": "exact",
    "cum_funding": {"all_time": "-12.5", "since_open": "-3.25", "since_change": "0"},
    "opened_at": "2026-09-20T08:15:30.123Z",
    "snapshot_as_of": "2026-09-25T11:58:02.456Z",
    "quality": "complete",
}

HL_RECONSTRUCTED_POSITION: dict[str, Any] = {
    "symbol": "ETH",
    "coin": "ETH",
    "size": "12.5",
    "side": "long",
    "entry_price": "2500.25",
    "mark_price": None,
    "mark_time": None,
    "position_value": None,
    "unrealized_pnl": None,
    "return_on_equity": None,
    "leverage": {"type": "unknown", "value": None},
    "max_leverage": None,
    "margin_used": None,
    "liquidation_price": None,
    "liquidation_price_status": "unavailable",
    "cum_funding": {"all_time": None, "since_open": None, "since_change": None},
    "opened_at": "2026-09-01T00:00:00Z",
    "snapshot_as_of": None,
    "quality": "partial",
}

HL_ACCOUNT: dict[str, Any] = {
    "account_value": "15000.123456",
    "cross_account_value": "15000.123456",
    "collateral": "14374.5",
    "total_margin_used": "7937.5",
    "cross_maintenance_margin_used": "1984.375",
    "withdrawable": None,
    "total_position_value": "79375",
    "total_unrealized_pnl": "625.625",
    "long_value": "0",
    "short_value": "79375",
    "n_positions": 1,
    "account_mode": "standard",
    "snapshot_as_of": "2026-09-25T11:58:02.456Z",
    "quality": "complete",
}

HL_CHANGE: dict[str, Any] = {
    "timestamp": "2026-09-25T10:00:01.500Z",
    "symbol": "BTC",
    "coin": "BTC",
    "side": "A",
    "price": "64000",
    "size": "0.5",
    "start_position": "-0.75",
    "end_position": "-1.25",
    "entry_price_after": "64000.5",
    "event_type": "increase",
    "cause": "trade",
    "direction": "Open Short",
    "closed_pnl": "0",
    "fee": "12.8",
    "fee_token": "USDC",
    "crossed": True,
    "trade_id": 123456789,
    "order_id": 987654321,
    "opened_at": "2026-09-20T08:15:30.123Z",
    "seq": 0,
    "block_number": 712345678,
    "event_index": 3,
    "continuity": "ok",
    "finalized": True,
}

LIGHTER_POSITION: dict[str, Any] = {
    "account_index": str(LIGHTER_ACCOUNT),
    "account_kind": "user",
    "symbol": "BTC",
    "coin": "BTC",
    "size": "109.79014",
    "side": "long",
    "entry_price": "84000.1",
    "mark_price": "84363.5",
    "mark_time": "2026-09-25T12:00:00Z",
    "position_value": "9262181.698",
    "unrealized_pnl": "39898.207",
    "return_on_equity": None,
    "leverage": {"type": "cross", "value": None},
    "max_leverage": None,
    "margin_used": None,
    "liquidation_price": None,
    "liquidation_price_status": "unavailable",
    "cum_funding": {"all_time": None, "since_open": None, "since_change": None},
    "opened_at": "2026-08-30T14:02:11Z",
    "snapshot_as_of": None,
    "quality": "complete",
    "initial_margin_fraction": "0.05",
    "allocated_margin": None,
    "margin_mode": "cross",
    "mark_source": "mark",
    "finalized": True,
}

LIGHTER_CHANGE: dict[str, Any] = {
    "timestamp": "2026-09-25T10:00:01.211Z",
    "account_index": str(LIGHTER_ACCOUNT),
    "account_kind": "user",
    "symbol": "BTC",
    "coin": "BTC",
    "side": "B",
    "price": "84367.9",
    "size": "0.00003",
    "start_position": "109.79011",
    "end_position": "109.79014",
    "entry_price_after": "84000.1",
    "event_type": "increase",
    "cause": "trade",
    "realized_pnl": "0",
    "fee": "0.000506",
    "fee_token": "USDC",
    "is_maker": False,
    "trade_id": 31944180930,
    "order_id": 562953419896990,
    "opened_at": "2026-08-30T14:02:11Z",
    "continuity": "ok",
    "position_size_before": "109.79011",
    "position_size_after": "109.79014",
    "fee_rate": "0.0002",
    "fee_usdc": "0.000506",
    "usdc_amount": "2.531037",
    "finalized": False,
}

HL_MARKET_ROW: dict[str, Any] = {
    "user_address": ADDRESS,
    "symbol": "BTC",
    "coin": "BTC",
    "size": "-250",
    "side": "short",
    "entry_price": "63000",
    "mark_price": "63500",
    "position_value": "15875000",
    "unrealized_pnl": "-125000",
    "leverage_type": "cross",
    "liquidation_price": "80000.1",
    "quality": "complete",
}

LIGHTER_MARKET_ROW: dict[str, Any] = {
    "account_index": str(LIGHTER_ACCOUNT),
    "account_kind": "user",
    "symbol": "BTC",
    "coin": "BTC",
    "size": "109.79014",
    "side": "long",
    "entry_price": "84000.1",
    "mark_price": "84363.5",
    "position_value": "9262181.698",
    "unrealized_pnl": "39898.207",
    "leverage_type": "cross",
    "liquidation_price": None,
    "quality": "complete",
}

SUMMARY: dict[str, Any] = {
    "snapshot_ts": "2026-09-25T12:00:00Z",
    "symbol": "BTC",
    "coin": "BTC",
    "long_count": 1200,
    "short_count": 900,
    "long_size": "1500.5",
    "short_size": "1400.25",
    "long_value": "95000000",
    "short_value": "88000000",
    "long_avg_entry_price": "63000.1",
    "short_avg_entry_price": "64500.2",
    "long_positions_with_entry": 1199,
    "short_positions_with_entry": 900,
    "long_top10_value_share": "0.412345",
    "short_top10_value_share": "0.5",
    "top10_value_share": "0.45",
    "quality": "complete",
}


def _with(row: dict[str, Any], **changes: Any) -> dict[str, Any]:
    out = copy.deepcopy(row)
    out.update(changes)
    return out


def _utc(text: str) -> datetime:
    return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(timezone.utc)


# ---------------------------------------------------------------------------
# Hyperliquid core: wallet routes
# ---------------------------------------------------------------------------


def test_hl_get_reads_the_live_snapshot_and_types_the_meta() -> None:
    client, api = mock_client(
        lambda path, q: envelope(
            {"positions": [HL_POSITION], "account": HL_ACCOUNT},
            as_of="2026-09-25T12:00:00.000Z",
            snapshot_ts="2026-09-25T12:00:00.000Z",
            source="snapshot",
            quality="complete",
            stale=False,
        )
    )

    result = client.hyperliquid.positions.get(ADDRESS)

    assert api.calls == [(f"/v1/hyperliquid/wallets/{ADDRESS}/positions", {})]
    assert isinstance(result, CursorResponse)
    assert isinstance(result.data, WalletPositions)
    position = result.data.positions[0]
    assert isinstance(position, Position)
    assert (position.symbol, position.side, position.size) == ("BTC", "short", "-1.25")
    assert position.leverage.type == "cross" and position.leverage.value == "10"
    assert position.cum_funding.all_time == "-12.5"
    assert position.max_leverage == 40
    assert position.mark_time == _utc("2026-09-25T12:00:00Z")
    assert position.dex is None and position.account_index is None
    assert isinstance(result.data.account, AccountSummary)
    assert result.data.account.withdrawable is None
    assert result.data.account.n_positions == 1
    assert result.data.account_seen is None
    assert isinstance(result.meta, ResponseMeta)
    assert result.meta.as_of == _utc("2026-09-25T12:00:00Z")
    assert result.meta.source == "snapshot"
    assert result.meta.stale is False
    assert result.next_cursor is None


def test_hl_get_as_of_sends_epoch_ms_and_exposes_the_clamp() -> None:
    client, api = mock_client(
        lambda path, q: envelope(
            {"positions": [HL_RECONSTRUCTED_POSITION], "account": None},
            as_of="2026-09-25T11:00:00.000Z",
            source="reconstructed",
            quality="partial",
            built_through="2026-09-25T11:00:00.000Z",
            finalized_through="2026-09-24T23:59:59.832Z",
            requested_end="2026-09-25T13:30:00.000Z",
            clamped_to="2026-09-25T11:00:00.000Z",
        )
    )

    result = client.hyperliquid.positions.get(
        ADDRESS, timestamp="2026-09-25T13:30:00Z", symbol="eth", limit=50
    )

    assert api.calls == [
        (
            f"/v1/hyperliquid/wallets/{ADDRESS}/positions",
            {"timestamp": "1790343000000", "symbol": "ETH", "limit": "50"},
        )
    ]
    position = result.data.positions[0]
    assert position.leverage.type == "unknown" and position.leverage.value is None
    assert position.liquidation_price_status == "unavailable"
    assert position.mark_price is None and position.quality == "partial"
    assert result.data.account is None
    meta = result.meta
    assert meta is not None
    assert meta.source == "reconstructed"
    assert meta.built_through == _utc("2026-09-25T11:00:00Z")
    assert meta.clamped_to == meta.built_through
    assert meta.requested_end == _utc("2026-09-25T13:30:00Z")
    assert meta.finalized_through == _utc("2026-09-24T23:59:59.832Z")


def test_hl_get_reports_never_seen_with_a_coverage_notice() -> None:
    client, _ = mock_client(
        lambda path, q: envelope(
            {"positions": [], "account": None, "account_seen": "never_seen"},
            notice="No activity is recorded for this address since 2025-05-25 15:00 (UTC).",
            coverage_from="2025-05-25T15:00:00.000Z",
            source="snapshot",
        )
    )

    result = client.hyperliquid.positions.get(ADDRESS)

    assert result.data.positions == []
    assert result.data.account_seen == "never_seen"
    assert result.meta is not None
    assert result.meta.coverage_from == _utc("2025-05-25T15:00:00Z")
    assert result.meta.notice is not None and "2025-05-25" in result.meta.notice


def test_core_positions_reject_dex_before_sending() -> None:
    client, api = mock_client(lambda path, q: envelope([]))

    with pytest.raises(ValueError, match="dex applies to HIP-3"):
        client.hyperliquid.positions.get(ADDRESS, dex="xyz")
    with pytest.raises(ValueError, match="dex applies to HIP-3"):
        client.hyperliquid.positions.account(ADDRESS, dex="xyz")
    with pytest.raises(ValueError, match="dex applies to HIP-3"):
        client.hyperliquid.positions.iterate_changes(ADDRESS, start=T_START, end=T_END, dex="xyz")

    assert api.requests == []


def test_hl_history_sends_the_window_and_parses_hourly_rows() -> None:
    row = _with(HL_POSITION, snapshot_ts="2026-09-25T11:00:00Z")
    client, api = mock_client(
        lambda path, q: envelope(
            [row],
            next_cursor="c-hist-2",
            source="snapshot",
            finalized_through="2026-09-24T23:59:59.832Z",
        )
    )

    result = client.hyperliquid.positions.history(
        ADDRESS,
        start=datetime(2026, 9, 24, 12, tzinfo=timezone.utc),
        end=T_END,
        symbol="btc",
        cursor="c-hist-1",
        limit=1000,
    )

    assert api.calls == [
        (
            f"/v1/hyperliquid/wallets/{ADDRESS}/positions/history",
            {
                "start": str(T_START),
                "end": str(T_END),
                "symbol": "BTC",
                "cursor": "c-hist-1",
                "limit": "1000",
            },
        )
    ]
    assert result.data[0].snapshot_ts == _utc("2026-09-25T11:00:00Z")
    assert result.next_cursor == "c-hist-2"
    assert result.meta is not None and result.meta.finalized_through is not None


def test_hl_iterate_changes_follows_cursors_with_unchanged_arguments() -> None:
    pages = {
        None: envelope(
            [HL_CHANGE, _with(HL_CHANGE, trade_id=2)], next_cursor="c2", source="changes"
        ),
        "c2": envelope([_with(HL_CHANGE, trade_id=3)], next_cursor="c3", source="changes"),
        "c3": envelope([], source="changes"),
    }
    client, api = mock_client(lambda path, q: pages[q.get("cursor")])

    legs = list(
        client.hyperliquid.positions.iterate_changes(
            ADDRESS, start=T_START, end=T_END, symbol="BTC", limit=2
        )
    )

    assert [leg.trade_id for leg in legs] == [123456789, 2, 3]
    assert all(isinstance(leg, PositionChange) for leg in legs)
    base = {"start": str(T_START), "end": str(T_END), "symbol": "BTC", "limit": "2"}
    assert api.calls == [
        (f"/v1/hyperliquid/wallets/{ADDRESS}/positions/changes", base),
        (f"/v1/hyperliquid/wallets/{ADDRESS}/positions/changes", {**base, "cursor": "c2"}),
        (f"/v1/hyperliquid/wallets/{ADDRESS}/positions/changes", {**base, "cursor": "c3"}),
    ]
    first = legs[0]
    assert first.side == "A" and first.direction == "Open Short" and first.closed_pnl == "0"
    assert first.crossed is True and first.is_maker is None and first.realized_pnl is None
    assert first.seq == 0 and first.block_number == 712345678 and first.event_index == 3
    assert first.continuity == "ok" and first.finalized is True


def test_hl_changes_page_exposes_built_and_finalized_boundaries() -> None:
    client, _ = mock_client(
        lambda path, q: envelope(
            [HL_CHANGE],
            source="changes",
            built_through="2026-09-25T11:00:00.000Z",
            finalized_through="2026-09-25T00:00:00.000Z",
        )
    )

    page = client.hyperliquid.positions.changes(ADDRESS, start=T_START, end=T_END)

    assert page.meta is not None
    assert page.meta.built_through == _utc("2026-09-25T11:00:00Z")
    assert page.meta.finalized_through == _utc("2026-09-25T00:00:00Z")
    assert page.meta.clamped_to is None


def test_hl_account_and_account_history() -> None:
    history_row = _with(HL_ACCOUNT, snapshot_ts="2026-09-25T11:00:00Z", withdrawable="1200.5")
    pages = {
        "/v1/hyperliquid/wallets/{a}/account".format(a=ADDRESS): envelope(
            [HL_ACCOUNT], source="snapshot", stale=True, notice="stale"
        ),
        "/v1/hyperliquid/wallets/{a}/account/history".format(a=ADDRESS): envelope(
            [history_row], source="snapshot"
        ),
    }
    client, api = mock_client(lambda path, q: pages[path])

    now = client.hyperliquid.positions.account(ADDRESS)
    history = client.hyperliquid.positions.account_history(
        ADDRESS, start=T_START, end=T_END, limit=24
    )

    assert api.calls == [
        (f"/v1/hyperliquid/wallets/{ADDRESS}/account", {}),
        (
            f"/v1/hyperliquid/wallets/{ADDRESS}/account/history",
            {"start": str(T_START), "end": str(T_END), "limit": "24"},
        ),
    ]
    assert isinstance(now.data[0], AccountSummary)
    assert now.meta is not None and now.meta.stale is True
    assert history.data[0].snapshot_ts == _utc("2026-09-25T11:00:00Z")
    assert history.data[0].withdrawable == "1200.5"


def test_hl_iterate_account_history_follows_cursors() -> None:
    pages = {
        None: envelope([HL_ACCOUNT], next_cursor="a2"),
        "a2": envelope([_with(HL_ACCOUNT, n_positions=2)]),
    }
    client, api = mock_client(lambda path, q: pages[q.get("cursor")])

    rows = list(
        client.hyperliquid.positions.iterate_account_history(ADDRESS, start=T_START, end=T_END)
    )

    assert [r.n_positions for r in rows] == [1, 2]
    assert [q.get("cursor") for _, q in api.calls] == [None, "a2"]


# ---------------------------------------------------------------------------
# HIP-3
# ---------------------------------------------------------------------------


def test_hip3_wallet_routes_take_dex_and_keep_symbol_case() -> None:
    hip3_position = _with(HL_POSITION, symbol="xyz:TSLA", coin="xyz:TSLA", dex="xyz")
    hip3_account = _with(HL_ACCOUNT, dex="xyz")
    client, api = mock_client(
        lambda path, q: (
            envelope([hip3_account])
            if path.endswith("/account")
            else envelope({"positions": [hip3_position], "account": hip3_account})
        )
    )

    result = client.hyperliquid.hip3.positions.get(ADDRESS, symbol="xyz:TSLA", dex="xyz")
    client.hyperliquid.hip3.positions.account(ADDRESS, dex="xyz")

    assert api.calls[0] == (
        f"/v1/hyperliquid/hip3/wallets/{ADDRESS}/positions",
        {"symbol": "xyz:TSLA", "dex": "xyz"},
    )
    assert api.calls[1] == (f"/v1/hyperliquid/hip3/wallets/{ADDRESS}/account", {"dex": "xyz"})
    assert result.data.positions[0].dex == "xyz"
    assert result.data.account is not None and result.data.account.dex == "xyz"


def test_hip3_market_and_summary_paths_keep_the_dex_prefix() -> None:
    hip3_summary = _with(SUMMARY, symbol="xyz:TSLA", coin="xyz:TSLA", dex="xyz")
    hip3_row = _with(HL_MARKET_ROW, symbol="xyz:TSLA", coin="xyz:TSLA", dex="xyz")
    client, api = mock_client(
        lambda path, q: (
            envelope([hip3_summary])
            if path.endswith("/summary")
            else envelope([hip3_row], totals=hip3_summary)
        )
    )

    summary = client.hyperliquid.hip3.positions.market_summary("xyz:TSLA")
    client.hyperliquid.hip3.positions.market("xyz:TSLA")

    assert api.raw_paths == [
        "/v1/hyperliquid/hip3/positions/xyz%3ATSLA/summary",
        "/v1/hyperliquid/hip3/positions/xyz%3ATSLA",
    ]
    assert api.calls[0][0] == "/v1/hyperliquid/hip3/positions/xyz:TSLA/summary"
    assert summary.data[0].dex == "xyz"


# ---------------------------------------------------------------------------
# Market routes
# ---------------------------------------------------------------------------


def test_hl_market_sends_filters_and_types_the_totals() -> None:
    client, api = mock_client(
        lambda path, q: envelope(
            [HL_MARKET_ROW],
            next_cursor="m2",
            as_of="2026-09-25T12:00:00.000Z",
            snapshot_ts="2026-09-25T12:00:00.000Z",
            source="snapshot",
            quality="complete",
            totals=SUMMARY,
        )
    )

    page = client.hyperliquid.positions.market(
        "btc", hour="2026-09-25T12:00:00Z", side="short", min_value=1_000_000, limit=100
    )

    assert api.calls == [
        (
            "/v1/hyperliquid/positions/BTC",
            {"hour": str(T_HOUR), "side": "short", "min_value": "1000000", "limit": "100"},
        )
    ]
    row = page.data[0]
    assert isinstance(row, MarketPosition)
    assert row.user_address == ADDRESS and row.leverage_type == "cross"
    assert page.meta is not None
    assert isinstance(page.meta.totals, MarketPositionsSummary)
    assert page.meta.totals.long_count == 1200
    assert page.meta.snapshot_ts == _utc("2026-09-25T12:00:00Z")
    assert page.next_cursor == "m2"


def test_market_hour_must_be_an_exact_utc_hour() -> None:
    client, api = mock_client(lambda path, q: envelope([]))

    with pytest.raises(ValueError, match="exact UTC hour"):
        client.hyperliquid.positions.market("BTC", hour=T_HOUR + 1)
    with pytest.raises(ValueError, match="exact UTC hour"):
        client.hyperliquid.positions.all("2026-09-25T12:30:00Z")
    with pytest.raises(ValueError, match="exact UTC hour"):
        client.lighter.positions.iterate_all(T_HOUR - 60_000)

    assert api.requests == []


def test_hl_iterate_market_follows_cursors_on_one_snapshot() -> None:
    pages = {
        None: envelope([HL_MARKET_ROW], next_cursor="m2", totals=SUMMARY),
        "m2": envelope([_with(HL_MARKET_ROW, size="-10")]),
    }
    client, api = mock_client(lambda path, q: pages[q.get("cursor")])

    rows = list(client.hyperliquid.positions.iterate_market("BTC", side="short"))

    assert [r.size for r in rows] == ["-250", "-10"]
    assert api.calls == [
        ("/v1/hyperliquid/positions/BTC", {"side": "short"}),
        ("/v1/hyperliquid/positions/BTC", {"side": "short", "cursor": "m2"}),
    ]


def test_market_summary_now_and_hourly_series() -> None:
    series = {
        None: envelope([SUMMARY], next_cursor="s2", finalized_through="2026-09-25T00:00:00.000Z"),
        "s2": envelope([_with(SUMMARY, snapshot_ts="2026-09-25T13:00:00Z")]),
    }

    def respond(path: str, q: dict[str, str]) -> dict[str, Any]:
        if "start" not in q:
            return envelope([SUMMARY], source="snapshot", stale=False)
        return series[q.get("cursor")]

    client, api = mock_client(respond)

    now = client.hyperliquid.positions.market_summary("BTC")
    hours = list(
        client.hyperliquid.positions.iterate_market_summary("BTC", start=T_START, end=T_END)
    )

    assert api.calls[0] == ("/v1/hyperliquid/positions/BTC/summary", {})
    assert api.calls[1:] == [
        ("/v1/hyperliquid/positions/BTC/summary", {"start": str(T_START), "end": str(T_END)}),
        (
            "/v1/hyperliquid/positions/BTC/summary",
            {"start": str(T_START), "end": str(T_END), "cursor": "s2"},
        ),
    ]
    assert isinstance(now.data[0], MarketPositionsSummary)
    assert now.data[0].top10_value_share == "0.45"
    assert [h.snapshot_ts for h in hours] == [
        _utc("2026-09-25T12:00:00Z"),
        _utc("2026-09-25T13:00:00Z"),
    ]


def test_bulk_all_requires_an_hour_and_iterates_every_page() -> None:
    bulk_row = _with(HL_MARKET_ROW, snapshot_ts="2026-09-25T12:00:00Z")
    pages = {
        None: envelope([bulk_row, bulk_row], next_cursor="b2", source="snapshot"),
        "b2": envelope([bulk_row]),
    }
    client, api = mock_client(lambda path, q: pages[q.get("cursor")])

    first = client.hyperliquid.positions.all(T_HOUR, limit=2)
    everything = list(client.hyperliquid.positions.iterate_all(T_HOUR, limit=2))

    assert api.calls[0] == ("/v1/hyperliquid/positions", {"hour": str(T_HOUR), "limit": "2"})
    assert first.next_cursor == "b2"
    assert first.data[0].snapshot_ts == _utc("2026-09-25T12:00:00Z")
    assert len(everything) == 3
    assert api.calls[-1] == (
        "/v1/hyperliquid/positions",
        {"hour": str(T_HOUR), "limit": "2", "cursor": "b2"},
    )


def test_a_replaced_snapshot_surfaces_as_a_409() -> None:
    client, _ = mock_client(
        lambda path, q: httpx.Response(
            409,
            json={
                "success": False,
                "error": "The snapshot this cursor was paging has been replaced or has expired.",
                "code": "snapshot_advanced",
            },
        )
    )

    with pytest.raises(OxArchiveError) as raised:
        client.hyperliquid.positions.market("BTC", cursor="stale")

    assert raised.value.code == 409
    assert "replaced" in raised.value.message


# ---------------------------------------------------------------------------
# Lighter and Lighter on Robinhood Chain
# ---------------------------------------------------------------------------


def test_lighter_get_uses_the_integer_account_index() -> None:
    client, api = mock_client(
        lambda path, q: envelope({"positions": [LIGHTER_POSITION], "account": None})
    )

    result = client.lighter.positions.get(LIGHTER_ACCOUNT, symbol="btc")
    client.lighter.positions.get(str(LIGHTER_ACCOUNT), timestamp=T_HOUR)

    assert api.calls == [
        (f"/v1/lighter/accounts/{LIGHTER_ACCOUNT}/positions", {"symbol": "BTC"}),
        (f"/v1/lighter/accounts/{LIGHTER_ACCOUNT}/positions", {"timestamp": str(T_HOUR)}),
    ]
    position = result.data.positions[0]
    assert position.account_index == str(LIGHTER_ACCOUNT)
    assert position.account_kind == "user"
    assert position.initial_margin_fraction == "0.05"
    assert position.allocated_margin is None
    assert position.margin_mode == "cross" and position.mark_source == "mark"
    assert position.finalized is True


@pytest.mark.parametrize("bad", ["0x1111111111111111111111111111111111111111", True, -1, "12a"])
def test_lighter_positions_reject_non_integer_account_indices(bad: Any) -> None:
    client, api = mock_client(lambda path, q: envelope([]))

    with pytest.raises(ValueError, match="account_index") as mainnet:
        client.lighter.positions.get(bad)
    with pytest.raises(ValueError, match="account_index") as rh:
        client.rh_lighter.positions.history(bad, start=T_START, end=T_END)

    if isinstance(bad, str) and not bad.lstrip("-").isdigit():
        assert "accounts.by_l1" in str(mainnet.value)
        assert "by_l1" not in str(rh.value)
    assert api.requests == []


def test_lighter_history_and_changes_parse_lighter_fields() -> None:
    pages = {
        f"/v1/lighter/accounts/{LIGHTER_ACCOUNT}/positions/history": envelope(
            [_with(LIGHTER_POSITION, snapshot_ts="2026-09-25T11:00:00Z")]
        ),
        f"/v1/lighter/accounts/{LIGHTER_ACCOUNT}/positions/changes": envelope(
            [LIGHTER_CHANGE],
            source="changes",
            built_through="2026-09-25T11:58:00.000Z",
            finalized_through="2026-09-24T21:00:00.000Z",
        ),
    }
    client, api = mock_client(lambda path, q: pages[path])

    history = client.lighter.positions.history(LIGHTER_ACCOUNT, start=T_START, end=T_END)
    changes = client.lighter.positions.changes(
        LIGHTER_ACCOUNT, start=T_START, end=T_END, symbol="btc", limit=10
    )

    assert api.calls[1] == (
        f"/v1/lighter/accounts/{LIGHTER_ACCOUNT}/positions/changes",
        {"start": str(T_START), "end": str(T_END), "symbol": "BTC", "limit": "10"},
    )
    assert history.data[0].snapshot_ts == _utc("2026-09-25T11:00:00Z")
    leg = changes.data[0]
    assert leg.side == "B" and leg.is_maker is False and leg.crossed is None
    assert leg.realized_pnl == "0" and leg.closed_pnl is None and leg.direction is None
    assert leg.position_size_before == "109.79011" and leg.position_size_after == "109.79014"
    assert leg.fee_rate == "0.0002" and leg.fee_usdc == "0.000506"
    assert leg.usdc_amount == "2.531037" and leg.finalized is False
    assert leg.seq is None and leg.block_number is None
    assert changes.meta is not None
    assert changes.meta.finalized_through == _utc("2026-09-24T21:00:00Z")


def test_lighter_market_routes_send_include_system() -> None:
    client, api = mock_client(
        lambda path, q: (
            envelope([SUMMARY])
            if path.endswith("/summary")
            else envelope(
                [LIGHTER_MARKET_ROW, _with(LIGHTER_MARKET_ROW, account_kind="insurance")],
                totals=SUMMARY,
            )
        )
    )

    page = client.lighter.positions.market(
        "btc", side="long", min_value=10_000.5, include_system=True, limit=2
    )
    client.lighter.positions.market_summary("BTC", include_system=True)
    client.lighter.positions.all(T_HOUR, include_system=True)

    assert api.calls == [
        (
            "/v1/lighter/positions/BTC",
            {"side": "long", "min_value": "10000.5", "include_system": "true", "limit": "2"},
        ),
        ("/v1/lighter/positions/BTC/summary", {"include_system": "true"}),
        ("/v1/lighter/positions", {"hour": str(T_HOUR), "include_system": "true"}),
    ]
    assert [row.account_kind for row in page.data] == ["user", "insurance"]
    assert page.data[0].account_index == str(LIGHTER_ACCOUNT)
    assert page.data[0].user_address is None


def test_lighter_accounts_by_l1_and_its_iterator() -> None:
    first = {
        "l1_address": ADDRESS,
        "total_accounts": 3,
        "accounts": [
            {"account_index": "12", "account_type": 0, "first_seen": "2025-01-17T00:00:00Z"},
            {"account_index": "13", "account_type": 1, "first_seen": None},
        ],
    }
    second = {
        "l1_address": ADDRESS,
        "total_accounts": 3,
        "accounts": [{"account_index": "99", "account_type": 0, "first_seen": None}],
    }
    pages = {None: envelope(first, next_cursor="l2"), "l2": envelope(second)}
    client, api = mock_client(lambda path, q: pages[q.get("cursor")])

    page = client.lighter.accounts.by_l1(ADDRESS, limit=2)
    indices = [a.account_index for a in client.lighter.accounts.iterate_by_l1(ADDRESS, limit=2)]

    assert api.calls[0] == ("/v1/lighter/accounts", {"l1_address": ADDRESS, "limit": "2"})
    assert api.calls[-1] == (
        "/v1/lighter/accounts",
        {"l1_address": ADDRESS, "limit": "2", "cursor": "l2"},
    )
    assert isinstance(page.data, LighterL1Accounts)
    assert page.data.total_accounts == 3
    assert page.data.accounts[0].first_seen == _utc("2025-01-17T00:00:00Z")
    assert indices == ["12", "13", "99"]


def test_rh_lighter_positions_use_the_robinhood_chain_root() -> None:
    rh_position = _with(LIGHTER_POSITION, account_index="7")
    rh_change = _with(LIGHTER_CHANGE, account_index="7", fee_token="USDG")

    def respond(path: str, q: dict[str, str]) -> dict[str, Any]:
        if path.endswith("/changes"):
            return envelope([rh_change])
        if path.endswith("/history"):
            return envelope([rh_position])
        if path.endswith("/summary"):
            return envelope([SUMMARY])
        if path.startswith("/v1/rh-lighter/accounts/"):
            return envelope({"positions": [rh_position], "account": None})
        return envelope([LIGHTER_MARKET_ROW])

    client, api = mock_client(respond)
    rh = client.rh_lighter.positions

    rh.get(7)
    rh.history(7, start=T_START, end=T_END)
    changes = rh.changes(7, start=T_START, end=T_END)
    rh.market("btc")
    rh.market_summary("BTC", start=T_START, end=T_END)
    rh.all(T_HOUR)

    assert [path for path, _ in api.calls] == [
        "/v1/rh-lighter/accounts/7/positions",
        "/v1/rh-lighter/accounts/7/positions/history",
        "/v1/rh-lighter/accounts/7/positions/changes",
        "/v1/rh-lighter/positions/BTC",
        "/v1/rh-lighter/positions/BTC/summary",
        "/v1/rh-lighter/positions",
    ]
    assert changes.data[0].fee_token == "USDG"
    assert not hasattr(client.rh_lighter, "accounts")
    assert not hasattr(rh, "account") and not hasattr(client.lighter.positions, "account")


# ---------------------------------------------------------------------------
# Async
# ---------------------------------------------------------------------------


def test_async_positions_methods_match_the_sync_requests() -> None:
    def respond(path: str, q: dict[str, str]) -> dict[str, Any]:
        if path.endswith("/wallets/" + ADDRESS + "/positions"):
            return envelope({"positions": [HL_POSITION], "account": HL_ACCOUNT})
        if path.endswith("/changes"):
            pages = {None: envelope([HL_CHANGE], next_cursor="c2"), "c2": envelope([HL_CHANGE])}
            return pages[q.get("cursor")]
        if path.endswith("/history") and "/account/" in path:
            return envelope([HL_ACCOUNT])
        if path.endswith("/history"):
            return envelope([HL_POSITION])
        if path.endswith("/summary"):
            return envelope([SUMMARY])
        if path == "/v1/lighter/accounts":
            return envelope({"l1_address": ADDRESS, "total_accounts": 0, "accounts": []})
        if path.startswith("/v1/lighter/accounts/"):
            return envelope({"positions": [LIGHTER_POSITION], "account": None})
        if path.endswith("/account"):
            return envelope([HL_ACCOUNT])
        return envelope([HL_MARKET_ROW])

    client, api = mock_client(respond)
    hl = client.hyperliquid.positions

    async def run() -> dict[str, Any]:
        out: dict[str, Any] = {}
        out["get"] = await hl.aget(ADDRESS)
        out["history"] = await hl.ahistory(ADDRESS, start=T_START, end=T_END)
        out["changes"] = [
            leg async for leg in hl.aiterate_changes(ADDRESS, start=T_START, end=T_END)
        ]
        out["account"] = await hl.aaccount(ADDRESS)
        out["account_history"] = await hl.aaccount_history(ADDRESS, start=T_START, end=T_END)
        out["market"] = await hl.amarket("BTC", hour=T_HOUR)
        out["summary"] = await hl.amarket_summary("BTC")
        out["all"] = await hl.aall(T_HOUR)
        out["lighter"] = await client.lighter.positions.aget(LIGHTER_ACCOUNT)
        out["l1"] = await client.lighter.accounts.aby_l1(ADDRESS)
        await client.aclose()
        return out

    out = asyncio.run(run())

    assert isinstance(out["get"].data, WalletPositions)
    assert len(out["changes"]) == 2
    assert isinstance(out["account"].data[0], AccountSummary)
    assert isinstance(out["summary"].data[0], MarketPositionsSummary)
    assert isinstance(out["lighter"].data.positions[0], Position)
    assert out["l1"].data.total_accounts == 0
    assert [path for path, _ in api.calls] == [
        f"/v1/hyperliquid/wallets/{ADDRESS}/positions",
        f"/v1/hyperliquid/wallets/{ADDRESS}/positions/history",
        f"/v1/hyperliquid/wallets/{ADDRESS}/positions/changes",
        f"/v1/hyperliquid/wallets/{ADDRESS}/positions/changes",
        f"/v1/hyperliquid/wallets/{ADDRESS}/account",
        f"/v1/hyperliquid/wallets/{ADDRESS}/account/history",
        "/v1/hyperliquid/positions/BTC",
        "/v1/hyperliquid/positions/BTC/summary",
        "/v1/hyperliquid/positions",
        f"/v1/lighter/accounts/{LIGHTER_ACCOUNT}/positions",
        "/v1/lighter/accounts",
    ]


def test_positions_resources_expose_the_same_method_names_on_every_venue() -> None:
    client, _ = mock_client(lambda path, q: envelope([]))
    shared = {
        "get",
        "history",
        "changes",
        "market",
        "market_summary",
        "all",
        "iterate_history",
        "iterate_changes",
        "iterate_market",
        "iterate_market_summary",
        "iterate_all",
    }
    shared |= {"a" + name for name in shared}
    hl_only = {
        "account",
        "account_history",
        "aaccount",
        "aaccount_history",
        "iterate_account_history",
        "aiterate_account_history",
    }

    for resource in (client.hyperliquid.positions, client.hyperliquid.hip3.positions):
        assert shared | hl_only <= set(dir(resource))
    for resource in (client.lighter.positions, client.rh_lighter.positions):
        assert shared <= set(dir(resource))
        assert not hl_only & set(dir(resource))
    assert {"by_l1", "aby_l1", "iterate_by_l1", "aiterate_by_l1"} <= set(
        dir(client.lighter.accounts)
    )


def test_response_meta_keeps_unknown_fields_and_empty_instants() -> None:
    meta = ResponseMeta.model_validate(
        {"count": 0, "request_id": "r", "as_of": "", "totals": {"future": 1}, "new_field": "x"}
    )

    assert meta.as_of is None
    assert meta.totals == {"future": 1}
    assert meta.model_extra == {"new_field": "x"}
