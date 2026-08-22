import asyncio
from pathlib import Path
from typing import Any, cast

import pytest

from oxarchive.exchanges import Hip4Client, LighterClient, SpotClient
from oxarchive.http import HttpClient
from oxarchive.resources.l3_orderbook import L3OrderBookResource
from oxarchive.types import CandleInterval, Hip4OpenInterestRecord, OpenInterest


class FakeHttp:
    def __init__(self, response: dict[str, Any] | None = None) -> None:
        self.calls: list[tuple[str, dict[str, Any] | None]] = []
        self.response = response or {
            "data": [
                {
                    "timestamp": "2026-05-02T08:00:00Z",
                    "open": 0.2,
                    "high": 0.3,
                    "low": 0.1,
                    "close": 0.25,
                    "volume": 10,
                }
            ],
            "meta": {"next_cursor": "next-cursor"},
        }

    def get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        self.calls.append((path, params))
        return self.response

    async def aget(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        return self.get(path, params)


def test_hip4_exposes_candle_history_without_funding() -> None:
    http = FakeHttp()
    client = Hip4Client(cast(HttpClient, http))

    result = client.candles.history(
        "#0",
        start="2026-05-02T08:00:00Z",
        end="2026-05-02T09:00:00Z",
        interval="1m",
    )

    assert http.calls[0][0] == "/v1/hyperliquid/hip4/candles/0"
    params = http.calls[0][1]
    assert params is not None
    assert params["interval"] == "1m"
    assert result.next_cursor == "next-cursor"
    assert result.data[0].close == 0.25
    assert not hasattr(client, "funding")
    assert type(client.candles).__name__ == "Hip4CandlesResource"


def test_hip4_exposes_async_candle_history() -> None:
    http = FakeHttp()
    client = Hip4Client(cast(HttpClient, http))

    result = asyncio.run(
        client.candles.ahistory(
            "0",
            start="2026-05-02T08:00:00Z",
            end="2026-05-02T09:00:00Z",
            interval="1h",
        )
    )

    assert http.calls[0][0] == "/v1/hyperliquid/hip4/candles/0"
    assert result.data[0].open == 0.2


def test_hip4_accepts_advertised_integer_symbols() -> None:
    http = FakeHttp()
    client = Hip4Client(cast(HttpClient, http))

    client.candles.history(
        cast(Any, 0),
        start="2026-05-02T08:00:00Z",
        end="2026-05-02T09:00:00Z",
        interval="1m",
    )

    assert http.calls[0][0] == "/v1/hyperliquid/hip4/candles/0"


def test_hip4_candle_cursor_is_forwarded_opaque_and_limit_is_capped() -> None:
    http = FakeHttp()
    client = Hip4Client(cast(HttpClient, http))

    with pytest.raises(ValueError, match="1000"):
        client.candles.history(
            "0",
            start="2026-05-02T08:00:00Z",
            end="2026-05-02T09:00:00Z",
            limit=1001,
        )

    assert http.calls == []

    client.candles.history(
        "0",
        start="2026-05-02T08:00:00Z",
        end="2026-05-02T09:00:00Z",
        limit=1000,
        cursor="opaque:hip4:candle:page-2",
    )

    assert http.calls[0][1] is not None
    assert http.calls[0][1]["cursor"] == "opaque:hip4:candle:page-2"
    assert http.calls[0][1]["limit"] == 1000


def test_lighter_candles_keep_the_10000_limit_and_opaque_cursor() -> None:
    http = FakeHttp()
    client = LighterClient(cast(HttpClient, http))

    result = client.candles.history(
        "BTC",
        start="2025-08-01T00:00:00Z",
        end="2025-08-01T01:00:00Z",
        limit=10000,
        cursor="opaque:lighter:candle:page-2",
    )

    assert result.data[0].close == 0.25
    assert http.calls[0][0] == "/v1/lighter/candles/BTC"
    assert http.calls[0][1] is not None
    assert http.calls[0][1]["cursor"] == "opaque:lighter:candle:page-2"
    assert http.calls[0][1]["limit"] == 10000


def test_hip4_open_interest_uses_the_family_model_on_history_and_current() -> None:
    response = {
        "data": {
            "coin": "#0",
            "symbol": "#0",
            "outcome_id": 0,
            "side": 0,
            "timestamp": "2026-05-02T08:00:00Z",
            "open_interest": "568048",
            "mark_price": "0.6502",
            "mid_price": "0.65038",
        },
        "meta": {"next_cursor": "opaque:hip4:oi:page-2"},
    }
    http = FakeHttp(response)
    client = Hip4Client(cast(HttpClient, http))

    assert type(client.open_interest).__name__ == "Hip4OpenInterestResource"

    current = client.open_interest.current("#0")
    assert isinstance(current, Hip4OpenInterestRecord)
    assert current.outcome_id == 0
    assert current.side == 0

    response["data"] = [response["data"]]
    history = client.open_interest.history(
        "#0",
        start="2026-05-02T08:00:00Z",
        end="2026-05-02T09:00:00Z",
    )
    assert isinstance(history.data[0], Hip4OpenInterestRecord)
    assert history.data[0].symbol == "#0"
    assert history.next_cursor == "opaque:hip4:oi:page-2"

    client.open_interest.history(
        "#0",
        start="2026-05-02T08:00:00Z",
        end="2026-05-02T09:00:00Z",
        cursor=history.next_cursor,
    )
    assert http.calls[-1][1] is not None
    assert http.calls[-1][1]["cursor"] == "opaque:hip4:oi:page-2"


def test_non_hip4_open_interest_keeps_the_generic_model() -> None:
    response = {
        "data": {
            "coin": "BTC",
            "timestamp": "2026-05-02T08:00:00Z",
            "open_interest": "568048",
        },
        "meta": {"next_cursor": None},
    }
    http = FakeHttp(response)
    client = LighterClient(cast(HttpClient, http))

    current = client.open_interest.current("BTC")
    assert isinstance(current, OpenInterest)
    assert not isinstance(current, Hip4OpenInterestRecord)


def test_lighter_l3_depth_is_an_individual_order_cap() -> None:
    http = FakeHttp()
    resource = L3OrderBookResource(cast(HttpClient, http), "/v1/lighter")

    with pytest.raises(ValueError, match="1 and 250 orders per side"):
        resource.get("BTC", depth=251)

    assert http.calls == []


def test_public_copy_keeps_family_specific_coverage() -> None:
    root = Path(__file__).resolve().parents[1]
    readme = (root / "README.md").read_text()
    exchanges = (root / "oxarchive" / "exchanges.py").read_text()
    types = (root / "oxarchive" / "types.py").read_text()
    l3_resource = (root / "oxarchive" / "resources" / "l3_orderbook.py").read_text()
    spot_resource = (root / "oxarchive" / "resources" / "spot.py").read_text()

    assert "client.hyperliquid.hip4.candles.history" in readme
    assert "2026-05-02" in readme
    assert "~10s" in readme
    assert "250 orders per side" in readme
    assert "March 5, 2026" in readme
    assert "raw ~1 min" not in readme
    assert "no funding, no liquidations, and no candles" not in readme
    assert "no funding / liquidations / candles" not in types
    assert "stored replay only; live bridges paused" in types
    assert "250 orders per side" in l3_resource
    assert "price levels per side" not in l3_resource
    assert "self.candles = CandlesResource" in exchanges
    assert "HIP-4 candle pages are capped at 1,000" in readme
    assert "Lighter candle pages remain capped at 10,000" in readme
    assert "client.spot.candles.history" in readme
    assert "2025-03-22T10:50:22Z" in readme
    assert "1m/5m/15m/30m/1h/4h/1d/1w" in readme
    assert "returns 501" not in readme
    assert "SpotCandlesResource" in exchanges
    assert "no funding, no open interest, no liquidations, and no candles" not in spot_resource
    assert "hype.base_token_name" in readme
    assert "hype.quote_token_name" in readme
    assert "hype.pair_index" in readme
    assert "hype.base}" not in readme
    assert "hype.asset_id" not in readme


def test_spot_exposes_verified_candle_history_and_preserves_negative_capabilities() -> None:
    http = FakeHttp()
    client = SpotClient(cast(HttpClient, http))

    result = client.candles.history(
        "hype-usdc",
        start="2025-03-22T10:50:22Z",
        end="2025-03-22T11:50:22Z",
        interval="5m",
        limit=1000,
        cursor="opaque:spot:candle:page-2",
    )

    assert type(client.candles).__name__ == "SpotCandlesResource"
    assert http.calls[0][0] == "/v1/hyperliquid/spot/candles/HYPE-USDC"
    params = http.calls[0][1]
    assert params is not None
    assert params["interval"] == "5m"
    assert params["limit"] == 1000
    assert params["cursor"] == "opaque:spot:candle:page-2"
    assert result.data[0].close == 0.25
    assert result.next_cursor == "next-cursor"
    assert not hasattr(client, "funding")
    assert not hasattr(client, "open_interest")
    assert not hasattr(client, "liquidations")

    with pytest.raises(ValueError, match="1000"):
        client.candles.history(
            "HYPE-USDC",
            start="2025-03-22T10:50:22Z",
            end="2025-03-22T11:50:22Z",
            limit=1001,
        )
    assert len(http.calls) == 1


def test_spot_candle_history_supports_all_verified_intervals_and_async() -> None:
    http = FakeHttp()
    client = SpotClient(cast(HttpClient, http))
    intervals: tuple[CandleInterval, ...] = ("1m", "5m", "15m", "30m", "1h", "4h", "1d", "1w")

    for interval in intervals:
        client.candles.history(
            "PURR-USDC",
            start="2025-03-22T10:50:22Z",
            end="2025-03-22T11:50:22Z",
            interval=interval,
        )
        assert http.calls[-1][0] == "/v1/hyperliquid/spot/candles/PURR-USDC"
        assert http.calls[-1][1] is not None
        assert http.calls[-1][1]["interval"] == interval

    result = asyncio.run(
        client.candles.ahistory(
            "HYPE-USDC",
            start="2025-03-22T10:50:22Z",
            end="2025-03-22T11:50:22Z",
            interval="1d",
            cursor="opaque:spot:candle:async-page-2",
        )
    )
    assert result.data[0].open == 0.2
    assert http.calls[-1][1] is not None
    assert http.calls[-1][1]["cursor"] == "opaque:spot:candle:async-page-2"
