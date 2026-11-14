"""Trade intent, USDC flows, moving-average breadth and positioning.

The response bodies in ``fixtures/derived`` were recorded from the API
(version 2026-10-01) with a Pro key, and with a Free key for the 403s. Each
file names the request that produced it. ``replay`` answers a request only
when its path and query are exactly the recorded ones, so these tests check
what the SDK sends as well as how it parses the answer. The positioning and
capabilities bodies are trimmed (see each file's ``note``).
"""

from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import httpx
import pytest
from _mock_api import mock_client

import oxarchive
from oxarchive import (
    BreadthMaReading,
    CursorResponse,
    OxArchiveError,
    PlanRequiredError,
    PositioningReading,
    TradeIntentBucket,
    UsdcFlowEvent,
    UsdcFlowVolumeBucket,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "derived"

D0 = 1793577600000  # 2026-11-02T00:00:00Z
H = 3_600_000


def fixture(name: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((FIXTURES / f"{name}.json").read_text())
    return data


def _answer(rec: dict[str, Any]) -> Any:
    if rec["status"] == 200:
        return rec["body"]
    return httpx.Response(rec["status"], json=rec["body"])


def replay(*names: str) -> Callable[[str, dict[str, str]], Any]:
    """Answer each recorded request with its recorded body; refuse anything else."""
    table: dict[tuple[str, tuple[tuple[str, str], ...]], dict[str, Any]] = {}
    for name in names:
        rec = fixture(name)
        query = tuple(sorted((k, str(v)) for k, v in rec["request"]["query"].items()))
        table[(rec["request"]["path"], query)] = rec

    def respond(path: str, query: dict[str, str]) -> Any:
        key = (path, tuple(sorted(query.items())))
        if key not in table:
            raise AssertionError(f"unrecorded request: {path} {query}")
        return _answer(table[key])

    return respond


def body_of(name: str) -> Callable[[str, dict[str, str]], Any]:
    """Answer every request with one recorded body, whatever was asked."""
    rec = fixture(name)
    return lambda path, query: _answer(rec)


def utc(text: str) -> datetime:
    return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(timezone.utc)


SPARSE = [f"usdc_flows_events_sparse_page{i}" for i in range(1, 5)]
SPARSE_START = 1782864000000  # 2026-07-01T00:00:00Z
SPARSE_END = 1793318400000  # 2026-10-30T00:00:00Z


# ---------------------------------------------------------------------------
# USDC flows
# ---------------------------------------------------------------------------


def test_usdc_flow_events_page_through_a_bridge_batch() -> None:
    client, api = mock_client(replay("usdc_flows_events_page1", "usdc_flows_events_page2"))

    first = client.hyperliquid.usdc_flows.history(start=D0, end=D0 + H, limit=3)
    second = client.hyperliquid.usdc_flows.history(
        start=D0, end=D0 + H, limit=3, cursor=first.next_cursor
    )

    assert isinstance(first, CursorResponse)
    assert first.has_more is True and first.next_cursor == "1793577600062_1205759951_18"
    event = first.data[0]
    assert isinstance(event, UsdcFlowEvent)
    assert event.id == "1205759951:16"
    assert event.kind == "evm_in"
    assert event.timestamp == utc("2026-11-02T00:00:00.062Z")
    assert event.timestamp_ms == 1793577600062
    assert event.user == "0x6b9e773128f453f5c2c60935ee2de2cbc5390a24"
    assert event.tx_hash is not None and event.tx_hash.startswith("0x")
    assert (event.block_number, event.event_index) == (1205759951, 16)
    assert event.fee_usd == 0.0 and event.amount_usd == 0.0001
    # The page boundary falls inside one block: ids continue, none repeats.
    ids = [e.id for e in first.data + second.data]
    assert ids == [
        "1205759951:16",
        "1205759951:17",
        "1205759951:18",
        "1205759951:19",
        "1205759962:0",
        "1205759962:1",
    ]
    assert [path for path, _ in api.calls] == ["/v1/hyperliquid/usdc-flows"] * 2
    assert first.meta is not None and first.meta.request_id


def test_usdc_flow_event_filters_are_sent() -> None:
    client, api = mock_client(replay("usdc_flows_events_filtered"))

    page = client.hyperliquid.usdc_flows.history(
        start=datetime(2026, 11, 2),
        end="2026-11-03T00:00:00Z",
        min_usd=1000000,
        kind="withdraw",
        limit=5,
    )

    assert api.calls == [
        (
            "/v1/hyperliquid/usdc-flows",
            {
                "start": str(D0),
                "end": str(D0 + 24 * H),
                "min_usd": "1000000",
                "kind": "withdraw",
                "limit": "5",
            },
        )
    ]
    assert len(page.data) == 5
    assert all(e.kind == "withdraw" and e.amount_usd >= 1_000_000 for e in page.data)
    assert all(e.fee_usd == 1.0 for e in page.data)


def test_usdc_flow_iterator_walks_empty_pages_until_the_cursor_ends() -> None:
    client, api = mock_client(replay(*SPARSE))

    events = list(
        client.hyperliquid.usdc_flows.iterate(
            start=SPARSE_START, end=SPARSE_END, min_usd=100000000000, limit=10
        )
    )

    # Three empty pages carry a cursor; only the fourth ends the walk.
    assert events == []
    assert len(api.calls) == 4
    cursors = [q.get("cursor") for _, q in api.calls]
    assert cursors == [
        None,
        "1785542399999_18446744073709551615_4294967295",
        "1788220799998_18446744073709551615_4294967295",
        "1790899199997_18446744073709551615_4294967295",
    ]
    for _, query in api.calls:
        assert query["start"] == str(SPARSE_START) and query["end"] == str(SPARSE_END)
        assert query["min_usd"] == "100000000000" and query["limit"] == "10"


def test_usdc_flow_iterator_async_walks_empty_pages() -> None:
    client, api = mock_client(replay(*SPARSE))

    async def run() -> list[UsdcFlowEvent]:
        return [
            e
            async for e in client.hyperliquid.usdc_flows.aiterate(
                start=SPARSE_START, end=SPARSE_END, min_usd=100000000000, limit=10
            )
        ]

    assert asyncio.run(run()) == []
    assert len(api.calls) == 4


def test_a_single_empty_page_with_a_cursor_is_not_the_last() -> None:
    client, _ = mock_client(replay(SPARSE[0]))

    page = client.hyperliquid.usdc_flows.history(
        start=SPARSE_START, end=SPARSE_END, min_usd=100000000000, limit=10
    )

    assert page.data == [] and page.has_more is True and page.next_cursor is not None


def test_usdc_flow_volume_pages_and_parses_buckets() -> None:
    client, api = mock_client(replay("usdc_flows_volume_page1", "usdc_flows_volume_page2"))

    first = client.hyperliquid.usdc_flows.volume(start=D0, end=D0 + 6 * H, interval="1h", limit=3)
    second = client.hyperliquid.usdc_flows.volume(
        start=D0, end=D0 + 6 * H, interval="1h", limit=3, cursor=first.next_cursor
    )

    bucket = first.data[0]
    assert isinstance(bucket, UsdcFlowVolumeBucket)
    assert bucket.timestamp == utc("2026-11-02T00:00:00Z") and bucket.timestamp_ms == D0
    assert (bucket.deposit_count, bucket.withdraw_count) == (30, 120)
    assert (bucket.evm_in_count, bucket.evm_out_count) == (5069, 118)
    assert bucket.net_usd == pytest.approx(
        bucket.deposit_usd + bucket.evm_in_usd - bucket.withdraw_usd - bucket.evm_out_usd, abs=0.02
    )
    assert first.next_cursor == "1793584800000"
    assert [b.timestamp_ms for b in second.data] == [D0 + 3 * H, D0 + 4 * H, D0 + 5 * H]
    assert api.calls[0] == (
        "/v1/hyperliquid/usdc-flows/volume",
        {"start": str(D0), "end": str(D0 + 6 * H), "interval": "1h", "limit": "3"},
    )


def test_usdc_flow_volume_iterator_follows_the_cursor() -> None:
    recorded = replay("usdc_flows_volume_page1", "usdc_flows_volume_page2")
    # The window holds seven hourly buckets; the third page was not recorded,
    # so the test answers it with a final page of one bucket.
    last = fixture("usdc_flows_volume_page2")["body"]
    final = {
        "success": True,
        "data": [
            {**last["data"][0], "timestamp": "2026-11-02T06:00:00.000Z", "timestamp_ms": D0 + 6 * H}
        ],
        "meta": {"count": 1, "request_id": "final-page", "has_more": False},
    }

    def respond(path: str, query: dict[str, str]) -> Any:
        if query.get("cursor") == "1793595600000":
            return final
        return recorded(path, query)

    client, api = mock_client(respond)

    buckets = list(
        client.hyperliquid.usdc_flows.iterate_volume(
            start=D0, end=D0 + 6 * H, interval="1h", limit=3
        )
    )

    assert [b.timestamp_ms for b in buckets] == [D0 + i * H for i in range(7)]
    assert len(api.calls) == 3


def test_usdc_flows_validate_before_sending() -> None:
    client, api = mock_client(lambda path, q: pytest.fail("no request expected"))
    flows = client.hyperliquid.usdc_flows

    with pytest.raises(ValueError, match="kind"):
        flows.history(kind="bridge")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="min_usd"):
        flows.history(min_usd=-1)
    with pytest.raises(ValueError, match="min_usd"):
        flows.history(min_usd=2e12)
    with pytest.raises(ValueError, match="limit"):
        flows.history(limit=1001)
    with pytest.raises(ValueError, match="interval"):
        flows.volume(interval="2h")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="limit"):
        flows.volume(limit=0)
    with pytest.raises(TypeError):
        flows.volume(min_usd=5)  # type: ignore[call-arg]
    assert api.requests == []


