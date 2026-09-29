"""Cumulative volume delta, HIP-3 oracle, HIP-4 questions, wallet
classification, the symbol universe, and order-flow cursor forwarding.

Paths, query parameters and parsing, sync and async. Response bodies are
shaped like the API's JSON.
"""

from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable

import pytest
from _mock_api import envelope, mock_client

from oxarchive import (
    ClassifiedWallet,
    CursorResponse,
    CvdBucket,
    Hip3OracleDiscoveryBounds,
    Hip3OracleExternalPrice,
    Hip4Question,
    ResponseMeta,
    SymbolEntry,
    WalletClassification,
)

T_START = 1790640000000  # 2026-09-29T00:00:00Z
T_END = 1790726400000  # 2026-09-30T00:00:00Z


def _utc(text: str) -> datetime:
    return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(timezone.utc)


def _bucket(ts: int, delta: float, cumulative: float) -> dict[str, Any]:
    return {
        "timestamp": ts,
        "buy_volume": 1000.0 + max(delta, 0),
        "sell_volume": 1000.0 - min(delta, 0),
        "delta": delta,
        "cumulative_delta": cumulative,
    }


PAGE_NOTICE = (
    "cumulative_delta runs from the first bucket of this page; "
    "to join pages, rebuild it from delta"
)

# ---------------------------------------------------------------------------
# Cumulative volume delta
# ---------------------------------------------------------------------------


def test_core_cvd_sends_the_window_and_parses_buckets_and_meta() -> None:
    client, api = mock_client(
        lambda path, q: envelope(
            [_bucket(T_START, 736138.35, 736138.35), _bucket(T_START + 60000, -50.5, 736087.85)],
            next_cursor=str(T_START + 60000),
            notice=PAGE_NOTICE,
        )
    )

    page = client.hyperliquid.cvd.history(
        "btc",
        start=datetime(2026, 9, 29),  # naive: UTC
        end="2026-09-30T00:00:00Z",
        interval="1m",
        limit=2,
    )

    assert api.calls == [
        (
            "/v1/hyperliquid/cvd/BTC",
            {"start": str(T_START), "end": str(T_END), "interval": "1m", "limit": "2"},
        )
    ]
    assert isinstance(page, CursorResponse)
    assert all(isinstance(b, CvdBucket) for b in page.data)
    assert page.data[0].timestamp == T_START
    assert page.data[1].delta == -50.5 and page.data[1].cumulative_delta == 736087.85
    assert page.next_cursor == str(T_START + 60000)
    assert isinstance(page.meta, ResponseMeta) and page.meta.notice == PAGE_NOTICE


def test_cvd_passes_the_cursor_back_unchanged_and_defaults_to_the_last_day() -> None:
    client, api = mock_client(lambda path, q: envelope([]))

    client.hyperliquid.cvd.history("ETH", start=T_START, end=T_END, cursor="1790640240000")
    client.hyperliquid.cvd.history("ETH")

    assert api.calls == [
        (
            "/v1/hyperliquid/cvd/ETH",
            {"start": str(T_START), "end": str(T_END), "cursor": "1790640240000"},
        ),
        ("/v1/hyperliquid/cvd/ETH", {}),
    ]


def test_hip3_cvd_keeps_the_symbol_case_and_prefix() -> None:
    client, api = mock_client(lambda path, q: envelope([_bucket(T_START, 1.0, 1.0)]))

    page = asyncio.run(
        client.hyperliquid.hip3.cvd.ahistory("km:US500", start=T_START, interval="4h")
    )

    assert api.calls == [
        ("/v1/hyperliquid/hip3/cvd/km:US500", {"start": str(T_START), "interval": "4h"})
    ]
    assert page.data[0].delta == 1.0 and page.next_cursor is None


def test_core_cvd_async_matches_sync() -> None:
    client, api = mock_client(lambda path, q: envelope([_bucket(T_START, 2.0, 2.0)]))

    sync = client.hyperliquid.cvd.history("BTC", start=T_START, end=T_END)
    asyn = asyncio.run(client.hyperliquid.cvd.ahistory("BTC", start=T_START, end=T_END))

    assert api.calls[0] == api.calls[1]
    assert sync == asyn


