import asyncio
from pathlib import Path
from typing import Any, cast

import pytest

from oxarchive.exchanges import Hip4Client
from oxarchive.http import HttpClient
from oxarchive.resources.l3_orderbook import L3OrderBookResource


class FakeHttp:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any] | None]] = []

    def get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        self.calls.append((path, params))
        return {
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