def test_usdc_flows_before_coverage_carry_the_notice() -> None:
    client, _ = mock_client(replay("usdc_flows_events_before_coverage"))

    page = client.hyperliquid.usdc_flows.history(start="2025-01-01", end="2025-01-02")

    assert page.data == [] and page.has_more is False
    assert page.meta is not None
    assert page.meta.coverage_from == utc("2025-09-27T09:33:00Z")
    assert page.meta.notice is not None and "2025-09-27 09:33 UTC" in page.meta.notice


def test_usdc_flows_are_core_only() -> None:
    client = oxarchive.Client(api_key="0xa_test")
    assert not hasattr(client.hyperliquid.hip3, "usdc_flows")


# ---------------------------------------------------------------------------
# Trade intent
# ---------------------------------------------------------------------------


def test_trade_intent_hourly_buckets_parse_and_page() -> None:
    client, api = mock_client(replay("trade_intent_btc_1h_page1", "trade_intent_btc_1h_page2"))

    first = client.hyperliquid.trade_intent.history(
        "btc", start=D0, end=D0 + 5 * H, interval="1h", limit=3
    )

    assert api.calls[0] == (
        "/v1/hyperliquid/trade-intent/BTC",
        {"start": str(D0), "end": str(D0 + 5 * H), "interval": "1h", "limit": "3"},
    )
    bucket = first.data[0]
    assert isinstance(bucket, TradeIntentBucket)
    assert bucket.timestamp == utc("2026-11-02T00:00:00Z") and bucket.timestamp_ms == D0
    assert bucket.close == 78061.0 and bucket.price_source == "mark"
    assert bucket.open_long == 27144995.59 and bucket.mm_usd == 66752421.84
    assert (bucket.winners_count, bucket.losers_count) == (4, 10)
    assert bucket.winners_net == 199258865.1 and bucket.losers_net == -257924170.78
    assert bucket.quality == "ok" and bucket.method == "who/3"
    assert bucket.is_final is True and bucket.preliminary is False
    assert bucket.preliminary_from is None and bucket.preliminary_from_ms is None
    assert first.meta is not None
    assert (first.meta.symbol, first.meta.venue) == ("BTC", "hyperliquid")
    assert first.meta.built_through == utc("2026-11-04T19:00:00Z")
    assert first.next_cursor == "1793588400000"

    walked = list(
        client.hyperliquid.trade_intent.iterate(
            "BTC", start=D0, end=D0 + 5 * H, interval="1h", limit=3
        )
    )
    assert [b.timestamp_ms for b in walked] == [D0 + i * H for i in range(6)]