@pytest.mark.parametrize("interval", ["2h", "1M", "tick"])
def test_cvd_rejects_an_unknown_interval_before_sending(interval: str) -> None:
    client, api = mock_client(lambda path, q: envelope([]))

    with pytest.raises(ValueError, match="interval must be one of"):
        client.hyperliquid.cvd.history("BTC", interval=interval)  # type: ignore[arg-type]
    assert api.requests == []


@pytest.mark.parametrize("limit", [0, 10001])
def test_cvd_rejects_a_limit_out_of_range(limit: int) -> None:
    client, api = mock_client(lambda path, q: envelope([]))

    with pytest.raises(ValueError, match="limit must be between 1 and 10000"):
        client.hyperliquid.hip3.cvd.history("km:US500", limit=limit)
    assert api.requests == []


def _cvd_pages() -> Callable[[str, dict[str, str]], dict[str, Any]]:
    pages = {
        None: envelope(
            [_bucket(T_START, 5.0, 5.0), _bucket(T_START + 60000, 3.0, 8.0)],
            next_cursor=str(T_START + 60000),
            notice=PAGE_NOTICE,
        ),
        # A short page that still carries a cursor: keep going.
        str(T_START + 60000): envelope(
            [_bucket(T_START + 120000, -1.0, -1.0)],
            next_cursor=str(T_START + 120000),
            notice=PAGE_NOTICE,
        ),
        str(T_START + 120000): envelope([_bucket(T_START + 180000, 4.0, 4.0)]),
    }
    return lambda path, q: pages[q.get("cursor")]


def test_cvd_iterate_follows_cursors_with_unchanged_arguments() -> None:
    client, api = mock_client(_cvd_pages())

    buckets = list(
        client.hyperliquid.cvd.iterate("BTC", start=T_START, end=T_END, interval="1m", limit=2)
    )

    assert [b.timestamp for b in buckets] == [T_START + i * 60000 for i in range(4)]
    assert sum(b.delta for b in buckets) == 11.0
    base = {"start": str(T_START), "end": str(T_END), "interval": "1m", "limit": "2"}
    assert api.calls == [
        ("/v1/hyperliquid/cvd/BTC", base),
        ("/v1/hyperliquid/cvd/BTC", {**base, "cursor": str(T_START + 60000)}),
        ("/v1/hyperliquid/cvd/BTC", {**base, "cursor": str(T_START + 120000)}),
    ]


def test_cvd_aiterate_follows_cursors() -> None:
    client, api = mock_client(_cvd_pages())

    async def collect() -> list[CvdBucket]:
        return [b async for b in client.hyperliquid.hip3.cvd.aiterate("km:US500", start=T_START)]

    buckets = asyncio.run(collect())

    assert len(buckets) == 4
    assert [q.get("cursor") for _, q in api.calls] == [
        None,
        str(T_START + 60000),
        str(T_START + 120000),
    ]
    assert all(path == "/v1/hyperliquid/hip3/cvd/km:US500" for path, _ in api.calls)


# ---------------------------------------------------------------------------
# HIP-3 oracle
# ---------------------------------------------------------------------------

BOUNDS: dict[str, Any] = {
    "block_number": 1164897235,
    "bound_fraction": 0.04,
    "lower_bound": 719.6544,
    "max_leverage": 25,
    "reference_price": 749.64,
    "reference_source": "external",
    "symbol": "km:US500",
    "timestamp": 1790649576004,
    "upper_bound": 779.6256,
}

EXTERNAL_PRICE: dict[str, Any] = {
    "block_number": 1164897235,
    "external_price": 749.64,
    "mark_price": 750.97,
    "symbol": "km:US500",
    "timestamp": 1790649576004,
}


def test_discovery_bounds_path_and_parsing() -> None:
    client, api = mock_client(lambda path, q: envelope(BOUNDS))

    bounds = client.hyperliquid.hip3.oracle.discovery_bounds("km:US500")
    abounds = asyncio.run(client.hyperliquid.hip3.oracle.adiscovery_bounds("km:US500"))

    assert api.calls == [("/v1/hyperliquid/hip3/oracle/discovery-bounds/km:US500", {})] * 2
    assert isinstance(bounds, Hip3OracleDiscoveryBounds) and bounds == abounds
    assert bounds.reference_source == "external" and bounds.max_leverage == 25
    assert bounds.lower_bound == pytest.approx(
        bounds.reference_price * (1 - bounds.bound_fraction)
    )
    assert bounds.upper_bound == pytest.approx(
        bounds.reference_price * (1 + bounds.bound_fraction)
    )
    assert bounds.block_number == 1164897235 and bounds.timestamp == 1790649576004


