"""The momentum factor (client.hyperliquid.factors.momentum).

The response bodies in ``fixtures/momentum`` were recorded from the API
(version 2026-10-01) with a paid key, and with a Free key for the 403. Each
file names the request that produced it. ``replay`` answers a request only
when its path and query are exactly the recorded ones, so these tests check
what the SDK sends as well as how it parses the answer. Long score lists are
trimmed (see each file's ``note``).
"""

from __future__ import annotations

import asyncio
import itertools
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import httpx
import pytest
from _mock_api import mock_client

from oxarchive import (
    CursorResponse,
    MomentumHolding,
    MomentumReturn,
    MomentumScore,
    OxArchiveError,
    PlanRequiredError,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "momentum"

COVERAGE = "2025-05-24T01:00:00Z"
PLANS = ["build", "pro", "scale", "enterprise"]


def fixture(name: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((FIXTURES / f"{name}.json").read_text())
    return data


def _answer(rec: dict[str, Any]) -> Any:
    if rec["status"] == 200:
        return rec["body"]
    return httpx.Response(rec["status"], json=rec["body"])


def query_of(name: str) -> dict[str, str]:
    """The recorded request's query, as the SDK sends it (strings)."""
    return {k: str(v) for k, v in fixture(name)["request"]["query"].items()}


def replay(*names: str) -> Callable[[str, dict[str, str]], Any]:
    """Answer each recorded request with its recorded body; refuse anything else."""
    table: dict[tuple[str, tuple[tuple[str, str], ...]], dict[str, Any]] = {}
    for name in names:
        rec = fixture(name)
        table[(rec["request"]["path"], tuple(sorted(query_of(name).items())))] = rec

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


def ms(text: str) -> int:
    return int(utc(text).timestamp() * 1000)


def _check_scores(scores: list[MomentumScore], raw: list[dict[str, Any]], lookback: str) -> None:
    assert len(scores) == len(raw) and scores
    for score, row in zip(scores, raw):
        assert isinstance(score, MomentumScore)
        assert score.symbol == row["symbol"]
        assert score.timestamp == utc(row["timestamp"])
        assert score.timestamp_ms == row["timestamp_ms"]
        assert score.lookback == lookback and score.method == "momentum/1"
        assert score.ret == row["ret"] and score.vol == row["vol"]
        assert score.score == row["score"] and score.pct_rank == row["pct_rank"]
        assert score.quintile == row["quintile"]
        assert (score.in_top25, score.in_top50, score.is_final) == (
            row["in_top25"],
            row["in_top50"],
            row["is_final"],
        )
        assert 0 < score.pct_rank <= 1 and 1 <= score.quintile <= 5
        # The top-25 universe is part of the top-50 one.
        assert not score.in_top25 or score.in_top50
    # One reading: every perp at the same hour, strongest first.
    assert len({s.timestamp_ms for s in scores}) == 1
    assert scores[0].timestamp_ms % 3_600_000 == 0
    assert [s.score for s in scores] == sorted((s.score for s in scores), reverse=True)


def _check_returns(buckets: list[MomentumReturn], raw: list[dict[str, Any]]) -> None:
    assert len(buckets) == len(raw)
    for bucket, row in zip(buckets, raw):
        assert isinstance(bucket, MomentumReturn)
        assert bucket.timestamp == utc(row["timestamp"])
        assert bucket.timestamp_ms == row["timestamp_ms"]
        assert bucket.calculated_at == utc(row["calculated_at"])
        assert bucket.calculated_at_ms == row["calculated_at_ms"]
        assert (bucket.lookback, bucket.universe, bucket.method) == (
            row["lookback"],
            row["universe"],
            "momentum/1",
        )
        assert (bucket.ret, bucket.long_ret, bucket.short_ret) == (
            row["ret"],
            row["long_ret"],
            row["short_ret"],
        )
        assert (bucket.hours, bucket.longs, bucket.shorts, bucket.is_final) == (
            row["hours"],
            row["longs"],
            row["shorts"],
            row["is_final"],
        )
        # The factor is the long leg less the short leg.
        assert bucket.ret == pytest.approx(bucket.long_ret - bucket.short_ret, abs=1e-12)
        assert bucket.calculated_at_ms > bucket.timestamp_ms


# ---------------------------------------------------------------------------
# Scores
# ---------------------------------------------------------------------------


def test_current_sends_the_lookback_and_parses_every_perp() -> None:
    name = "momentum_current_14d"
    client, api = mock_client(replay(name))

    page = client.hyperliquid.factors.momentum.current("14d")

    assert api.calls == [("/v1/hyperliquid/factors/momentum/current", {"lookback": "14d"})]
    assert isinstance(page, CursorResponse)
    assert page.next_cursor is None and page.has_more is False
    assert (
        page.meta is not None
        and page.meta.request_id == fixture(name)["body"]["meta"]["request_id"]
    )
    assert page.meta.count == 178  # recorded; the fixture keeps 6 of the records
    _check_scores(page.data, fixture(name)["body"]["data"], "14d")
    first = page.data[0]
    assert first.symbol == "BLUR" and first.timestamp == utc("2026-11-23T16:00:00Z")
    assert first.pct_rank == 1.0 and first.quintile == 5 and first.is_final is False
    assert first.score == pytest.approx(first.ret / first.vol)  # type: ignore[operator]
    assert page.data[-1].quintile == 1


def test_get_sends_at_in_milliseconds_and_reads_that_hour() -> None:
    name = "momentum_scores_7d_at"
    client, api = mock_client(replay(name, name))

    by_text = client.hyperliquid.factors.momentum.get("7d", at="2026-11-01T12:00:00Z")
    by_datetime = client.hyperliquid.factors.momentum.get(
        "7d", at=datetime(2026, 11, 1, 12, tzinfo=timezone.utc)
    )

    assert api.calls == [("/v1/hyperliquid/factors/momentum", query_of(name))] * 2
    assert query_of(name)["at"] == str(ms("2026-11-01T12:00:00Z"))
    for page in (by_text, by_datetime):
        _check_scores(page.data, fixture(name)["body"]["data"], "7d")
        # The reading is as of the close of the hour at or before `at`.
        assert page.data[0].timestamp == utc("2026-11-01T12:00:00Z")
        assert all(s.is_final for s in page.data)
    assert by_text.data[0].symbol == "HYPE" and by_text.data[0].in_top25 is True


def test_get_without_at_sends_only_the_lookback() -> None:
    client, api = mock_client(body_of("momentum_current_14d"))

    client.hyperliquid.factors.momentum.get("7d")

    assert api.calls == [("/v1/hyperliquid/factors/momentum", {"lookback": "7d"})]


def test_async_scores() -> None:
    name = "momentum_scores_7d_at"
    client, api = mock_client(replay("momentum_current_14d", name))

    async def run() -> tuple[int, int]:
        current = await client.hyperliquid.factors.momentum.acurrent("14d")
        past = await client.hyperliquid.factors.momentum.aget("7d", at=int(query_of(name)["at"]))
        return len(current.data), len(past.data)

    assert asyncio.run(run()) == (
        len(fixture("momentum_current_14d")["body"]["data"]),
        len(fixture(name)["body"]["data"]),
    )
    assert [path for path, _ in api.calls] == [
        "/v1/hyperliquid/factors/momentum/current",
        "/v1/hyperliquid/factors/momentum",
    ]


def test_new_score_fields_are_kept() -> None:
    rec = fixture("momentum_current_14d")
    row = {**rec["body"]["data"][0], "ret": None, "vol": None, "sector": "l1"}
    client, _ = mock_client(lambda path, q: {**rec["body"], "data": [row]})

    score = client.hyperliquid.factors.momentum.current("14d").data[0]

    assert score.ret is None and score.vol is None
    assert score.model_extra == {"sector": "l1"}


# ---------------------------------------------------------------------------
# Returns
# ---------------------------------------------------------------------------

PAGES = ("momentum_returns_7d_top25_1d_page1", "momentum_returns_7d_top25_1d_page2")
RETURNS = "/v1/hyperliquid/factors/momentum/returns"


def _window(name: str) -> dict[str, Any]:
    q = query_of(name)
    return {
        "universe": q["universe"],
        "interval": q["interval"],
        "start": int(q["start"]),
        "end": int(q["end"]),
        "limit": int(q["limit"]),
    }


def test_returns_page_with_the_window_unchanged() -> None:
    client, api = mock_client(replay(*PAGES))

    first = client.hyperliquid.factors.momentum.returns("7d", **_window(PAGES[0]))
    second = client.hyperliquid.factors.momentum.returns(
        "7d", **_window(PAGES[0]), cursor=first.next_cursor
    )

    assert api.calls == [(RETURNS, query_of(PAGES[0])), (RETURNS, query_of(PAGES[1]))]
    assert query_of(PAGES[0])["start"] == str(ms("2026-10-01T00:00:00Z"))
    assert first.has_more is True and first.next_cursor == "1791676800000"
    assert second.has_more is True and second.next_cursor == "1792540800000"
    _check_returns(first.data, fixture(PAGES[0])["body"]["data"])
    _check_returns(second.data, fixture(PAGES[1])["body"]["data"])
    joined = first.data + second.data
    opens = [b.timestamp_ms for b in joined]
    # Daily buckets, oldest first, none repeated across the page boundary;
    # the cursor is the next bucket's open.
    assert opens[0] == ms("2026-10-01T00:00:00Z")
    assert all(b - a == 86_400_000 for a, b in zip(opens, opens[1:]))
    assert second.data[0].timestamp_ms == int(first.next_cursor or 0)
    for b in joined:
        assert (b.lookback, b.universe, b.hours, b.is_final) == ("7d", "top25", 24, True)
        assert b.calculated_at_ms == b.timestamp_ms + 86_400_000
        assert b.holdings is None
    oct1 = first.data[0]
    assert oct1.ret == 0.011022206600979339 and (oct1.longs, oct1.shorts) == (6, 5)
    assert oct1.long_ret == -0.016356793266587358 and oct1.short_ret == -0.027378999867566683


def test_iterate_returns_sends_the_cursor_and_the_same_window() -> None:
    client, api = mock_client(replay(*PAGES))

    walk = client.hyperliquid.factors.momentum.iterate_returns("7d", **_window(PAGES[0]))
    # Two recorded pages of a longer walk: stop after their 20 buckets.
    walked = list(itertools.islice(walk, 20))

    assert api.calls == [(RETURNS, query_of(PAGES[0])), (RETURNS, query_of(PAGES[1]))]
    expected = fixture(PAGES[0])["body"]["data"] + fixture(PAGES[1])["body"]["data"]
    assert [b.timestamp_ms for b in walked] == [row["timestamp_ms"] for row in expected]


def test_aiterate_returns_and_areturns() -> None:
    client, api = mock_client(replay(*PAGES))

    async def run() -> tuple[int, int]:
        page = await client.hyperliquid.factors.momentum.areturns("7d", **_window(PAGES[0]))
        walked = []
        async for bucket in client.hyperliquid.factors.momentum.aiterate_returns(
            "7d", **_window(PAGES[0])
        ):
            walked.append(bucket)
            if len(walked) == 20:
                break
        return len(page.data), len(walked)

    assert asyncio.run(run()) == (10, 20)
    assert [q for _, q in api.calls] == [query_of(n) for n in (PAGES[0], PAGES[0], PAGES[1])]


def test_iterate_returns_stops_on_the_page_without_a_cursor() -> None:
    name = "momentum_returns_14d_top50_1h_holdings"
    client, api = mock_client(replay(name))
    q = query_of(name)

    walked = list(
        client.hyperliquid.factors.momentum.iterate_returns(
            "14d",
            universe="top50",
            interval="1h",
            holdings=True,
            start=int(q["start"]),
            end=int(q["end"]),
        )
    )

    assert len(walked) == 4 and api.calls == [(RETURNS, q)]


def test_returns_with_holdings_universe_and_hourly_buckets() -> None:
    name = "momentum_returns_14d_top50_1h_holdings"
    client, api = mock_client(replay(name))

    page = client.hyperliquid.factors.momentum.returns(
        "14d",
        universe="top50",
        interval="1h",
        holdings=True,
        start="2026-11-15T00:00:00Z",
        end="2026-11-15T03:00:00Z",
    )

    assert api.calls == [(RETURNS, query_of(name))]
    assert query_of(name)["holdings"] == "true"
    assert page.has_more is False and page.next_cursor is None
    raw = fixture(name)["body"]["data"]
    _check_returns(page.data, raw)
    # end is a bucket open: the 03:00 bucket is the last one.
    assert [b.timestamp for b in page.data] == [utc(f"2026-11-15T0{h}:00:00Z") for h in range(4)]
    for bucket, row in zip(page.data, raw):
        assert bucket.universe == "top50" and bucket.lookback == "14d"
        assert bucket.hours == 1
        assert bucket.calculated_at_ms == bucket.timestamp_ms + 3_600_000
        assert bucket.holdings is not None
        assert all(isinstance(h, MomentumHolding) for h in bucket.holdings)
        assert [(h.symbol, h.weight) for h in bucket.holdings] == [
            (h["symbol"], h["weight"]) for h in row["holdings"]
        ]
        longs = [h.weight for h in bucket.holdings if h.weight > 0]
        shorts = [h.weight for h in bucket.holdings if h.weight < 0]
        assert (len(longs), len(shorts)) == (bucket.longs, bucket.shorts) == (11, 10)
        # Each leg sums to 1 in size, long leg first.
        assert sum(longs) == pytest.approx(1.0) and sum(shorts) == pytest.approx(-1.0)
        assert all(h.weight > 0 for h in bucket.holdings[: len(longs)])
    assert page.data[0].holdings is not None and page.data[0].holdings[0].symbol == "STRK"


def test_returns_before_coverage_are_empty_with_a_notice() -> None:
    client, api = mock_client(body_of("momentum_returns_before_coverage"))

    page = client.hyperliquid.factors.momentum.returns("7d", start="2025-05-01", end="2025-05-02")

    assert api.calls == [
        (
            RETURNS,
            {
                "lookback": "7d",
                "start": str(ms("2025-05-01T00:00:00Z")),
                "end": str(ms("2025-05-02T00:00:00Z")),
            },
        )
    ]
    assert page.data == [] and page.has_more is False
    assert page.meta is not None and page.meta.coverage_from == utc(COVERAGE)
    assert page.meta.notice is not None
    assert "returns begin 2025-05-24 01:00 UTC" in page.meta.notice


def test_holdings_false_is_sent_and_defaults_are_left_to_the_api() -> None:
    client, api = mock_client(body_of(PAGES[0]))

    client.hyperliquid.factors.momentum.returns("14d")
    client.hyperliquid.factors.momentum.returns(
        "14d", holdings=False, start="2026-11-01", end="2026-11-02T00:00:00Z"
    )

    assert api.calls == [
        (RETURNS, {"lookback": "14d"}),
        (
            RETURNS,
            {
                "lookback": "14d",
                "holdings": "false",
                "start": str(ms("2026-11-01T00:00:00Z")),
                "end": str(ms("2026-11-02T00:00:00Z")),
            },
        ),
    ]


def test_iterate_returns_without_end_fixes_it_once() -> None:
    first = fixture(PAGES[0])["body"]
    last = fixture("momentum_returns_14d_top50_1h_holdings")["body"]
    client, api = mock_client(lambda path, q: last if q.get("cursor") else first)
    before = int(time.time() * 1000)

    list(client.hyperliquid.factors.momentum.iterate_returns("7d", start="2026-10-01"))

    after = int(time.time() * 1000)
    (_, a), (_, b) = api.calls
    assert a["end"] == b["end"] and before <= int(a["end"]) <= after
    assert a["start"] == b["start"] == str(ms("2026-10-01T00:00:00Z"))
    assert "cursor" not in a and b["cursor"] == first["meta"]["next_cursor"]


def test_a_repeated_cursor_raises_instead_of_looping() -> None:
    client, api = mock_client(body_of(PAGES[1]))
    cursor = fixture(PAGES[1])["body"]["meta"]["next_cursor"]

    with pytest.raises(OxArchiveError, match="cursor it was sent") as caught:
        list(
            client.hyperliquid.factors.momentum.iterate_returns(
                "7d", start="2026-10-01", end="2026-11-20"
            )
        )

    assert len(api.calls) == 2 and api.calls[1][1]["cursor"] == cursor
    assert caught.value.error_code == "internal_error"


# ---------------------------------------------------------------------------
# Parameters
# ---------------------------------------------------------------------------


def test_parameters_are_checked_before_sending() -> None:
    client, api = mock_client(lambda path, q: pytest.fail("no request expected"))
    momentum = client.hyperliquid.factors.momentum

    for bad in ("1d", "28d", "7D", "", None, 7):
        with pytest.raises(ValueError, match="7d or 14d"):
            momentum.current(bad)  # type: ignore[arg-type]
        with pytest.raises(ValueError, match="7d or 14d"):
            momentum.get(bad)  # type: ignore[arg-type]
        with pytest.raises(ValueError, match="7d or 14d"):
            momentum.returns(bad)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        momentum.current()  # type: ignore[call-arg]
    with pytest.raises(ValueError, match="top25 or top50"):
        momentum.returns("7d", universe="top100")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="1h or 1d"):
        momentum.returns("7d", interval="4h")  # type: ignore[arg-type]
    for limit in (0, 1001, True):
        with pytest.raises(ValueError, match="limit"):
            momentum.returns("7d", limit=limit)
    with pytest.raises(ValueError, match="holdings"):
        momentum.returns("7d", holdings="yes")  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        momentum.iterate_returns("7d")  # type: ignore[call-arg]
    assert api.requests == []


def test_the_sdk_lists_match_the_capability_row() -> None:
    from oxarchive.resources.momentum import MOMENTUM_INTERVALS, MOMENTUM_MAX_LIMIT

    row = next(
        r
        for r in fixture("capabilities_momentum_row")["body"]["data"]
        if r["datatype"] == "momentum"
    )
    assert set(row["intervals"]) == MOMENTUM_INTERVALS
    assert row["page_limit"] == MOMENTUM_MAX_LIMIT


def test_the_capability_row_names_the_plans_and_the_routes() -> None:
    client, _ = mock_client(replay("capabilities_momentum_row"))

    rows = [r for r in client.capabilities() if r.datatype == "momentum"]

    assert len(rows) == 1
    row = rows[0]
    assert row.venue == "hyperliquid" and row.plans == PLANS
    assert sorted(row.rest_routes) == [
        "/v1/hyperliquid/factors/momentum",
        "/v1/hyperliquid/factors/momentum/current",
        "/v1/hyperliquid/factors/momentum/returns",
    ]
    assert row.ws_channels == [] and row.page_limit == 1000
    # As recorded: the row does not set available_from; coverage_from on a
    # response before coverage names the start.
    assert row.available_from is None
    assert row.notes is not None and "2025-05-24 01:00 UTC" in row.notes


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

FORBIDDEN = {
    "momentum_free_forbidden": lambda c: c.hyperliquid.factors.momentum.current("7d"),
    "momentum_free_forbidden_returns": lambda c: c.hyperliquid.factors.momentum.returns("7d"),
}


@pytest.mark.parametrize("name", sorted(FORBIDDEN))
def test_a_free_key_gets_a_typed_plan_error(name: str) -> None:
    client, api = mock_client(replay(name))

    with pytest.raises(PlanRequiredError) as caught:
        FORBIDDEN[name](client)

    error = caught.value
    assert isinstance(error, OxArchiveError)
    assert error.status == 403 and error.error_code == "forbidden"
    assert error.datatype == "momentum"
    assert error.required_plans == PLANS
    assert error.upgrade_url == "https://0xarchive.io/pricing"
    assert error.request_id == fixture(name)["body"]["request_id"]
    assert error.message == fixture(name)["body"]["error"]
    assert "Build, Pro, Scale and Enterprise" in error.message
    assert len(api.calls) == 1


def test_a_plan_error_is_raised_from_async_calls_too() -> None:
    client, _ = mock_client(body_of("momentum_free_forbidden"))

    with pytest.raises(PlanRequiredError):
        asyncio.run(client.hyperliquid.factors.momentum.aget("7d"))


RECORDED_ERRORS = [
    ("momentum_missing_lookback", 400, "invalid_parameter", "lookback", ["7d", "14d"]),
    ("momentum_lookback_28d", 400, "invalid_parameter", "lookback", ["7d", "14d"]),
    ("momentum_current_refuses_at", 400, "invalid_parameter", "at", None),
    ("momentum_returns_invalid_interval", 400, "invalid_interval", "interval", ["1h", "1d"]),
    ("momentum_cold_503", 503, "upstream_unavailable", None, None),
]


@pytest.mark.parametrize("name,status,code,param,values", RECORDED_ERRORS)
def test_recorded_error_bodies_keep_their_contract_fields(
    name: str, status: int, code: str, param: Any, values: Any
) -> None:
    rec = fixture(name)
    client, _ = mock_client(body_of(name))

    with pytest.raises(OxArchiveError) as caught:
        client.hyperliquid.factors.momentum.returns("7d")

    error = caught.value
    assert type(error) is OxArchiveError
    assert (error.status, error.error_code, error.param) == (status, code, param)
    assert error.message == rec["body"]["error"]
    assert error.request_id == rec["body"]["request_id"]
    assert error.valid_values == values


def test_a_cold_start_is_a_retryable_503() -> None:
    name = "momentum_cold_503"
    client, api = mock_client(replay(name))

    with pytest.raises(OxArchiveError) as caught:
        client.hyperliquid.factors.momentum.current("7d")

    error = caught.value
    assert not isinstance(error, PlanRequiredError)
    assert error.status == 503 and error.error_code == "upstream_unavailable"
    assert "still being prepared" in error.message and "Retry" in error.message
    assert len(api.calls) == 1