def test_trade_intent_second_buckets_have_no_close_or_cohort_snapshot() -> None:
    rec = fixture("trade_intent_btc_1s")
    client, _ = mock_client(replay("trade_intent_btc_1s"))
    q = rec["request"]["query"]

    page = client.hyperliquid.trade_intent.history(
        "BTC", start=q["start"], end=q["end"], interval="1s"
    )

    bucket = page.data[0]
    assert bucket.close is None and bucket.price_source is None
    assert bucket.winners_net is None and bucket.winners_gross is None
    assert bucket.losers_net is None and bucket.losers_gross is None
    assert bucket.winners_count is None and bucket.losers_count is None
    assert bucket.winners_flow == 0.0 and bucket.losers_flow == 0.02
    assert bucket.preliminary is True and bucket.is_final is False
    assert bucket.preliminary_from == bucket.timestamp
    assert bucket.preliminary_from_ms == bucket.timestamp_ms
    assert page.meta is not None and page.meta.preliminary_row_count == 3


def test_trade_intent_open_hour_minutes_are_preliminary() -> None:
    rec = fixture("trade_intent_btc_1m_live")
    q = rec["request"]["query"]
    client, _ = mock_client(replay("trade_intent_btc_1m_live"))

    page = client.hyperliquid.trade_intent.history(
        "BTC", start=q["start"], end=q["end"], interval="1m", limit=3
    )

    assert all(b.preliminary and not b.is_final for b in page.data)
    assert page.has_more is True and page.next_cursor == "1793822280000"
    assert page.meta is not None and page.meta.preliminary_row_count == 3
    assert page.meta.built_through == utc("2026-11-04T20:01:00Z")


