"""The 2026-10-01 API contract: version selector, error codes, pagination state,
response meta, capabilities, working filters, WebSocket replay rules and verbs.

Every REST call goes through the real ``Client`` into a mocked transport, so
the tests see the exact path, query and headers the SDK sends. The response
bodies are the shapes the API returns under ``0xArchive-Version: 2026-10-01``.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional, cast, get_args

import httpx
import pytest
from _mock_api import envelope, mock_client

import oxarchive
from oxarchive import (
    API_VERSION,
    API_VERSION_HEADER,
    ERROR_CODES,
    VENUES,
    WEBSOCKET_ERROR_CODES,
    Capability,
    CursorResponse,
    ErrorCode,
    OxArchiveError,
    ResponseMeta,
    Venue,
)
from oxarchive.resources.trades import TradesResource
from oxarchive.types import (
    CvdBucket,
    Hip3OracleDiscoveryBounds,
    Hip3OracleExternalPrice,
    LighterLiquidation,
    LighterLiquidationVolume,
    LighterMarketContextUpdate,
    OrderBook,
    Trade,
    WsChannel,
    WsError,
    WsHistoricalData,
    WsReplaySnapshot,
    WsReplayStarted,
    WsSubscribed,
)
from oxarchive.websocket import (
    BULK_REPLAY_CHANNELS,
    L4_LIVE_ONLY_CHANNELS,
    L4_REPLAY_CHANNELS,
    LIVE_CHANNELS,
    REPLAY_CHANNELS,
    WS_CHANNELS,
    OxArchiveWs,
    WsOptions,
    decode_lighter_payload,
)

T_START = 1790640000000  # 2026-09-29T00:00:00Z
T_END = 1790726400000  # 2026-09-30T00:00:00Z
ROOT = Path(__file__).resolve().parents[1]


def _page(
    data: Any, *, has_more: bool, next_cursor: Optional[str] = None, **meta: Any
) -> dict[str, Any]:
    body = envelope(data, next_cursor=next_cursor, **meta)
    body["meta"]["has_more"] = has_more
    return body


def _subject(data: Any, symbol: str, venue: str, **meta: Any) -> dict[str, Any]:
    return envelope(data, symbol=symbol, venue=venue, **meta)


# ===========================================================================
# 1. Version selector
# ===========================================================================


def test_api_version_constants() -> None:
    assert API_VERSION == "2026-10-01"
    assert API_VERSION_HEADER == "0xArchive-Version"


SYNC_CALLS: list[Callable[[oxarchive.Client], Any]] = [
    lambda c: c.hyperliquid.orderbook.get("BTC"),
    lambda c: c.hyperliquid.trades.history("BTC", start=T_START, end=T_END),
    lambda c: c.lighter.trades.recent("BTC"),
    lambda c: c.capabilities(),
    lambda c: c.symbols.list(),
    lambda c: c.data_quality.status(),
    lambda c: c.webhooks.list_endpoints(),
    lambda c: c.hyperliquid.positions.get("0xabc"),
]


def _any_body(path: str, query: dict[str, str]) -> dict[str, Any]:
    if path.endswith("/orderbook/BTC"):
        return envelope({"coin": "BTC", "timestamp": "2026-09-29T00:00:00Z", "bids": [], "asks": []})
    if path.endswith("/data-quality/status"):
        return envelope({"status": "operational", "updated_at": "2026-09-29T00:00:00Z", "exchanges": {}, "data_types": {}, "active_incidents": 0})
    if "/positions" in path or "/wallets/" in path:
        return envelope({"address": "0xabc", "positions": [], "account": None, "account_seen": None})
    return envelope([])


@pytest.mark.parametrize("call", SYNC_CALLS)
def test_every_sync_request_sends_the_version_header(call: Callable[[oxarchive.Client], Any]) -> None:
    client, api = mock_client(_any_body)

    call(client)

    assert api.requests, "no request was sent"
    for request in api.requests:
        assert request.headers[API_VERSION_HEADER] == API_VERSION
        assert request.headers["X-API-Key"] == "0xa_test"


def test_every_async_request_sends_the_version_header() -> None:
    client, api = mock_client(_any_body)

    async def run() -> None:
        await client.hyperliquid.orderbook.aget("BTC")
        await client.hyperliquid.trades.ahistory("BTC", start=T_START, end=T_END)
        await client.acapabilities()
        await client.symbols.alist()
        await client.data_quality.astatus()

    asyncio.run(run())

    assert len(api.requests) == 5
    assert {r.headers[API_VERSION_HEADER] for r in api.requests} == {API_VERSION}


def test_a_fresh_client_sends_the_header_on_both_transports() -> None:
    client = oxarchive.Client(api_key="0xa_test", base_url="https://api.example.test")
    assert client._http.client.headers[API_VERSION_HEADER] == API_VERSION
    assert client._http.async_client.headers[API_VERSION_HEADER] == API_VERSION
    client.close()


def test_websocket_connects_with_the_version_parameter() -> None:
    ws = OxArchiveWs(WsOptions(api_key="0xa_key"))
    assert ws._connection_url() == "wss://api.0xarchive.io/ws?apiKey=0xa_key&version=2026-10-01"

    custom = OxArchiveWs(WsOptions(api_key="0xa_key", ws_url="wss://example.test/ws?region=eu"))
    assert custom._connection_url() == (
        "wss://example.test/ws?region=eu&apiKey=0xa_key&version=2026-10-01"
    )


def test_websocket_connect_opens_the_versioned_url(monkeypatch: pytest.MonkeyPatch) -> None:
    opened: list[str] = []

    async def fake_connect(url: str, **kwargs: Any) -> Any:
        opened.append(url)
        raise OSError("offline")

    monkeypatch.setattr("oxarchive.websocket.ws_connect", fake_connect)
    ws = OxArchiveWs(WsOptions(api_key="0xa_key", auto_reconnect=False))
    errors: list[Exception] = []
    ws.on_error(errors.append)

    asyncio.run(ws.connect())

    assert opened == ["wss://api.0xarchive.io/ws?apiKey=0xa_key&version=2026-10-01"]
    assert ws.state == "disconnected" and errors


# ---- data quality, status coverage and symbols envelopes ----------------------

STATUS = {
    "status": "degraded",
    "updated_at": "2026-09-29T14:57:56.919Z",
    "exchanges": {"hyperliquid": {"status": "operational", "last_data_at": "2026-09-29T14:55:10Z", "latency_ms": 1200}},
    "data_types": {},
    "active_incidents": 0,
}
COVERAGE = {
    "exchanges": [
        {
            "exchange": "hyperliquid",
            "data_types": {
                "orderbook": {
                    "earliest": "2023-04-15T00:00:07Z",
                    "latest": "2026-09-29T14:56:01Z",
                    "total_records": 28098760700,
                    "symbols": 234,
                    "resolution": "~1.2 seconds",
                    "completeness": 100.0,
                }
            },
        }
    ]
}
SYMBOL_COVERAGE = {
    "exchange": "hyperliquid",
    "symbol": "BTC",
    "data_types": {
        "funding": {
            "earliest": "2023-05-20T02:50:04Z",
            "latest": "2026-09-29T14:55:42.583Z",
            "total_records": 1755931,
            "completeness": 100.0,
            "historical_coverage": 99.0,
            "gaps": [],
        }
    },
}
INCIDENT = {
    "id": "INC-2026-001",
    "status": "resolved",
    "severity": "major",
    "exchange": "lighter",
    "data_types": ["orderbook"],
    "symbols_affected": ["ALL"],
    "started_at": "2026-02-12T22:02:03Z",
    "resolved_at": "2026-02-12T22:52:00Z",
    "duration_minutes": 49,
    "title": "Upstream outage",
}
LATENCY = {"measured_at": "2026-09-29T14:57:57.571Z", "exchanges": {}}
SLA = {
    "period": "2026-09",
    "sla_targets": {"uptime": 99.9, "data_completeness": 99.5, "api_latency_p99_ms": 500},
    "actual": {
        "uptime": 100.0,
        "uptime_status": "met",
        "data_completeness": {"orderbook": 99.9, "funding": 99.9, "open_interest": 99.9, "overall": 99.9},
        "completeness_status": "met",
        "api_latency_p99_ms": 369,
        "latency_status": "met",
    },
    "incidents_this_period": 0,
    "total_downtime_minutes": 0,
}


def _versioned(payload: Any) -> dict[str, Any]:
    return {"success": True, "data": payload, "meta": {"request_id": "req-dq"}}


def _legacy(payload: dict[str, Any]) -> dict[str, Any]:
    return {"success": True, **payload, "meta": {"request_id": "req-dq"}}


DQ_ROUTES: dict[str, Any] = {
    "/v1/data-quality/status": STATUS,
    "/v1/data-quality/coverage": COVERAGE,
    "/v1/status/coverage": COVERAGE,
    "/v1/data-quality/coverage/hyperliquid": COVERAGE["exchanges"][0],
    "/v1/data-quality/coverage/hyperliquid/BTC": SYMBOL_COVERAGE,
    "/v1/data-quality/incidents": {"incidents": [INCIDENT], "pagination": {"total": 1, "limit": 20, "offset": 0}},
    "/v1/data-quality/incidents/INC-2026-001": INCIDENT,
    "/v1/data-quality/latency": LATENCY,
    "/v1/data-quality/sla": SLA,
}


def _check_data_quality(client: oxarchive.Client) -> None:
    dq = client.data_quality
    status = dq.status()
    assert status.status == "degraded" and status.exchanges["hyperliquid"].status == "operational"
    assert status.response_meta is not None and status.response_meta.request_id == "req-dq"
    assert dq.coverage().exchanges[0].data_types["orderbook"].total_records == 28098760700
    assert dq.status_coverage().exchanges[0].exchange == "hyperliquid"
    assert dq.exchange_coverage("hyperliquid").exchange == "hyperliquid"
    symbol = dq.symbol_coverage("hyperliquid", "BTC")
    assert symbol.symbol == "BTC" and symbol.data_types["funding"].completeness == 100.0
    assert dq.list_incidents().incidents[0].id == "INC-2026-001"
    assert dq.get_incident("INC-2026-001").duration_minutes == 49
    assert dq.latency().exchanges == {}
    assert dq.sla().period == "2026-09"


def test_data_quality_parses_the_versioned_envelope() -> None:
    client, api = mock_client(lambda path, q: _versioned(DQ_ROUTES[path]))
    _check_data_quality(client)
    assert len(api.requests) == 9


def test_data_quality_still_parses_the_older_top_level_body() -> None:
    client, _ = mock_client(lambda path, q: _legacy(DQ_ROUTES[path]))
    _check_data_quality(client)


def test_data_quality_async_parses_the_versioned_envelope() -> None:
    client, _ = mock_client(lambda path, q: _versioned(DQ_ROUTES[path]))

    async def run() -> None:
        assert (await client.data_quality.astatus()).status == "degraded"
        assert (await client.data_quality.astatus_coverage()).exchanges[0].exchange == "hyperliquid"
        assert (await client.data_quality.asymbol_coverage("hyperliquid", "BTC")).symbol == "BTC"

    asyncio.run(run())


SYMBOL_ROW = {
    "symbol": "BTC",
    "exchange": "hyperliquid",
    "coverage_from": "2023-04-15T00:00:00Z",
    "data_types": ["trades", "l2_orderbook"],
    "coverage_by_type": {"trades": "2023-04-15T00:00:00Z"},
}


def test_symbols_parse_the_versioned_data_array() -> None:
    client, api = mock_client(
        lambda p, q: {"success": True, "data": [SYMBOL_ROW], "meta": {"count": 1, "request_id": "r"}}
    )
    rows = client.symbols.list()
    assert [r.symbol for r in rows] == ["BTC"] and api.calls[0][0] == "/v1/symbols"


def test_symbols_still_parse_the_older_symbols_key() -> None:
    client, _ = mock_client(
        lambda p, q: {"success": True, "symbols": [SYMBOL_ROW], "meta": {"request_id": "r"}}
    )
    assert [r.exchange for r in client.symbols.list()] == ["hyperliquid"]
    assert [r.symbol for r in asyncio.run(client.symbols.alist())] == ["BTC"]


# ---- time outliers -------------------------------------------------------------

CVD_V = {
    "buy_volume": 94913298.5,
    "sell_volume": 97951950.4,
    "delta": -3038651.9,
    "cumulative_delta": -3038651.9,
    "timestamp": "2026-09-29T13:00:00.000Z",
    "timestamp_ms": 1790686800000,
}
ORACLE_V = {
    "symbol": "km:US500",
    "external_price": 749.64,
    "mark_price": 750.97,
    "block_number": 1165513777,
    "timestamp": "2026-09-29T14:58:00.016Z",
    "timestamp_ms": 1790693880016,
}
BOUNDS_V = {
    "symbol": "km:US500",
    "reference_price": 749.64,
    "reference_source": "external",
    "max_leverage": 25,
    "bound_fraction": 0.04,
    "lower_bound": 719.6544,
    "upper_bound": 779.6256,
    "block_number": 1165513777,
    "timestamp": "2026-09-29T14:58:00.016Z",
    "timestamp_ms": 1790693880016,
}
LIGHTER_LIQ_V = {
    "symbol": "BTC",
    "timestamp": "2026-09-20T02:40:57.104Z",
    "timestamp_ms": 1789872057104,
    "transaction_time_us": 1789872057136978,
    "trade_id": 31156998607,
    "price": 80866.3,
    "size": 0.00064,
}
LIGHTER_VOLUME_V = {
    "symbol": "BTC",
    "timestamp": "2026-09-20T00:00:00.000Z",
    "timestamp_ms": 1789862400000,
    "total_usd": 125479.97,
    "count": 194,
}


def test_versioned_time_fields_parse_to_utc_datetimes_with_ms() -> None:
    cvd = CvdBucket.model_validate(CVD_V)
    assert cvd.timestamp == datetime(2026, 9, 29, 13, tzinfo=timezone.utc)
    assert cvd.timestamp_ms == 1790686800000

    for model, row in (
        (Hip3OracleExternalPrice, ORACLE_V),
        (Hip3OracleDiscoveryBounds, BOUNDS_V),
    ):
        parsed = model.model_validate(row)
        assert parsed.timestamp == datetime(2026, 9, 29, 14, 58, 0, 16000, tzinfo=timezone.utc)
        assert parsed.timestamp_ms == 1790693880016

    liq = LighterLiquidation.model_validate(LIGHTER_LIQ_V)
    assert liq.timestamp_ms == 1789872057104 and liq.timestamp.tzinfo is not None
    vol = LighterLiquidationVolume.model_validate(LIGHTER_VOLUME_V)
    assert vol.timestamp == datetime(2026, 9, 20, tzinfo=timezone.utc) and vol.timestamp_ms == 1789862400000


def test_older_integer_times_still_parse_and_fill_the_ms_field() -> None:
    legacy = {**CVD_V, "timestamp": 1790686800000}
    del legacy["timestamp_ms"]
    cvd = CvdBucket.model_validate(legacy)
    assert cvd.timestamp == datetime(2026, 9, 29, 13, tzinfo=timezone.utc)
    assert cvd.timestamp_ms == 1790686800000


def test_levels_snapshot_ts_ms_is_typed() -> None:
    client, _ = mock_client(
        lambda path, q: _subject(
            [{"snapshot_ts": "2026-09-28T15:01:49.000Z", "snapshot_ts_ms": 1790607709000, "block_number": 1, "mid_price": 1.0, "total_long": 0.0, "total_short": 0.0, "flagged_notional": 0.0}]
            if path.endswith("/levels/history")
            else [{"snapshot_ts": "2026-09-28T15:00:01.000Z", "snapshot_ts_ms": 1790607601000, "mid_price": 1.0, "total_bid_size": 0.0, "total_ask_size": 0.0}]
            if path.endswith("/trigger-levels/history")
            else {"snapshot_ts": "2026-09-29T14:56:47.000Z", "snapshot_ts_ms": 1790693807000, "block_number": 1, "mid_price": 1.0, "total_long": 0.0, "total_short": 0.0, "flagged_notional": 0.0, "levels": []},
            "BTC",
            "hyperliquid",
        )
    )
    levels = client.hyperliquid.liquidations.levels("BTC")
    assert levels.snapshot_ts == "2026-09-29T14:56:47.000Z" and levels.snapshot_ts_ms == 1790693807000
    history = client.hyperliquid.liquidations.levels_history("BTC", summary=True)
    assert history.data[0].snapshot_ts_ms == 1790607709000
    triggers = client.hyperliquid.orders.trigger_levels_history("BTC", summary=True)
    assert triggers.data[0].snapshot_ts_ms == 1790607601000


def test_cvd_oracle_and_lighter_liquidations_parse_the_versioned_bodies() -> None:
    def respond(path: str, q: dict[str, str]) -> dict[str, Any]:
        if "/cvd/" in path:
            return _page([CVD_V], has_more=False, symbol="BTC", venue="hyperliquid")
        if "external-price" in path:
            return _subject(ORACLE_V, "km:US500", "hip3")
        if "discovery-bounds" in path:
            return _subject(BOUNDS_V, "km:US500", "hip3")
        if path.endswith("/volume"):
            return _page([LIGHTER_VOLUME_V], has_more=True, next_cursor="1789862400000", symbol="BTC", venue="rh-lighter")
        return _page([LIGHTER_LIQ_V], has_more=False, symbol="BTC", venue="lighter")

    client, _ = mock_client(respond)
    assert client.hyperliquid.cvd.history("BTC").data[0].timestamp_ms == 1790686800000
    price = client.hyperliquid.hip3.oracle.external_price("km:US500")
    assert price.timestamp_ms == 1790693880016 and price.response_meta.venue == "hip3"
    assert client.hyperliquid.hip3.oracle.discovery_bounds("km:US500").timestamp_ms == 1790693880016
    liqs = client.lighter.liquidations.history("BTC", start=T_START, end=T_END)
    assert liqs.data[0].timestamp_ms == 1789872057104 and liqs.has_more is False
    volume = client.rh_lighter.liquidations.volume("BTC", start=T_START, end=T_END)
    assert volume.data[0].timestamp_ms == 1789862400000 and volume.has_more is True
    assert volume.meta.venue == "rh-lighter"


def test_l4_snapshot_order_times_pass_through_in_the_versioned_shape() -> None:
    snapshot = {
        "coin": "BTC",
        "timestamp": "2026-09-29T14:57:29.345Z",
        "last_block_number": 1165513326,
        "bids": [
            {"oid": 1, "price": 83824.0, "side": "B", "size": 0.28, "timestamp": "2026-09-29T14:57:27.983Z", "timestamp_ms": 1790693847983, "user_address": "0x7b"},
            {"oid": 2, "price": 83823.0, "side": "B", "size": 0.1, "timestamp": None, "timestamp_ms": 0, "user_address": "0x7c"},
        ],
        "asks": [],
    }
    client, _ = mock_client(lambda p, q: _subject(snapshot, "BTC", "hyperliquid"))
    book = client.hyperliquid.l4_orderbook.get("BTC")
    assert book["bids"][0]["timestamp"] == "2026-09-29T14:57:27.983Z"
    assert book["bids"][0]["timestamp_ms"] == 1790693847983
    assert book["bids"][1]["timestamp"] is None and book["bids"][1]["timestamp_ms"] == 0


# ---- Lighter replay uses the live shapes ----------------------------------------

LIVE_LEG = {
    "coin": "BTC",
    "side": "A",
    "px": "84925.1",
    "sz": "0.001",
    "time": 1790503200112,
    "hash": "55ce05e1",
    "tid": 32208547226,
    "oid": 562953431283143,
    "crossed": False,
    "dir": None,
    "fee": "0.000028",
    "fee_token": None,
    "closed_pnl": None,
    "start_position": "-0.04286",
    "users": ["281474976656674"],
}
LIVE_BOOK = {
    "coin": "BTC",
    "time": 1790503223423,
    "levels": [
        [{"n": 1, "px": "84870.8", "sz": "0.00244"}],
        [{"n": 1, "px": "84881.4", "sz": "0.05275"}],
    ],
}
LIVE_CTX = {
    "coin": "BTC",
    "ctx": {
        "openInterest": "175884735.9",
        "funding": "0.000008",
        "markPx": "84349.7",
        "oraclePx": "84391.7",
        "premium": None,
        "midPx": None,
        "dayNtlVlm": None,
        "dayBaseVlm": None,
        "prevDayPx": None,
        "impactPxs": None,
    },
}


def _historical(channel: str, data: Any, ts: int = 1790503200112) -> str:
    return json.dumps(
        {"type": "historical_data", "channel": channel, "coin": "BTC", "symbol": "BTC", "timestamp": ts, "data": data}
    )


@pytest.mark.parametrize("prefix", ["lighter", "rh_lighter"])
def test_lighter_replay_records_decode_with_the_live_parsers(prefix: str) -> None:
    ws = OxArchiveWs(WsOptions(api_key="k"))
    raw: list[tuple[str, int, Any]] = []
    decoded: list[tuple[str, str, int, Any]] = []
    ws.on_historical_data(lambda coin, ts, data: raw.append((coin, ts, data)))
    ws.on_replay_data(lambda channel, coin, ts, record: decoded.append((channel, coin, ts, record)))

    ws._handle_message(_historical(f"{prefix}_trades", [LIVE_LEG]))
    ws._handle_message(_historical(f"{prefix}_orderbook", LIVE_BOOK, 1790503223423))
    ws._handle_message(_historical(f"{prefix}_funding", LIVE_CTX))

    assert raw[0] == ("BTC", 1790503200112, [LIVE_LEG])
    channel, coin, ts, legs = decoded[0]
    assert channel == f"{prefix}_trades" and coin == "BTC" and ts == 1790503200112
    assert isinstance(legs, list) and isinstance(legs[0], Trade)
    assert (legs[0].side, legs[0].price, legs[0].account_index, legs[0].fee) == ("A", "84925.1", "281474976656674", "0.000028")
    book = decoded[1][3]
    assert isinstance(book, OrderBook) and book.bids[0].px == "84870.8" and book.asks[0].px == "84881.4"
    ctx = decoded[2][3]
    assert isinstance(ctx, LighterMarketContextUpdate) and ctx.ctx.funding_rate == "0.000008"


def test_other_replay_records_pass_through_unchanged() -> None:
    ws = OxArchiveWs(WsOptions(api_key="k"))
    decoded: list[Any] = []
    ws.on_replay_data(lambda channel, coin, ts, record: decoded.append((channel, record)))
    candle = {"open": 1.0, "close": 2.0}

    ws._handle_message(_historical("lighter_candles", candle))
    ws._handle_message(_historical("orderbook", {"bids": [], "asks": []}))

    assert decoded == [("lighter_candles", candle), ("orderbook", {"bids": [], "asks": []})]
    assert decode_lighter_payload("funding", "BTC", candle) is candle


def test_replay_messages_with_list_payloads_are_typed() -> None:
    data = WsHistoricalData.model_validate(
        {"type": "historical_data", "channel": "lighter_trades", "coin": "BTC", "timestamp": 1, "data": [LIVE_LEG]}
    )
    assert data.data == [LIVE_LEG]
    snap = WsReplaySnapshot.model_validate(
        {"type": "replay_snapshot", "channel": "lighter_trades", "coin": "BTC", "timestamp": 1, "data": [LIVE_LEG]}
    )
    assert isinstance(snap.data, list)
    decoded = decode_lighter_payload("lighter_trades", "BTC", snap.data)
    assert [t.trade_id for t in decoded] == [32208547226]


def test_acknowledgements_carry_the_selected_version() -> None:
    sub = WsSubscribed.model_validate(
        {"type": "subscribed", "channel": "trades", "coin": "BTC", "symbol": "BTC", "version": "2026-10-01"}
    )
    assert sub.version == API_VERSION
    started = WsReplayStarted.model_validate(
        {"type": "replay_started", "channel": "hip3_l4_diffs", "coin": "xyz:TSLA", "symbol": "xyz:TSLA", "start": 1, "end": 2, "speed": 3.0, "version": "2026-10-01"}
    )
    assert started.version == API_VERSION and started.symbol == "xyz:TSLA"


# ===========================================================================
# 2. Errors
# ===========================================================================


def test_error_code_set_matches_the_contract() -> None:
    assert ERROR_CODES == get_args(ErrorCode)
    assert len(set(ERROR_CODES)) == len(ERROR_CODES)
    assert ERROR_CODES[:5] == (
        "invalid_parameter",
        "invalid_symbol",
        "invalid_interval",
        "invalid_cursor",
        "invalid_time_range",
    )
    for code in (
        "range_before_coverage",
        "historical_range_exceeded",
        "historical_depth_exceeded",
        "unsupported_for_venue",
        "route_not_found",
        "not_found",
        "unauthorized",
        "forbidden",
        "insufficient_credits",
        "rate_limited",
        "conflict",
        "upstream_unavailable",
        "internal_error",
        "positions_unavailable",
        "api_key_limit_reached",
        "oauth_not_permitted",
    ):
        assert code in ERROR_CODES
    assert WEBSOCKET_ERROR_CODES == {"slow_consumer", "endpoint_unsupported"}
    assert WEBSOCKET_ERROR_CODES <= set(ERROR_CODES)
    assert oxarchive.ErrorCode is ErrorCode and "ERROR_CODES" in oxarchive.__all__


def test_rest_errors_expose_the_contract_fields() -> None:
    body = {
        "success": False,
        "code": 400,
        "error_code": "invalid_parameter",
        "error": "Invalid side 'both'. Use buy or sell.",
        "request_id": "req-1",
        "param": "side",
        "valid_values": ["buy", "sell"],
    }
    client, _ = mock_client(lambda p, q: httpx.Response(400, json=body))

    with pytest.raises(OxArchiveError) as caught:
        client.hyperliquid.trades.history("BTC", start=T_START, end=T_END, side=cast(Any, "both"))

    error = caught.value
    assert (error.status, error.code, error.error_code) == (400, 400, "invalid_parameter")
    assert (error.request_id, error.param, error.valid_values) == ("req-1", "side", ["buy", "sell"])
    assert error.message == "Invalid side 'both'. Use buy or sell."
    assert error.details == body
    assert "error_code: invalid_parameter" in str(error) and "request_id: req-1" in str(error)


def test_unsupported_for_venue_keeps_where_it_is_available() -> None:
    body = {
        "success": False,
        "code": 404,
        "error_code": "unsupported_for_venue",
        "error": "Order flow is not offered on Hyperliquid spot.",
        "request_id": "req-2",
        "datatype": "order_flow",
        "venue": "spot",
        "available_on": [{"route": "/v1/hyperliquid/orders/{symbol}/flow", "venue": "hyperliquid"}],
    }
    client, _ = mock_client(lambda p, q: httpx.Response(404, json=body))

    with pytest.raises(OxArchiveError) as caught:
        asyncio.run(client._http.aget("/v1/hyperliquid/spot/orders/HYPE-USDC/flow"))

    assert caught.value.error_code == "unsupported_for_venue"
    assert caught.value.details["available_on"][0]["venue"] == "hyperliquid"


@pytest.mark.parametrize(
    "status, code",
    [(401, "unauthorized"), (403, "forbidden"), (404, "not_found"), (429, "rate_limited"), (502, "upstream_unavailable"), (500, "internal_error")],
)
def test_an_error_page_without_a_body_gets_a_code_from_its_status(status: int, code: str) -> None:
    client, _ = mock_client(lambda p, q: httpx.Response(status, text="<html>Bad Gateway</html>"))

    with pytest.raises(OxArchiveError) as caught:
        client.hyperliquid.orderbook.get("BTC")

    assert caught.value.status == status and caught.value.error_code == code
    assert "Bad Gateway" in caught.value.message


def test_a_json_error_without_a_code_gets_one_from_its_status() -> None:
    client, _ = mock_client(lambda p, q: httpx.Response(429, json={"error": "Too many requests"}))

    with pytest.raises(OxArchiveError) as caught:
        client.hyperliquid.orderbook.get("BTC")

    assert caught.value.error_code == "rate_limited" and caught.value.message == "Too many requests"


def test_network_errors_have_status_zero_and_no_code() -> None:
    def fail(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("unreachable", request=request)

    client = oxarchive.Client(api_key="0xa_test", base_url="https://api.example.test")
    client._http._client = httpx.Client(base_url=client._http.base_url, transport=httpx.MockTransport(fail))

    with pytest.raises(OxArchiveError) as caught:
        client.hyperliquid.orderbook.get("BTC")

    assert caught.value.status == 0 and caught.value.error_code is None


def test_core_recent_trades_are_refused_with_the_api_code() -> None:
    client, api = mock_client(lambda p, q: envelope([]))

    for call in (
        lambda: client.hyperliquid.trades.recent("BTC"),
        lambda: asyncio.run(client.hyperliquid.trades.arecent("BTC")),
    ):
        with pytest.raises(OxArchiveError) as caught:
            call()
        assert caught.value.error_code == "unsupported_for_venue" and caught.value.status == 404
        assert "history" in caught.value.message

    assert api.requests == []


@pytest.mark.parametrize(
    "frame",
    [
        {"type": "error", "message": "Unknown channel 'x'.", "error_code": "invalid_parameter"},
        {"type": "error", "message": "Dropped ~40 live lighter_trades messages for BTC", "error_code": "slow_consumer"},
        {"type": "error", "message": "Use wss://api.0xarchive.io/ws for lighter_orderbook", "error_code": "endpoint_unsupported"},
        {"type": "error", "message": "replay.seek is not supported for L4 channels", "error_code": "unsupported_for_venue"},
    ],
)
def test_websocket_errors_expose_error_code(frame: dict[str, Any]) -> None:
    ws = OxArchiveWs(WsOptions(api_key="k"))
    seen: list[Any] = []
    ws.on_message(seen.append)

    ws._handle_message(json.dumps(frame))

    assert isinstance(seen[0], WsError)
    assert seen[0].error_code == frame["error_code"] and seen[0].message == frame["message"]


def test_a_websocket_error_without_a_code_still_parses() -> None:
    assert WsError.model_validate({"type": "error", "message": "x"}).error_code is None


# ===========================================================================
# 3. Pagination
# ===========================================================================


def test_has_more_comes_from_meta() -> None:
    client, _ = mock_client(lambda p, q: _page([], has_more=True, next_cursor="c2"))
    page = client.hyperliquid.funding.history("BTC", start=T_START, end=T_END)
    assert page.has_more is True and page.next_cursor == "c2" and page.meta.has_more is True

    client, _ = mock_client(lambda p, q: _page([], has_more=False))
    page = client.hyperliquid.funding.history("BTC", start=T_START, end=T_END)
    assert page.has_more is False and page.next_cursor is None


def test_has_more_follows_next_cursor_where_the_route_does_not_send_it() -> None:
    client, _ = mock_client(lambda p, q: envelope([], next_cursor="1790640060000"))
    assert client.hyperliquid.orders.flow("BTC", start=T_START, end=T_END).has_more is True

    client, _ = mock_client(lambda p, q: envelope([]))
    assert client.hyperliquid.orders.flow("BTC", start=T_START, end=T_END).has_more is False


def test_cursor_response_derives_its_state() -> None:
    assert CursorResponse(data=[], next_cursor="x").has_more is True
    assert CursorResponse(data=[]).has_more is False
    meta = ResponseMeta(has_more=True, next_cursor="n")
    page = CursorResponse(data=[], meta=meta)
    assert page.has_more is True and page.next_cursor == "n"
    assert CursorResponse(data=[], next_cursor="x", has_more=False).has_more is False


def test_an_empty_final_page_after_a_full_one_stops_the_iterator() -> None:
    pages = [
        _page([CVD_V, CVD_V], has_more=True, next_cursor="c2"),
        _page([], has_more=False),
    ]
    client, api = mock_client(lambda p, q: pages[len(api.requests) - 1])

    buckets = list(client.hyperliquid.cvd.iterate("BTC", start=T_START, end=T_END, limit=2))

    assert len(buckets) == 2 and len(api.requests) == 2
    assert api.calls[1][1]["cursor"] == "c2"


def test_iterators_stop_when_has_more_is_false_even_with_a_cursor() -> None:
    client, api = mock_client(lambda p, q: _page([CVD_V], has_more=False, next_cursor="stale"))
    assert len(list(client.hyperliquid.cvd.iterate("BTC", start=T_START))) == 1
    assert len(api.requests) == 1

    async def collect() -> list[Any]:
        return [b async for b in client.hyperliquid.cvd.aiterate("BTC", start=T_START)]

    assert len(asyncio.run(collect())) == 1 and len(api.requests) == 2


def test_positions_iterators_stop_on_has_more() -> None:
    row = {
        "symbol": "BTC",
        "coin": "BTC",
        "size": "1",
        "side": "long",
        "entry_price": "1",
        "leverage": {"type": "cross", "value": "1"},
        "cum_funding": {"all_time": None, "since_open": None, "since_change": None},
        "liquidation_price_status": "exact",
        "quality": "complete",
    }
    pages = [
        _page([row], has_more=True, next_cursor="p2"),
        _page([row], has_more=False, next_cursor="ignored"),
    ]
    client, api = mock_client(lambda p, q: pages[len(api.requests) - 1])

    rows = list(client.hyperliquid.positions.iterate_history("0xabc", start=T_START, end=T_END))

    assert len(rows) == 2 and len(api.requests) == 2 and api.calls[1][1]["cursor"] == "p2"


# Every paged method returns meta (symbol, venue and has_more included).
PAGED_CALLS: list[tuple[str, Callable[[oxarchive.Client], CursorResponse[Any]]]] = [
    ("orderbook.history", lambda c: c.hyperliquid.orderbook.history("BTC", start=T_START, end=T_END)),
    ("trades.history", lambda c: c.hyperliquid.trades.history("BTC", start=T_START, end=T_END)),
    ("funding.history", lambda c: c.hyperliquid.funding.history("BTC", start=T_START, end=T_END)),
    ("oi.history", lambda c: c.hyperliquid.open_interest.history("BTC", start=T_START, end=T_END)),
    ("candles.history", lambda c: c.hyperliquid.candles.history("BTC", start=T_START, end=T_END)),
    ("liquidations.history", lambda c: c.hyperliquid.liquidations.history("BTC", start=T_START, end=T_END)),
    ("liquidations.volume", lambda c: c.hyperliquid.liquidations.volume("BTC", start=T_START, end=T_END)),
    ("orders.history", lambda c: c.hyperliquid.orders.history("BTC", start=T_START, end=T_END)),
    ("orders.tpsl", lambda c: c.hyperliquid.orders.tpsl("BTC", start=T_START, end=T_END)),
    ("l4.diffs", lambda c: c.hyperliquid.l4_orderbook.diffs("BTC", start=T_START, end=T_END)),
    ("l4.history", lambda c: c.hyperliquid.l4_orderbook.history("BTC", start=T_START, end=T_END)),
    ("l2.history", lambda c: c.hyperliquid.l2_orderbook.history("BTC", start=T_START, end=T_END)),
    ("l2.diffs", lambda c: c.hyperliquid.l2_orderbook.diffs("BTC", start=T_START, end=T_END)),
    ("l3.history", lambda c: c.lighter.l3_orderbook.history("BTC", start=T_START, end=T_END)),
    ("prices", lambda c: c.hyperliquid.get_price_history("BTC", start=T_START, end=T_END)),
    ("spot.twap", lambda c: c.spot.twap.history("HYPE-USDC", start=T_START, end=T_END)),
    ("spot.orders", lambda c: c.spot.orders.history("HYPE-USDC", start=T_START, end=T_END)),
    ("hip4.outcomes", lambda c: c.hyperliquid.hip4.outcomes.list()),
    ("hip4.questions", lambda c: c.hyperliquid.hip4.questions.list()),
    ("breadth.history", lambda c: c.hyperliquid.hip3.breadth.history()),
]


@pytest.mark.parametrize("name, call", PAGED_CALLS, ids=[n for n, _ in PAGED_CALLS])
def test_every_paged_method_returns_meta_and_has_more(
    name: str, call: Callable[[oxarchive.Client], CursorResponse[Any]]
) -> None:
    client, _ = mock_client(
        lambda p, q: _page([], has_more=True, next_cursor="n", symbol="BTC", venue="hyperliquid")
    )

    page = call(client)

    assert page.has_more is True and page.next_cursor == "n"
    assert isinstance(page.meta, ResponseMeta)
    assert (page.meta.symbol, page.meta.venue, page.meta.request_id) == ("BTC", "hyperliquid", "req-test")


# ===========================================================================
# 4. meta.symbol / meta.venue and response_meta
# ===========================================================================


def test_venue_set() -> None:
    assert VENUES == get_args(Venue) == ("hyperliquid", "hip3", "hip4", "spot", "lighter", "rh-lighter")


BOOK = {"coin": "xyz:TSLA", "timestamp": "2026-09-29T00:00:00Z", "bids": [], "asks": []}

RECORD_CALLS: list[tuple[str, Any, Callable[[oxarchive.Client], Any]]] = [
    ("orderbook", BOOK, lambda c: c.hyperliquid.hip3.orderbook.get("xyz:TSLA")),
    ("funding", {"coin": "BTC", "timestamp": "2026-09-29T00:00:00Z", "funding_rate": "0.0001"}, lambda c: c.hyperliquid.funding.current("BTC")),
    ("oi", {"coin": "BTC", "timestamp": "2026-09-29T00:00:00Z", "open_interest": "1"}, lambda c: c.hyperliquid.open_interest.current("BTC")),
    ("freshness", {"coin": "BTC", "exchange": "hyperliquid", "measured_at": "2026-09-29T00:00:00Z", "orderbook": {}, "trades": {}, "funding": {}, "open_interest": {}}, lambda c: c.hyperliquid.get_freshness("BTC")),
    ("oracle", ORACLE_V, lambda c: c.hyperliquid.hip3.oracle.external_price("km:US500")),
]


@pytest.mark.parametrize("name, data, call", RECORD_CALLS, ids=[n for n, _, _ in RECORD_CALLS])
def test_records_returned_on_their_own_carry_the_response_meta(
    name: str, data: Any, call: Callable[[oxarchive.Client], Any]
) -> None:
    client, _ = mock_client(lambda p, q: _subject(data, "xyz:TSLA", "hip3"))

    record = call(client)

    assert isinstance(record.response_meta, ResponseMeta)
    assert (record.response_meta.symbol, record.response_meta.venue) == ("xyz:TSLA", "hip3")
    assert record.response_meta.request_id == "req-test"
    # The meta is not part of the record's data.
    assert "response_meta" not in record.model_dump() and "_response_meta" not in record.model_dump()


def test_async_records_carry_the_response_meta() -> None:
    client, _ = mock_client(lambda p, q: _subject(BOOK, "xyz:TSLA", "hip3"))
    book = asyncio.run(client.hyperliquid.hip3.orderbook.aget("xyz:TSLA"))
    assert book.response_meta.venue == "hip3"


def test_rows_inside_a_list_have_no_response_meta() -> None:
    client, _ = mock_client(lambda p, q: _page([BOOK], has_more=False, symbol="xyz:TSLA", venue="hip3"))
    page = client.hyperliquid.hip3.orderbook.history("xyz:TSLA", start=T_START, end=T_END)
    assert page.data[0].response_meta is None and page.meta.venue == "hip3"
    assert OrderBook.model_validate(BOOK).response_meta is None


# ===========================================================================
# 5. Capabilities
# ===========================================================================

CAPABILITY_ROWS = [
    {
        "venue": "spot",
        "datatype": "l4_diffs",
        "rest_routes": ["/v1/hyperliquid/spot/orderbook/{symbol}/l4/diffs"],
        "ws_channels": ["spot_l4_diffs"],
        "live": True,
        "replay": True,
        "available_from": "2026-03-11T01:03:00.000Z",
        "cadence": "event",
        "page_limit": 10000,
        "intervals": [],
        "notes": "WebSocket replay is bulk (speed is ignored) and single-channel only.",
    },
    {
        "venue": "hyperliquid",
        "datatype": "summary",
        "rest_routes": ["/v1/hyperliquid/summary/{symbol}"],
        "ws_channels": [],
        "live": False,
        "replay": False,
        "available_from": None,
        "cadence": "snapshot",
        "page_limit": None,
        "intervals": [],
        "notes": None,
    },
]


def test_capabilities_returns_typed_rows() -> None:
    client, api = mock_client(lambda p, q: envelope(CAPABILITY_ROWS))

    rows = client.capabilities()

    assert api.calls == [("/v1/capabilities", {})]
    assert all(isinstance(r, Capability) for r in rows)
    spot = rows[0]
    assert (spot.venue, spot.datatype, spot.live, spot.replay) == ("spot", "l4_diffs", True, True)
    assert spot.available_from == datetime(2026, 3, 11, 1, 3, tzinfo=timezone.utc)
    assert spot.page_limit == 10000 and spot.ws_channels == ["spot_l4_diffs"]
    assert rows[1].available_from is None and rows[1].page_limit is None
    assert [r.datatype for r in asyncio.run(client.acapabilities())] == ["l4_diffs", "summary"]


# ===========================================================================
# 6. Parameters the API applies
# ===========================================================================

TRADE = {"coin": "BTC", "side": "B", "price": "1", "size": "1", "timestamp": "2026-09-29T00:00:00Z"}

VENUE_TRADES: list[tuple[str, Callable[[oxarchive.Client], TradesResource], str]] = [
    ("hyperliquid", lambda c: c.hyperliquid.trades, "/v1/hyperliquid/trades/BTC"),
    ("hip3", lambda c: c.hyperliquid.hip3.trades, "/v1/hyperliquid/hip3/trades/xyz:TSLA"),
    ("hip4", lambda c: c.hyperliquid.hip4.trades, "/v1/hyperliquid/hip4/trades/0"),
    ("spot", lambda c: c.spot.trades, "/v1/hyperliquid/spot/trades/HYPE-USDC"),
    ("lighter", lambda c: c.lighter.trades, "/v1/lighter/trades/BTC"),
    ("rh-lighter", lambda c: c.rh_lighter.trades, "/v1/rh-lighter/trades/BTC"),
]
SYMBOLS = {"hyperliquid": "BTC", "hip3": "xyz:TSLA", "hip4": "#0", "spot": "HYPE-USDC", "lighter": "BTC", "rh-lighter": "BTC"}


@pytest.mark.parametrize("venue, resource, path", VENUE_TRADES, ids=[v for v, _, _ in VENUE_TRADES])
def test_trades_side_is_sent_on_every_venue(
    venue: str, resource: Callable[[oxarchive.Client], TradesResource], path: str
) -> None:
    client, api = mock_client(lambda p, q: envelope([TRADE]))
    trades = resource(client)
    symbol = SYMBOLS[venue]

    trades.list(symbol, start=T_START, end=T_END, side="buy")
    trades.history(symbol, start=T_START, end=T_END, side="sell", limit=5)
    asyncio.run(trades.alist(symbol, start=T_START, end=T_END, side="buy"))
    asyncio.run(trades.ahistory(symbol, start=T_START, end=T_END, side="sell"))

    assert [c[0] for c in api.calls] == [path] * 4
    assert [c[1]["side"] for c in api.calls] == ["buy", "sell", "buy", "sell"]
    assert api.calls[1][1] == {"start": str(T_START), "end": str(T_END), "limit": "5", "side": "sell"}

    if venue != "hyperliquid":
        trades.recent(symbol, limit=10, side="sell")
        asyncio.run(trades.arecent(symbol, side="buy"))
        assert api.calls[-2] == (f"{path}/recent", {"limit": "10", "side": "sell"})
        assert api.calls[-1] == (f"{path}/recent", {"side": "buy"})


def test_trades_without_side_send_no_side() -> None:
    client, api = mock_client(lambda p, q: envelope([TRADE]))
    client.hyperliquid.trades.history("BTC", start=T_START, end=T_END)
    client.lighter.trades.recent("BTC")
    assert all("side" not in q for _, q in api.calls)


def test_hip4_flat_trade_helpers_pass_side_through() -> None:
    client, api = mock_client(lambda p, q: envelope([TRADE]))
    client.hyperliquid.hip4.get_trades("0", start=T_START, end=T_END, side="buy")
    client.hyperliquid.hip4.get_trades_recent("0", limit=3, side="sell")
    assert api.calls[0][1]["side"] == "buy"
    assert api.calls[1] == ("/v1/hyperliquid/hip4/trades/0/recent", {"limit": "3", "side": "sell"})


@pytest.mark.parametrize(
    "orders, path",
    [
        (lambda c: c.hyperliquid.orders, "/v1/hyperliquid/orders/BTC/history"),
        (lambda c: c.hyperliquid.hip3.orders, "/v1/hyperliquid/hip3/orders/BTC/history"),
        (lambda c: c.hyperliquid.hip4.orders, "/v1/hyperliquid/hip4/orders/BTC/history"),
    ],
    ids=["hyperliquid", "hip3", "hip4"],
)
def test_order_history_sends_triggered(orders: Callable[[oxarchive.Client], Any], path: str) -> None:
    client, api = mock_client(lambda p, q: envelope([]))

    orders(client).history("BTC", start=T_START, end=T_END, triggered=True)
    asyncio.run(orders(client).ahistory("BTC", start=T_START, end=T_END, triggered=False))
    orders(client).history("BTC", start=T_START, end=T_END)

    assert [c[0] for c in api.calls] == [path] * 3
    assert api.calls[0][1]["triggered"] == "true"
    assert api.calls[1][1]["triggered"] == "false"
    assert "triggered" not in api.calls[2][1]


@pytest.mark.parametrize(
    "book, path",
    [
        (lambda c: c.hyperliquid.l2_orderbook, "/v1/hyperliquid/orderbook/BTC/l2/history"),
        (lambda c: c.hyperliquid.hip3.l2_orderbook, "/v1/hyperliquid/hip3/orderbook/BTC/l2/history"),
    ],
    ids=["hyperliquid", "hip3"],
)
def test_full_depth_history_sends_depth(book: Callable[[oxarchive.Client], Any], path: str) -> None:
    client, api = mock_client(lambda p, q: envelope([]))

    book(client).history("BTC", start=T_START, end=T_END, depth=50)
    asyncio.run(book(client).ahistory("BTC", start=T_START, end=T_END, depth=3))

    assert api.calls == [
        (path, {"start": str(T_START), "end": str(T_END), "depth": "50"}),
        (path, {"start": str(T_START), "end": str(T_END), "depth": "3"}),
    ]


@pytest.mark.parametrize(
    "book, path",
    [
        (lambda c: c.hyperliquid.hip3.orderbook, "/v1/hyperliquid/hip3/orderbook/xyz:TSLA/history"),
        (lambda c: c.hyperliquid.hip4.orderbook, "/v1/hyperliquid/hip4/orderbook/67200/history"),
        (lambda c: c.spot.orderbook, "/v1/hyperliquid/spot/orderbook/HYPE-USDC/history"),
    ],
    ids=["hip3", "hip4", "spot"],
)
def test_order_book_history_sends_depth_on_hip3_hip4_and_spot(
    book: Callable[[oxarchive.Client], Any], path: str
) -> None:
    client, api = mock_client(lambda p, q: envelope([]))
    symbol = path.split("/orderbook/")[1].split("/")[0]
    if symbol == "67200":
        symbol = "#67200"

    book(client).history(symbol, start=T_START, end=T_END, depth=5)

    assert api.calls == [(path, {"start": str(T_START), "end": str(T_END), "depth": "5"})]


def test_l3_history_granularity_stays_refused() -> None:
    client, api = mock_client(lambda p, q: envelope([]))

    with pytest.raises(TypeError, match="does not take 'granularity'"):
        client.lighter.l3_orderbook.history("BTC", start=T_START, end=T_END, granularity="10s")
    with pytest.raises(TypeError, match="does not take 'granularity'"):
        asyncio.run(client.lighter.l3_orderbook.ahistory("BTC", start=T_START, end=T_END, granularity="1s"))

    assert api.requests == []


# ===========================================================================
# 7. WebSocket replay rules mirror capabilities
# ===========================================================================

# ``ws_channels``, ``live`` and ``replay`` of every row of GET /v1/capabilities
# that names a channel, as served on 2026-10-04, plus the ``mempool`` row.
CAPABILITY_CHANNELS: dict[str, tuple[str, bool, bool]] = {
    "orderbook": ("hyperliquid", True, True),
    "orderbook_full": ("hyperliquid", True, True),
    "l4_diffs": ("hyperliquid", True, True),
    "l4_orders": ("hyperliquid", True, True),
    "trades": ("hyperliquid", True, True),
    "candles": ("hyperliquid", False, True),
    "funding": ("hyperliquid", True, True),
    "open_interest": ("hyperliquid", True, True),
    "liquidations": ("hyperliquid", True, True),
    "ticker": ("hyperliquid", True, False),
    "all_tickers": ("hyperliquid", True, False),
    "mempool": ("hyperliquid", True, False),
    "hip3_orderbook": ("hip3", True, True),
    "hip3_orderbook_full": ("hip3", True, True),
    "hip3_l4_diffs": ("hip3", True, True),
    "hip3_l4_orders": ("hip3", True, True),
    "hip3_trades": ("hip3", True, True),
    "hip3_candles": ("hip3", False, True),
    "hip3_funding": ("hip3", True, True),
    "hip3_open_interest": ("hip3", True, True),
    "hip3_liquidations": ("hip3", True, True),
    "hip4_orderbook": ("hip4", False, True),
    "hip4_l4_diffs": ("hip4", True, True),
    "hip4_l4_orders": ("hip4", True, True),
    "hip4_trades": ("hip4", True, True),
    "hip4_open_interest": ("hip4", False, True),
    "spot_orderbook": ("spot", True, False),
    "spot_l4_diffs": ("spot", True, True),
    "spot_l4_orders": ("spot", True, True),
    "spot_trades": ("spot", True, False),
    "lighter_orderbook": ("lighter", True, True),
    "lighter_l3_orderbook": ("lighter", False, True),
    "lighter_trades": ("lighter", True, True),
    "lighter_candles": ("lighter", False, True),
    "lighter_funding": ("lighter", True, True),
    "lighter_open_interest": ("lighter", True, True),
    "rh_lighter_orderbook": ("rh-lighter", True, True),
    "rh_lighter_trades": ("rh-lighter", True, True),
    "rh_lighter_candles": ("rh-lighter", False, True),
    "rh_lighter_funding": ("rh-lighter", True, True),
    "rh_lighter_open_interest": ("rh-lighter", True, True),
}


# Channels the SDK names that no capabilities row lists, with the ``live`` and
# ``replay`` of their datatype's row: spot TWAP is served over REST only.
REST_ONLY_CHANNELS: dict[str, tuple[str, bool, bool]] = {
    "spot_twap": ("spot", False, False),
}


def test_channel_table_mirrors_capabilities() -> None:
    assert set(WS_CHANNELS) == set(CAPABILITY_CHANNELS) | set(REST_ONLY_CHANNELS)
    assert set(WS_CHANNELS) == set(get_args(WsChannel))
    for channel, (venue, live, replay) in {**CAPABILITY_CHANNELS, **REST_ONLY_CHANNELS}.items():
        spec = WS_CHANNELS[channel]
        assert (spec.venue, spec.live, spec.replay) == (venue, live, replay), channel


def test_only_mempool_names_an_endpoint_and_plans() -> None:
    # The mempool row of /v1/capabilities is the only one with ``ws_endpoint``
    # and ``plans``; every other channel is on every endpoint and every plan.
    restricted = {
        channel: (spec.ws_endpoint, spec.plans)
        for channel, spec in WS_CHANNELS.items()
        if spec.ws_endpoint is not None or spec.plans is not None
    }
    assert restricted == {
        "mempool": ("wss://stream.0xarchive.io/ws", ("pro", "scale", "enterprise"))
    }


def test_bulk_replay_channels_are_every_l4_and_full_depth_channel() -> None:
    assert L4_REPLAY_CHANNELS == {c for c in WS_CHANNELS if "_l4_" in c or c.startswith("l4_")}
    assert BULK_REPLAY_CHANNELS == L4_REPLAY_CHANNELS | {"orderbook_full", "hip3_orderbook_full"}
    assert L4_REPLAY_CHANNELS <= REPLAY_CHANNELS and L4_REPLAY_CHANNELS <= LIVE_CHANNELS
    assert L4_LIVE_ONLY_CHANNELS == frozenset()


class _Recorder:
    def __init__(self) -> None:
        self.sent: list[dict[str, Any]] = []

    async def __call__(self, message: dict[str, Any]) -> None:
        self.sent.append(message)


def _offline() -> tuple[OxArchiveWs, _Recorder]:
    ws = OxArchiveWs(WsOptions(api_key="k"))
    recorder = _Recorder()
    setattr(ws, "_send", recorder)
    return ws, recorder


@pytest.mark.parametrize("channel", sorted(BULK_REPLAY_CHANNELS))
def test_every_bulk_channel_replays_on_its_own(channel: str) -> None:
    ws, recorder = _offline()

    asyncio.run(ws.replay(cast(WsChannel, channel), "BTC", start=T_START, end=T_END, speed=5))

    assert recorder.sent == [
        {"op": "replay", "channel": channel, "symbol": "BTC", "start": T_START, "speed": 5, "end": T_END}
    ]
    with pytest.raises(ValueError, match="single-channel only"):
        asyncio.run(ws.multi_replay(["trades", cast(WsChannel, channel)], "BTC", start=T_START))
    assert len(recorder.sent) == 1


@pytest.mark.parametrize("channel", sorted(c for c, s in WS_CHANNELS.items() if not s.replay))
def test_channels_without_replay_are_refused_before_sending(channel: str) -> None:
    ws, recorder = _offline()

    with pytest.raises(ValueError, match="does not support historical replay"):
        asyncio.run(ws.replay(cast(WsChannel, channel), "BTC", start=T_START))
    with pytest.raises(ValueError, match="does not support historical replay"):
        asyncio.run(ws.multi_replay([cast(WsChannel, channel)], "BTC", start=T_START))

    assert recorder.sent == []


@pytest.mark.parametrize("channel", ["candles", "hip3_candles"])
def test_replay_only_candle_channels_are_refused_for_live_subscription(channel: str) -> None:
    ws = OxArchiveWs(WsOptions(api_key="k"))

    with pytest.raises(ValueError, match="supports replay, not live subscriptions"):
        ws.subscribe(cast(WsChannel, channel), "BTC")
    with pytest.raises(ValueError, match="supports replay, not live subscriptions"):
        asyncio.run(ws.subscribe_async(cast(WsChannel, channel), "BTC"))

    assert ws._subscriptions == set()


def test_live_channels_subscribe_and_replayable_channels_multi_replay() -> None:
    ws, recorder = _offline()

    asyncio.run(ws.multi_replay(["hip3_orderbook", "hip3_trades", "hip3_funding", "hip3_open_interest"], "xyz:TSLA", start=T_START))

    assert recorder.sent[0]["channels"] == ["hip3_orderbook", "hip3_trades", "hip3_funding", "hip3_open_interest"]
    for channel in sorted(LIVE_CHANNELS):
        ws.subscribe(cast(WsChannel, channel), None if channel == "all_tickers" else "BTC")
    assert len(ws._subscriptions) == len(LIVE_CHANNELS)


@pytest.mark.parametrize("channel", ["hip4_orderbook", "hip4_open_interest"])
def test_hip4_book_and_open_interest_replay_but_do_not_stream(channel: str) -> None:
    ws, recorder = _offline()

    with pytest.raises(ValueError, match="supports replay, not live subscriptions"):
        ws.subscribe(cast(WsChannel, channel), "#82260")
    asyncio.run(ws.replay(cast(WsChannel, channel), "#82260", start=T_START, end=T_END))

    assert ws._subscriptions == set()
    assert [m["channel"] for m in recorder.sent] == [channel]


def test_spot_twap_neither_streams_nor_replays() -> None:
    ws, recorder = _offline()

    for call in (
        lambda: ws.subscribe_spot_twap("HYPE-USDC"),
        lambda: asyncio.run(ws.subscribe_async("spot_twap", "HYPE-USDC")),
        lambda: asyncio.run(ws.replay("spot_twap", "HYPE-USDC", start=T_START)),
    ):
        with pytest.raises(ValueError, match="served over REST"):
            call()

    assert ws._subscriptions == set() and recorder.sent == []


def test_a_channel_missing_from_the_table_is_left_to_the_server() -> None:
    ws, recorder = _offline()
    asyncio.run(ws.replay(cast(WsChannel, "future_channel"), "BTC", start=T_START))
    assert recorder.sent[0]["channel"] == "future_channel"


def test_bulk_replay_frames_reach_the_l4_handlers() -> None:
    ws = OxArchiveWs(WsOptions(api_key="k"))
    snapshots: list[tuple[str, str]] = []
    batches: list[tuple[str, int]] = []
    ws.on_l4_snapshot(lambda channel, coin, data: snapshots.append((channel, coin)))
    ws.on_l4_batch(lambda channel, coin, events: batches.append((channel, len(events))))

    ws._handle_message(json.dumps({"type": "l4_snapshot", "channel": "spot_l4_diffs", "coin": "PURR-USDC", "symbol": "PURR-USDC", "last_block_number": 1165417484, "timestamp": 1790686949346, "data": {"bids": [], "asks": []}}))
    ws._handle_message(json.dumps({"type": "l4_batch", "channel": "spot_l4_diffs", "coin": "PURR-USDC", "symbol": "PURR-USDC", "data": [{"block_number": 1165417487, "seq": 573, "diff_type": "remove"}]}))
    ws._handle_message(json.dumps({"type": "l4_batch", "channel": "hip3_orderbook_full", "coin": "xyz:TSLA", "symbol": "xyz:TSLA", "data": [{"side": "B", "px": 354.4, "sz": 0.0, "n": 0, "bn": 1}]}))

    assert snapshots == [("spot_l4_diffs", "PURR-USDC")]
    assert batches == [("spot_l4_diffs", 1), ("hip3_orderbook_full", 1)]


# ===========================================================================
# 8. Verbs
# ===========================================================================


def test_history_aliases_call_the_same_routes() -> None:
    assert TradesResource.history is TradesResource.list
    assert TradesResource.ahistory is TradesResource.alist
    client, api = mock_client(lambda p, q: envelope([]))

    client.spot.twap.history("HYPE-USDC", start=T_START, end=T_END)
    client.spot.twap.by_symbol("HYPE-USDC", start=T_START, end=T_END)
    asyncio.run(client.spot.twap.ahistory("HYPE-USDC"))
    client.hyperliquid.hip4.get_price_history("0", start=T_START, end=T_END)
    client.hyperliquid.hip4.get_prices("0", start=T_START, end=T_END)
    asyncio.run(client.hyperliquid.hip4.aget_price_history("0"))

    paths = [c[0] for c in api.calls]
    assert paths[:3] == ["/v1/hyperliquid/spot/twap/HYPE-USDC"] * 3
    assert paths[3:] == ["/v1/hyperliquid/hip4/prices/0"] * 3


def test_existing_names_keep_working() -> None:
    client, api = mock_client(lambda p, q: envelope([]))
    client.hyperliquid.trades.list("BTC", start=T_START, end=T_END)
    asyncio.run(client.lighter.trades.alist("BTC", start=T_START, end=T_END))
    client.trades.list("BTC", start=T_START, end=T_END)  # legacy namespace
    assert [c[0] for c in api.calls] == [
        "/v1/hyperliquid/trades/BTC",
        "/v1/lighter/trades/BTC",
        "/v1/hyperliquid/trades/BTC",
    ]


# ===========================================================================
# 9. Venue name
# ===========================================================================


def test_the_venue_is_named_lighter_everywhere_shipped() -> None:
    shipped = [ROOT / "README.md", ROOT / "pyproject.toml", *sorted((ROOT / "oxarchive").rglob("*.py"))]
    for path in shipped:
        text = path.read_text()
        assert "Lighter.xyz" not in text and "lighterxyz" not in text.lower(), path