def test_external_price_path_and_parsing_including_nulls() -> None:
    client, api = mock_client(lambda path, q: envelope(EXTERNAL_PRICE))
    empty, _ = mock_client(
        lambda path, q: envelope({**EXTERNAL_PRICE, "external_price": None, "mark_price": None})
    )

    price = client.hyperliquid.hip3.oracle.external_price("xyz:XYZ100")
    aprice = asyncio.run(client.hyperliquid.hip3.oracle.aexternal_price("xyz:XYZ100"))
    missing = empty.hyperliquid.hip3.oracle.external_price("km:US500")

    assert api.calls == [("/v1/hyperliquid/hip3/oracle/external-price/xyz:XYZ100", {})] * 2
    assert isinstance(price, Hip3OracleExternalPrice) and price == aprice
    assert (price.external_price, price.mark_price) == (749.64, 750.97)
    assert missing.external_price is None and missing.mark_price is None


# ---------------------------------------------------------------------------
# HIP-4 questions
# ---------------------------------------------------------------------------

QUESTION: dict[str, Any] = {
    "question_id": 0,
    "name": "Recurring",
    "description": (
        "class:priceBucket|underlying:BTC|expiry:20260508-0600|"
        "priceThresholds:79303,82540|period:1d"
    ),
    "fallback_outcome_id": 6,
    "named_outcome_ids": [7, 8, 9],
    "settled_named_outcomes": [],
    "first_seen_at": "2026-05-08T05:57:28.326Z",
    "last_updated_at": "2026-05-08T05:57:28.326Z",
}


def test_questions_list_pages_with_the_question_id_cursor() -> None:
    client, api = mock_client(
        lambda path, q: envelope([QUESTION, {**QUESTION, "question_id": 1}], next_cursor="1")
    )

    page = client.hyperliquid.hip4.questions.list(limit=2)
    apage = asyncio.run(client.hyperliquid.hip4.questions.alist(cursor=page.next_cursor, limit=2))

    assert api.calls == [
        ("/v1/hyperliquid/hip4/questions", {"limit": "2"}),
        ("/v1/hyperliquid/hip4/questions", {"cursor": "1", "limit": "2"}),
    ]
    assert all(isinstance(q, Hip4Question) for q in page.data)
    assert page.next_cursor == "1" and apage.next_cursor == "1"
    assert page.meta is not None and page.meta.count == 2
    question = page.data[0]
    assert question.named_outcome_ids == [7, 8, 9]
    assert question.fallback_outcome_id == 6 and question.settled_named_outcomes == []
    assert question.first_seen_at == _utc("2026-05-08T05:57:28.326Z")


def test_question_get_and_the_flat_helpers() -> None:
    client, api = mock_client(lambda path, q: envelope({**QUESTION, "extra_field": "kept"}))

    one = client.hyperliquid.hip4.questions.get(0)
    two = asyncio.run(client.hyperliquid.hip4.questions.aget(0))
    three = client.hyperliquid.hip4.get_question(0)
    four = asyncio.run(client.hyperliquid.hip4.aget_question(0))

    assert api.calls == [("/v1/hyperliquid/hip4/questions/0", {})] * 4
    assert one == two == three == four
    assert one.model_extra == {"extra_field": "kept"}


def test_hip4_list_questions_flat_helper_forwards_paging() -> None:
    client, api = mock_client(lambda path, q: envelope([QUESTION]))

    client.hyperliquid.hip4.list_questions(cursor="41", limit=100)
    asyncio.run(client.hyperliquid.hip4.alist_questions(cursor="41", limit=100))

    assert api.calls == [("/v1/hyperliquid/hip4/questions", {"cursor": "41", "limit": "100"})] * 2


# ---------------------------------------------------------------------------
# Wallet classification
# ---------------------------------------------------------------------------