def test_hip3_trade_intent_keeps_the_symbol_case() -> None:
    client, api = mock_client(replay("trade_intent_hip3_1h"))

    page = client.hyperliquid.hip3.trade_intent.history(
        "xyz:XYZ100", start=D0, end=D0 + 2 * H, interval="1h"
    )

    assert api.raw_paths == ["/v1/hyperliquid/hip3/trade-intent/xyz:XYZ100"]
    assert page.meta is not None and (page.meta.symbol, page.meta.venue) == ("xyz:XYZ100", "hip3")
    assert len(page.data) == 3 and page.data[0].close == 28568.0


def test_trade_intent_async_history_and_iterate() -> None:
    client, api = mock_client(replay("trade_intent_btc_1h_page1", "trade_intent_btc_1h_page2"))

    async def run() -> tuple[CursorResponse[list[TradeIntentBucket]], list[TradeIntentBucket]]:
        page = await client.hyperliquid.trade_intent.ahistory(
            "BTC", start=D0, end=D0 + 5 * H, interval="1h", limit=3
        )
        walked = [
            b
            async for b in client.hyperliquid.trade_intent.aiterate(
                "BTC", start=D0, end=D0 + 5 * H, interval="1h", limit=3
            )
        ]
        return page, walked

    page, walked = asyncio.run(run())
    assert len(page.data) == 3 and len(walked) == 6
    assert len(api.calls) == 3


def test_trade_intent_validates_before_sending() -> None:
    client, api = mock_client(lambda path, q: pytest.fail("no request expected"))
    intent = client.hyperliquid.trade_intent

    with pytest.raises(ValueError, match="interval"):
        intent.history("BTC", interval="2m")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="limit"):
        intent.history("BTC", limit=2001)
    with pytest.raises(ValueError, match="limit"):
        intent.iterate("BTC", start=D0, limit=0)
    with pytest.raises(ValueError, match="symbol"):
        intent.history("")
    assert api.requests == []


# ---------------------------------------------------------------------------
# Moving-average breadth
# ---------------------------------------------------------------------------


def test_breadth_ma_current_sends_n_and_parses_the_reading() -> None:
    client, api = mock_client(replay("breadth_ma_hl_current_n200"))

    reading = client.hyperliquid.breadth_ma.current(200)

    assert api.calls == [("/v1/hyperliquid/breadth/above-ma/current", {"n": "200"})]
    assert isinstance(reading, BreadthMaReading)
    assert reading.n == 200 and reading.method == "ma-breadth/1"
    assert reading.timestamp == utc("2026-11-04T19:59:00Z")
    assert reading.calculated_at == utc("2026-11-04T20:00:00Z")
    assert reading.calculated_at_ms == 1793822400000
    assert reading.value_pct == 31.7919 and reading.coverage_ratio == 0.7793
    counts = reading.counts
    assert (
        counts.candidates
        == counts.eligible + counts.excluded_stale_price + counts.excluded_short_history
    )
    assert counts.eligible == counts.above + counts.at + counts.below
    assert reading.distance.median == -0.081344
    assert reading.is_final is False
    assert reading.response_meta is not None and reading.response_meta.request_id


