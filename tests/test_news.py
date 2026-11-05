"""News stories on Hyperliquid, HIP-3 and Lighter.

The response bodies in ``fixtures/news`` have the shape the backend builds (migration 338's
``news_story_json`` and the reaction job), with the regression values of the news build
(BTC 2026-11-04 02:57 UTC, xyz:CL 18:07 UTC). They are not recordings: the routes are dark until
``NEWS_ROUTES_ENABLED`` is set, so replace them with recordings after launch. Each file names the
request that produces it; ``replay`` answers a request only when its path and query are exactly
the recorded ones, so these tests check what the SDK sends as well as how it parses the answer.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import httpx
import pytest
from _mock_api import mock_client

from oxarchive import (
    CursorResponse,
    NewsReaction,
    NewsStory,
    OxArchiveError,
    PlanRequiredError,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "news"

FIRST_SEEN = 1793761020000  # 2026-11-04T02:57:00Z
QUERY = {"limit": 2, "min_weight": 2, "symbols": "BTC,BNB"}


def fixture(name: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((FIXTURES / f"{name}.json").read_text())
    return data


def _answer(rec: dict[str, Any]) -> Any:
    if rec["status"] == 200:
        return rec["body"]
    return httpx.Response(rec["status"], json=rec["body"])


def replay(*names: str) -> Callable[[str, dict[str, str]], Any]:
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


def utc(text: str) -> datetime:
    return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(timezone.utc)


def test_a_page_parses_stories_with_their_reactions() -> None:
    client, api = mock_client(replay("news_hl_page1"))

    page = client.hyperliquid.news.list(limit=2, min_weight=2, symbols=["BTC", "BNB"])

    assert isinstance(page, CursorResponse)
    assert api.calls == [("/v1/hyperliquid/news", {k: str(v) for k, v in QUERY.items()})]
    assert page.has_more is True
    assert page.next_cursor == "1793760070100_c3d90be1a7746f20"
    liq, tree = page.data
    assert isinstance(liq, NewsStory)
    assert liq.id == "st_8a41c07e5d2b9f13"
    assert (liq.origin, liq.topic, liq.weight, liq.weight_rule) == (
        "venue",
        "liquidation",
        3,
        "venue",
    )
    assert liq.first_seen_at == utc("2026-11-04T02:57:00.000Z")
    assert liq.url is None and liq.source_line is None
    assert [(m.venue, m.symbol) for m in liq.markets] == [("hyperliquid", "BTC")]
    reaction = liq.reaction
    assert isinstance(reaction, NewsReaction)
    assert reaction.status == "final" and reaction.from_ == liq.first_seen_at
    assert (reaction.market.venue, reaction.market.symbol) == ("hyperliquid", "BTC")
    five = reaction.windows["5m"]
    assert five.end == utc("2026-11-04T03:02:00.000Z")
    assert five.price is not None
    assert (five.price.at, five.price.end, five.price.move_pct) == (76554.0, 75983.0, -0.75)
    assert five.liquidations_usd is not None and five.liquidations_usd.long == 16650000.0
    assert five.liquidations_usd.short == 0.0
    assert (five.oi_change_pct, five.volume_vs_prior) == (-0.76, 4.4)
    assert five.move_z == -7.0 and five.move_level == "large"
    assert five.bid_depth_25bp_usd is not None and five.bid_depth_25bp_usd.at == 4200000
    assert reaction.others[0].market.symbol == "ETH" and reaction.others[0].move_pct_5m == -1.12
    assert reaction.known_at is not None
    # The 1-minute window has no depth or move_z.
    assert reaction.windows["1m"].move_level is None
    assert reaction.windows["1m"].bid_depth_25bp_usd is None

    assert tree.source == "Tree News" and tree.source_line == "via Tree News"
    assert tree.headline == "Binance says it has replenished 95% of stolen crypto assets"
    assert [m.symbol for m in tree.markets] == ["BNB", "BTC"]
    assert [r.source for r in tree.reports] == ["Tree News", "Tree News"]
    assert tree.reports[1].published_at is None


def test_a_measuring_reaction_has_only_the_windows_that_are_due() -> None:
    client, _ = mock_client(replay("news_hl_page1"))

    tree = client.hyperliquid.news.list(limit=2, min_weight=2, symbols="BTC,BNB").data[1]

    assert tree.reaction is not None
    assert tree.reaction.status == "measuring"
    assert list(tree.reaction.windows) == ["1m"]
    one = tree.reaction.windows["1m"]
    assert one.oi_change_pct is None  # unmeasured stays None, never 0
    assert one.liquidations_usd is not None and one.liquidations_usd.total == 0.0


def test_a_story_without_a_market_has_no_reaction() -> None:
    client, _ = mock_client(replay("news_hl_page2"))

    page = client.hyperliquid.news.list(
        limit=2, min_weight=2, symbols="BTC,BNB", cursor="1793760070100_c3d90be1a7746f20"
    )

    story = page.data[0]
    assert story.markets == [] and story.reaction is None
    assert story.url == "https://www.sec.gov/example/open-meeting"
    assert page.has_more is False and page.next_cursor is None


def test_the_iterator_follows_the_cursor_with_the_same_window() -> None:
    # `end` is fixed to now before the first request, so the recorded queries (which carry none)
    # are answered by a responder that ignores it.
    seen: list[dict[str, str]] = []
    inner = replay("news_hl_page1", "news_hl_page2")

    def respond(path: str, query: dict[str, str]) -> Any:
        seen.append(dict(query))
        return inner(path, {k: v for k, v in query.items() if k != "end"})

    client, api = mock_client(respond)
    ids = [s.id for s in client.hyperliquid.news.iterate(limit=2, min_weight=2, symbols="BTC,BNB")]

    assert ids == ["st_8a41c07e5d2b9f13", "st_c3d90be1a7746f20", "st_19ab0c5d7e3f8a42"]
    assert len(seen) == 2
    assert "cursor" not in seen[0] and seen[1]["cursor"] == "1793760070100_c3d90be1a7746f20"
    assert seen[0]["end"] == seen[1]["end"]


def test_the_async_iterator_and_list() -> None:
    seen: list[dict[str, str]] = []
    inner = replay("news_hl_page1", "news_hl_page2")

    def respond(path: str, query: dict[str, str]) -> Any:
        seen.append(dict(query))
        return inner(path, {k: v for k, v in query.items() if k != "end"})

    client, _ = mock_client(respond)

    async def run() -> list[str]:
        page = await client.hyperliquid.news.alist(
            end=None, limit=2, min_weight=2, symbols="BTC,BNB"
        )
        assert page.next_cursor is not None
        return [
            s.id
            async for s in client.hyperliquid.news.aiterate(
                limit=2, min_weight=2, symbols="BTC,BNB"
            )
        ]

    assert asyncio.run(run()) == [
        "st_8a41c07e5d2b9f13",
        "st_c3d90be1a7746f20",
        "st_19ab0c5d7e3f8a42",
    ]


def test_as_of_is_sent_in_milliseconds_and_shows_the_feed_as_known_then() -> None:
    client, api = mock_client(replay("news_hl_as_of"))

    as_of = datetime(2026, 11, 4, 2, 58, 30, tzinfo=timezone.utc)
    page = client.hyperliquid.news.list(as_of=as_of, limit=1, symbols="BTC")

    assert api.calls[0][1]["as_of"] == str(FIRST_SEEN + 90000)
    reaction = page.data[0].reaction
    assert reaction is not None and reaction.status == "measuring"
    assert list(reaction.windows) == ["1m"]


def test_hip3_uses_its_own_route_and_keeps_the_symbol_as_given() -> None:
    client, api = mock_client(replay("news_hip3_cl"))

    page = client.hyperliquid.hip3.news.list(symbols="xyz:CL", topic="macro", limit=1)

    assert api.calls[0][0] == "/v1/hyperliquid/hip3/news"
    assert api.calls[0][1]["symbols"] == "xyz:CL"
    story = page.data[0]
    assert [(m.venue, m.symbol) for m in story.markets] == [
        ("hip3", "xyz:CL"),
        ("hip3", "xyz:BRENTOIL"),
    ]
    five = story.reaction.windows["5m"] if story.reaction else None
    assert five is not None and five.price is not None
    assert (five.price.at, five.price.end, five.price.move_pct) == (88.173, 88.9, 0.82)
    assert (five.oi_change_pct, five.volume_vs_prior, five.move_z) == (1.83, 8.3, 3.6)
    assert five.move_level == "large"


def test_lighter_reports_a_liquidation_total_only() -> None:
    client, api = mock_client(replay("news_lighter_total_only"))

    page = client.lighter.news.list(symbols="BTC", limit=1)

    assert api.calls[0][0] == "/v1/lighter/news"
    five = page.data[0].reaction.windows["5m"] if page.data[0].reaction else None
    assert five is not None and five.liquidations_usd is not None
    assert five.liquidations_usd.long is None and five.liquidations_usd.short is None
    assert five.liquidations_usd.total == 1210000.0
    assert five.move_z is None and five.move_level is None


def test_the_robinhood_chain_lighter_client_has_no_news() -> None:
    client, _ = mock_client(replay())
    assert not hasattr(client.rh_lighter, "news")
    assert not hasattr(client.hyperliquid.hip4, "news")
    assert not hasattr(client.spot, "news")


def test_unknown_fields_are_kept() -> None:
    story = NewsStory.model_validate(
        {
            "id": "st_1",
            "headline": "h",
            "source": "s",
            "origin": "outlet",
            "topic": "newtopic",
            "weight": 1,
            "first_seen_at": "2026-11-04T00:00:00.000Z",
            "future_field": 7,
        }
    )
    assert story.model_extra == {"future_field": 7}
    assert story.markets == [] and story.reaction is None


def test_symbols_take_a_string_or_a_list_and_are_trimmed() -> None:
    sent: list[dict[str, str]] = []

    def respond(path: str, query: dict[str, str]) -> Any:
        sent.append(query)
        return {"success": True, "data": [], "meta": {"count": 0, "has_more": False}}

    client, _ = mock_client(respond)
    client.hyperliquid.news.list(symbols=[" BTC", "ETH,SOL "])
    client.hyperliquid.news.list(symbols="BTC")
    client.hyperliquid.news.list(symbols=[])
    client.hyperliquid.news.list()

    assert sent[0]["symbols"] == "BTC,ETH,SOL"
    assert sent[1]["symbols"] == "BTC"
    assert "symbols" not in sent[2] and sent[3] == {}


def test_parameters_are_checked_before_sending() -> None:
    client, api = mock_client(replay())
    news = client.hyperliquid.news

    for kwargs in (
        {"limit": 0},
        {"limit": 501},
        {"min_weight": 0},
        {"min_weight": 4},
        {"symbols": [f"S{i}" for i in range(21)]},
        {"start": "not a time"},
        {"as_of": object()},
    ):
        with pytest.raises(ValueError):
            news.list(**kwargs)  # type: ignore[arg-type]
    assert api.calls == []


@pytest.mark.parametrize(
    "call, path",
    [
        (lambda c: c.hyperliquid.news.list(), "/v1/hyperliquid/news"),
        (lambda c: c.hyperliquid.hip3.news.list(), "/v1/hyperliquid/hip3/news"),
        (lambda c: c.lighter.news.list(), "/v1/lighter/news"),
    ],
)
def test_a_free_key_gets_a_typed_plan_error(call: Callable[[Any], Any], path: str) -> None:
    rec = fixture("news_free_forbidden")
    client, api = mock_client(lambda p, q: _answer(rec))

    with pytest.raises(PlanRequiredError) as caught:
        call(client)

    error = caught.value
    assert isinstance(error, OxArchiveError)
    assert error.status == 403 and error.error_code == "forbidden"
    assert error.datatype == "news"
    assert error.required_plans == ["build", "pro", "scale", "enterprise"]
    assert error.upgrade_url == "https://0xarchive.io/pricing"
    assert error.request_id == rec["body"]["request_id"]
    assert "Build, Pro, Scale and Enterprise" in error.message
    assert api.calls[0][0] == path


def test_a_plan_error_is_raised_from_async_calls_too() -> None:
    rec = fixture("news_free_forbidden")
    client, _ = mock_client(lambda p, q: _answer(rec))

    async def run() -> None:
        await client.lighter.news.alist()

    with pytest.raises(PlanRequiredError):
        asyncio.run(run())


def test_a_bad_parameter_error_keeps_its_fields() -> None:
    rec = fixture("news_invalid_parameter")
    client, _ = mock_client(lambda p, q: _answer(rec))

    with pytest.raises(OxArchiveError) as caught:
        client.hyperliquid.news.list(min_weight=3)

    assert not isinstance(caught.value, PlanRequiredError)
    assert caught.value.error_code == "invalid_parameter"
    assert caught.value.status == 400