METRICS: dict[str, Any] = {
    "total_orders": 99693611,
    "cancel_rate": 0.4983595688995557,
    "fill_rate": 0.0016403358084802445,
    "order_to_trade_ratio": 143.55992534981473,
    "ioc_ratio": 0.0,
    "post_only_ratio": 0.0,
    "tpsl_ratio": 0.0,
    "trigger_order_ratio": 0.0,
    "unique_coins_traded": 166,
    "uses_tpsl": False,
    "uses_builder": False,
    "avg_order_size_usd": 552.7562187473471,
    "max_order_size_usd": 40000.42404,
    "median_cancel_speed_ms": 678.0,
    "active_hours": 24,
    "total_fills": 694439,
    "total_volume_usd": 185558445.308452,
    "maker_ratio": 1.0,
    "long_short_ratio": 0.9988400002728354,
    "buy_volume_usd": 92725379.4887142,
    "sell_volume_usd": 92833065.81973696,
    "total_fees_usd": -1855.2356810011863,
    "realized_pnl_usd": 727.6003800000058,
    "liquidation_count": 1203,
    "max_single_fill_usd": 40000.415219999995,
    "unique_fill_coins": 165,
    "uses_twap": False,
    "twap_fill_ratio": 0.0,
    "uses_cloid": True,
    "cloid_ratio": 1.0,
    "uses_priority_gas": False,
    "total_priority_gas_paid": 0.0,
    "total_builder_fees_paid": 0.0,
}

CLASSIFY: dict[str, Any] = {
    "wallets": [
        {
            "address": "0x4e60e3a4a32d63d245aa4e4ce304b4254b088f95",
            "metrics": METRICS,
            "period": "24h",
        }
    ],
    "total": 6434,
    "date": "2026-09-28",
}


def test_classify_sends_every_filter_and_parses_the_page() -> None:
    client, api = mock_client(lambda path, q: envelope(CLASSIFY))

    result = client.hyperliquid.wallets.classify(
        min_orders=1000,
        min_volume_usd=1_000_000,
        sort="total_volume_usd",
        order="asc",
        limit=50,
        offset=100,
        uses_twap=True,
        uses_priority_gas=False,
        min_cancel_rate=0.1,
        max_cancel_rate=0.9,
        date=date(2026, 9, 28),
    )

    assert api.calls == [
        (
            "/v1/hyperliquid/wallets/classify",
            {
                "min_orders": "1000",
                "min_volume_usd": "1000000",
                "sort": "total_volume_usd",
                "order": "asc",
                "limit": "50",
                "offset": "100",
                "uses_twap": "true",
                "uses_priority_gas": "false",
                "min_cancel_rate": "0.1",
                "max_cancel_rate": "0.9",
                "date": "2026-09-28",
            },
        )
    ]
    assert isinstance(result, WalletClassification)
    assert result.total == 6434 and result.date == "2026-09-28"
    wallet = result.wallets[0]
    assert isinstance(wallet, ClassifiedWallet) and wallet.period == "24h"
    assert wallet.metrics.total_orders == 99693611
    assert wallet.metrics.uses_cloid is True
    assert wallet.metrics.top_builder is None
    assert wallet.metrics.total_fees_usd == pytest.approx(-1855.2356810011863)


def test_hip3_classify_path_and_no_filters_by_default() -> None:
    client, api = mock_client(lambda path, q: envelope(CLASSIFY))

    result = asyncio.run(client.hyperliquid.hip3.wallets.aclassify())

    assert api.calls == [("/v1/hyperliquid/hip3/wallets/classify", {})]
    assert result.wallets[0].address.startswith("0x4e60")


@pytest.mark.parametrize(
    "value, sent",
    [
        ("2026-09-28", "2026-09-28"),
        (date(2026, 9, 28), "2026-09-28"),
        (datetime(2026, 9, 28, 23, 30), "2026-09-28"),  # naive: UTC
        # 01:30 on the 29th at UTC+3 is 22:30 on the 28th in UTC
        (datetime(2026, 9, 29, 1, 30, tzinfo=timezone(timedelta(hours=3))), "2026-09-28"),
    ],
)
def test_classify_date_is_a_utc_calendar_date(value: Any, sent: str) -> None:
    client, api = mock_client(lambda path, q: envelope(CLASSIFY))

    client.hyperliquid.wallets.classify(date=value)

    assert api.calls == [("/v1/hyperliquid/wallets/classify", {"date": sent})]