def test_hip3_breadth_ma_current_and_daily_history() -> None:
    client, api = mock_client(replay("breadth_ma_hip3_current_n5", "breadth_ma_hip3_n20_1d"))

    current = client.hyperliquid.hip3.breadth_ma.current(5)
    daily = client.hyperliquid.hip3.breadth_ma.history(20, start=D0 - 48 * H, end=D0, interval="1d")

    assert current.n == 5
    assert [r.timestamp_ms for r in daily.data] == [D0 - 48 * H, D0 - 24 * H, D0]
    assert daily.data[0].calculated_at_ms == daily.data[0].timestamp_ms + 24 * H
    assert daily.data[0].is_final is True
    assert [path for path, _ in api.calls] == [
        "/v1/hyperliquid/hip3/breadth/above-ma/current",
        "/v1/hyperliquid/hip3/breadth/above-ma",
    ]


def test_breadth_ma_history_pages_and_iterates() -> None:
    client, api = mock_client(replay("breadth_ma_hl_n50_1h_page1", "breadth_ma_hl_n50_1h_page2"))

    page = client.hyperliquid.breadth_ma.history(
        50, start=D0, end=D0 + 4 * H, interval="1h", limit=3
    )
    walked = list(
        client.hyperliquid.breadth_ma.iterate(50, start=D0, end=D0 + 4 * H, interval="1h", limit=3)
    )

    assert api.calls[0] == (
        "/v1/hyperliquid/breadth/above-ma",
        {"n": "50", "start": str(D0), "end": str(D0 + 4 * H), "interval": "1h", "limit": "3"},
    )
    assert page.next_cursor == "1793588400000" and page.has_more is True
    assert [r.timestamp_ms for r in walked] == [D0 + i * H for i in range(5)]
    assert all(r.n == 50 for r in walked)


def test_breadth_ma_async_current_history_and_iterate() -> None:
    client, api = mock_client(
        replay(
            "breadth_ma_hl_current_n200",
            "breadth_ma_hl_n50_1h_page1",
            "breadth_ma_hl_n50_1h_page2",
        )
    )

    async def run() -> tuple[BreadthMaReading, int, int]:
        current = await client.hyperliquid.breadth_ma.acurrent(200)
        page = await client.hyperliquid.breadth_ma.ahistory(
            50, start=D0, end=D0 + 4 * H, interval="1h", limit=3
        )
        walked = [
            r
            async for r in client.hyperliquid.breadth_ma.aiterate(
                50, start=D0, end=D0 + 4 * H, interval="1h", limit=3
            )
        ]
        return current, len(page.data), len(walked)

    current, page_len, walked_len = asyncio.run(run())
    assert current.n == 200 and page_len == 3 and walked_len == 5
    assert len(api.calls) == 4


def test_breadth_ma_before_its_length_starts_is_empty_with_a_notice() -> None:
    client, _ = mock_client(replay("breadth_ma_before_coverage"))

    page = client.hyperliquid.breadth_ma.history(
        200, start="2025-05-01", end="2025-05-02", interval="1d"
    )

    assert page.data == [] and page.has_more is False
    assert page.meta is not None and page.meta.coverage_from == utc("2025-10-08T00:00:00Z")
    assert page.meta.notice is not None and "200-day" in page.meta.notice


def test_breadth_ma_requires_a_valid_n() -> None:
    client, api = mock_client(lambda path, q: pytest.fail("no request expected"))
    breadth = client.hyperliquid.breadth_ma

    for bad in (0, 7, 100, True, "50"):
        with pytest.raises(ValueError, match="5, 20, 50 or 200"):
            breadth.current(bad)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        breadth.current()  # type: ignore[call-arg]
    with pytest.raises(ValueError, match="interval"):
        breadth.history(5, interval="2m")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="limit"):
        breadth.history(5, limit=1001)
    assert api.requests == []


# ---------------------------------------------------------------------------
# Positioning
# ---------------------------------------------------------------------------


def test_positioning_current_returns_every_listed_perp() -> None:
    client, api = mock_client(replay("positioning_hl_4h"))

    cross = client.hyperliquid.positioning.current("4h")

    assert api.calls == [("/v1/hyperliquid/positioning", {"window": "4h"})]
    assert isinstance(cross, CursorResponse)
    assert cross.next_cursor is None and cross.has_more is False
    assert cross.meta is not None and cross.meta.as_of == utc("2026-11-04T20:00:00Z")
    assert cross.meta.count == 179  # recorded; the fixture keeps the first 3 records
    reading = cross.data[0]
    assert isinstance(reading, PositioningReading)
    assert reading.symbol == "0G" and reading.window == "4h"
    assert reading.window_end == cross.meta.as_of
    assert reading.window_end_ms - reading.window_start_ms == 4 * H
    assert reading.oi_buckets == 48 and reading.typical_windows == 1952
    assert reading.oi_start == 6731236.0 and reading.mark_end == 0.15742
    assert reading.liq_long_count == 0 and reading.liq_long_usd == 0.0
    assert reading.typical_flow == pytest.approx(0.10218384332958294)
    assert [r.symbol for r in cross.data] == sorted(r.symbol for r in cross.data)


def test_hip3_positioning_and_async() -> None:
    client, api = mock_client(replay("positioning_hip3_1h"))

    cross = asyncio.run(client.hyperliquid.hip3.positioning.acurrent("1h"))

    assert api.calls == [("/v1/hyperliquid/hip3/positioning", {"window": "1h"})]
    assert cross.meta is not None and cross.meta.as_of == utc("2026-11-04T19:55:00Z")
    assert all(r.window == "1h" for r in cross.data)


def test_positioning_missing_readings_stay_none_and_new_fields_are_kept() -> None:
    rec = fixture("positioning_hl_4h")
    row = {
        **rec["body"]["data"][0],
        "oi_start": None,
        "mark_start": None,
        "typical_price": None,
        "typical_oi": None,
        "typical_flow": None,
        "typical_windows": 120,
        "state": "quiet",
    }
    body = {**rec["body"], "data": [row]}
    client, _ = mock_client(lambda path, q: body)

    reading = client.hyperliquid.positioning.current("4h").data[0]

    assert reading.oi_start is None and reading.mark_start is None
    assert reading.typical_price is None and reading.typical_windows == 120
    assert reading.model_extra == {"state": "quiet"}


def test_positioning_requires_a_window() -> None:
    client, api = mock_client(lambda path, q: pytest.fail("no request expected"))

    for bad in ("2h", "1d", ""):
        with pytest.raises(ValueError, match="1h, 4h or 24h"):
            client.hyperliquid.positioning.current(bad)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        client.hyperliquid.positioning.current()  # type: ignore[call-arg]
    assert api.requests == []


# ---------------------------------------------------------------------------
# Iterators
# ---------------------------------------------------------------------------


def _two_page_chain() -> Callable[[str, dict[str, str]], Any]:
    first, last = fixture(SPARSE[2])["body"], fixture(SPARSE[3])["body"]
    return lambda path, q: last if q.get("cursor") else first


def test_an_iterator_without_end_fixes_it_once() -> None:
    client, api = mock_client(_two_page_chain())
    before = int(time.time() * 1000)

    list(client.hyperliquid.usdc_flows.iterate(start=SPARSE_START))
    list(client.hyperliquid.trade_intent.iterate("BTC", start=SPARSE_START))
    list(client.hyperliquid.breadth_ma.iterate(5, start=SPARSE_START))
    list(client.hyperliquid.usdc_flows.iterate_volume(start=SPARSE_START))

    after = int(time.time() * 1000)
    assert len(api.calls) == 8
    for i in range(0, 8, 2):
        (_, a), (_, b) = api.calls[i], api.calls[i + 1]
        assert a["end"] == b["end"] and before <= int(a["end"]) <= after
        assert "cursor" not in a and b["cursor"]