# ---------------------------------------------------------------------------
# Symbol universe
# ---------------------------------------------------------------------------

SYMBOLS: dict[str, Any] = {
    "symbols": [
        {
            "symbol": "BTC",
            "exchange": "hyperliquid",
            "coverage_from": "2023-04-15T00:00:00Z",
            "data_types": ["l2_orderbook", "trades", "liquidations"],
            "coverage_by_type": {"trades": "2023-04-15T00:00:00Z"},
            "size_per_day": {"trades": 120.5},
        },
        {
            "symbol": "#0",
            "exchange": "hip4",
            "coverage_from": "2026-05-02T00:00:00Z",
            "coverage_to": "2026-05-03T06:00:05Z",
            "data_types": ["l2_orderbook", "trades"],
            "coverage_by_type": {"trades": "2026-05-02T00:00:00Z"},
            "size_per_day": {"trades": 3.93},
            "slug": "btc-above-78213-yes-may-03-0600",
            "outcome_pair": ["#0", "#1"],
            "display_title": "BTC above 78,213 on May 3 at 06:00 UTC? Yes",
            "is_settled": True,
        },
    ]
}


def test_symbols_list_reads_the_unwrapped_response() -> None:
    client, api = mock_client(lambda path, q: SYMBOLS)

    symbols = client.symbols.list()
    asymbols = asyncio.run(client.symbols.alist())

    assert api.calls == [("/v1/symbols", {})] * 2
    assert symbols == asymbols
    btc, outcome = symbols
    assert isinstance(btc, SymbolEntry)
    assert btc.exchange == "hyperliquid" and btc.coverage_to is None and btc.slug is None
    assert btc.coverage_from == _utc("2023-04-15T00:00:00Z")
    assert btc.coverage_by_type["trades"] == _utc("2023-04-15T00:00:00Z")
    assert btc.size_per_day == {"trades": 120.5}
    assert outcome.outcome_pair == ["#0", "#1"] and outcome.is_settled is True
    assert outcome.coverage_to == _utc("2026-05-03T06:00:05Z")


# ---------------------------------------------------------------------------
# Order flow forwards the cursor on every venue, sync and async
# ---------------------------------------------------------------------------

FLOW_CASES: list[tuple[str, Callable[[Any], Any], str]] = [
    ("core", lambda c: c.hyperliquid.orders, "/v1/hyperliquid/orders/BTC/flow"),
    ("hip3", lambda c: c.hyperliquid.hip3.orders, "/v1/hyperliquid/hip3/orders/BTC/flow"),
    ("hip4", lambda c: c.hyperliquid.hip4.orders, "/v1/hyperliquid/hip4/orders/BTC/flow"),
]


@pytest.mark.parametrize("name, resource, path", FLOW_CASES, ids=[c[0] for c in FLOW_CASES])
def test_order_flow_forwards_the_cursor(
    name: str, resource: Callable[[Any], Any], path: str
) -> None:
    client, api = mock_client(
        lambda p, q: envelope([{"timestamp": T_START}], next_cursor=str(T_START + 60000))
    )
    orders = resource(client)

    page = orders.flow("BTC", start=T_START, end=T_END, interval="1m", cursor="1790640060000")
    apage = asyncio.run(
        orders.aflow("BTC", start=T_START, end=T_END, interval="1m", cursor="1790640060000")
    )

    expected = {
        "start": str(T_START),
        "end": str(T_END),
        "interval": "1m",
        "cursor": "1790640060000",
    }
    assert api.calls == [(path, expected), (path, expected)]
    assert page.next_cursor == apage.next_cursor == str(T_START + 60000)


def test_hip4_order_flow_flat_helpers_forward_the_cursor() -> None:
    client, api = mock_client(lambda p, q: envelope([]))

    client.hyperliquid.hip4.get_order_flow("#0", start=T_START, end=T_END, cursor="c1")
    asyncio.run(client.hyperliquid.hip4.aget_order_flow("0", start=T_START, end=T_END, cursor="c1"))

    expected = {"start": str(T_START), "end": str(T_END), "cursor": "c1"}
    assert api.calls == [("/v1/hyperliquid/hip4/orders/0/flow", expected)] * 2