def test_an_async_iterator_without_end_fixes_it_once() -> None:
    client, api = mock_client(_two_page_chain())

    async def run() -> None:
        async for _ in client.hyperliquid.hip3.trade_intent.aiterate(
            "xyz:XYZ100", start=SPARSE_START
        ):
            pass

    asyncio.run(run())
    assert len(api.calls) == 2 and api.calls[0][1]["end"] == api.calls[1][1]["end"]


def test_a_repeated_cursor_raises_instead_of_looping() -> None:
    client, api = mock_client(body_of(SPARSE[0]))

    with pytest.raises(OxArchiveError) as caught:
        list(client.hyperliquid.usdc_flows.iterate(start=SPARSE_START, end=SPARSE_END))

    assert len(api.calls) == 2
    assert caught.value.error_code == "internal_error"
    assert "cursor it was sent" in caught.value.message

    async def run() -> None:
        async for _ in client.hyperliquid.breadth_ma.aiterate(
            5, start=SPARSE_START, end=SPARSE_END
        ):
            pass

    with pytest.raises(OxArchiveError, match="cursor it was sent"):
        asyncio.run(run())


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

FORBIDDEN = {
    "usdc_flows_free_forbidden": ("usdc_flows", lambda c: c.hyperliquid.usdc_flows.history()),
    "trade_intent_free_forbidden": (
        "trade_intent",
        lambda c: c.hyperliquid.trade_intent.history("BTC"),
    ),
    "breadth_ma_free_forbidden": ("breadth_ma", lambda c: c.hyperliquid.breadth_ma.current(5)),
    "positioning_free_forbidden": (
        "positioning",
        lambda c: c.hyperliquid.positioning.current("1h"),
    ),
}


@pytest.mark.parametrize("name", sorted(FORBIDDEN))
def test_a_free_key_gets_a_typed_plan_error(name: str) -> None:
    datatype, call = FORBIDDEN[name]
    client, api = mock_client(replay(name))

    with pytest.raises(PlanRequiredError) as caught:
        call(client)

    error = caught.value
    assert isinstance(error, OxArchiveError)
    assert error.status == 403 and error.error_code == "forbidden"
    assert error.datatype == datatype
    assert error.required_plans == ["build", "pro", "scale", "enterprise"]
    assert error.upgrade_url == "https://0xarchive.io/pricing"
    assert error.request_id == fixture(name)["body"]["request_id"]
    assert "Build, Pro, Scale and Enterprise" in error.message
    assert error.details["datatype"] == datatype
    assert len(api.calls) == 1


def test_a_plan_error_is_raised_from_async_calls_too() -> None:
    client, _ = mock_client(replay("positioning_free_forbidden"))

    with pytest.raises(PlanRequiredError):
        asyncio.run(client.hyperliquid.positioning.acurrent("1h"))


def test_a_403_without_required_plans_stays_a_plain_error() -> None:
    body = {
        "code": 403,
        "error": "Forbidden",
        "error_code": "forbidden",
        "request_id": "req-1",
        "success": False,
    }
    client, _ = mock_client(lambda path, q: httpx.Response(403, json=body))

    with pytest.raises(OxArchiveError) as caught:
        client.hyperliquid.positioning.current("1h")

    assert type(caught.value) is OxArchiveError
    assert caught.value.error_code == "forbidden"
    assert not isinstance(caught.value, PlanRequiredError)


def test_plan_required_error_from_response_directly() -> None:
    body = fixture("usdc_flows_free_forbidden")["body"]

    error = OxArchiveError.from_response(403, body)

    assert isinstance(error, PlanRequiredError) and error.datatype == "usdc_flows"
    assert type(OxArchiveError.from_response(400, body)) is OxArchiveError


RECORDED_ERRORS = [
    ("trade_intent_invalid_interval", 400, "invalid_interval", "interval", True),
    ("usdc_flows_volume_refuses_min_usd", 400, "invalid_parameter", "min_usd", False),
    ("breadth_ma_missing_n", 400, "invalid_parameter", "n", True),
    ("breadth_ma_current_refuses_window", 400, "invalid_parameter", "interval", False),
    ("positioning_missing_window", 400, "invalid_parameter", "window", True),
    ("positioning_refuses_end", 400, "invalid_parameter", "end", False),
    ("usdc_flows_hip3_unsupported", 404, "unsupported_for_venue", None, False),
    ("positioning_lighter_unsupported", 404, "unsupported_for_venue", None, False),
    ("positioning_cold_503", 503, "upstream_unavailable", None, False),
]


@pytest.mark.parametrize("name,status,code,param,has_values", RECORDED_ERRORS)
def test_recorded_error_bodies_keep_their_contract_fields(
    name: str, status: int, code: str, param: Any, has_values: bool
) -> None:
    rec = fixture(name)
    client, _ = mock_client(body_of(name))

    with pytest.raises(OxArchiveError) as caught:
        client.hyperliquid.positioning.current("1h")

    error = caught.value
    assert type(error) is OxArchiveError
    assert (error.status, error.error_code, error.param) == (status, code, param)
    assert error.message == rec["body"]["error"]
    assert error.request_id == rec["body"]["request_id"]
    if has_values:
        assert error.valid_values == rec["body"]["valid_values"]
    else:
        assert error.valid_values is None
    if code == "unsupported_for_venue":
        assert error.details["available_on"] == rec["body"]["available_on"]


# ---------------------------------------------------------------------------
# Capabilities rows
# ---------------------------------------------------------------------------


def test_capability_rows_name_the_plans_and_starts() -> None:
    client, _ = mock_client(replay("capabilities_derived_rows"))

    rows = {(r.venue, r.datatype): r for r in client.capabilities()}

    plans = ["build", "pro", "scale", "enterprise"]
    assert {key for key in rows} == {
        ("hyperliquid", "usdc_flows"),
        ("hyperliquid", "trade_intent"),
        ("hyperliquid", "breadth_ma"),
        ("hyperliquid", "positioning"),
        ("hip3", "trade_intent"),
        ("hip3", "breadth_ma"),
        ("hip3", "positioning"),
    }
    assert all(r.plans == plans for r in rows.values())
    assert rows[("hyperliquid", "usdc_flows")].available_from == utc("2025-09-27T09:33:00Z")
    assert rows[("hyperliquid", "trade_intent")].available_from == utc("2025-05-25T15:00:00Z")
    assert rows[("hip3", "trade_intent")].available_from == utc("2025-10-13T12:00:00Z")
    assert rows[("hyperliquid", "breadth_ma")].available_from == utc("2025-03-27T00:00:00Z")
    assert rows[("hip3", "breadth_ma")].available_from == utc("2025-12-27T00:00:00Z")
    assert rows[("hyperliquid", "positioning")].available_from is None
    assert rows[("hyperliquid", "trade_intent")].page_limit == 2000
    assert rows[("hyperliquid", "trade_intent")].intervals == [
        "1s",
        "5s",
        "15s",
        "1m",
        "5m",
        "15m",
        "1h",
        "4h",
        "1d",
    ]


def test_sdk_intervals_match_the_capability_rows() -> None:
    from oxarchive.resources.breadth_ma import BREADTH_MA_INTERVALS, BREADTH_MA_MAX_LIMIT
    from oxarchive.resources.trade_intent import TRADE_INTENT_INTERVALS, TRADE_INTENT_MAX_LIMIT
    from oxarchive.resources.usdc_flows import USDC_FLOW_INTERVALS, USDC_FLOWS_MAX_LIMIT

    rows = {
        (r["venue"], r["datatype"]): r for r in fixture("capabilities_derived_rows")["body"]["data"]
    }
    for (venue, datatype), row in rows.items():
        if datatype == "trade_intent":
            assert set(row["intervals"]) == TRADE_INTENT_INTERVALS
            assert row["page_limit"] == TRADE_INTENT_MAX_LIMIT
        elif datatype == "breadth_ma":
            assert set(row["intervals"]) == BREADTH_MA_INTERVALS
            assert row["page_limit"] == BREADTH_MA_MAX_LIMIT
        elif datatype == "usdc_flows":
            assert set(row["intervals"]) == USDC_FLOW_INTERVALS
            assert row["page_limit"] == USDC_FLOWS_MAX_LIMIT


def test_version_is_1_14_1() -> None:
    assert oxarchive.__version__ == "1.15.0"
