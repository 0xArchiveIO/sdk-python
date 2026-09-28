"""Times without a time zone are UTC, whatever the machine's local zone.

Every test runs with the process time zone set to America/New_York (UTC-4 in
September), where reading a naive time as local time would shift it by four
hours.
"""

from __future__ import annotations

import os
import time
from datetime import date, datetime, timedelta, timezone
from typing import Any, Iterator

import pytest
from _mock_api import envelope, mock_client

from oxarchive._time import to_unix_ms

SEPT_1_UTC = 1788220800000  # 2026-09-01T00:00:00Z
SEPT_1_NOON_UTC = 1788264000000  # 2026-09-01T12:00:00Z


@pytest.fixture(autouse=True)
def new_york_time_zone() -> Iterator[None]:
    if not hasattr(time, "tzset"):
        pytest.skip("time.tzset is not available on this platform")
    previous = os.environ.get("TZ")
    os.environ["TZ"] = "America/New_York"
    time.tzset()
    try:
        # The zone really is in effect: local midnight is 04:00 UTC.
        assert datetime(2026, 9, 1).timestamp() * 1000 == SEPT_1_UTC + 4 * 3_600_000
        yield
    finally:
        if previous is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = previous
        time.tzset()


@pytest.mark.parametrize(
    "value",
    [
        "2026-09-01",
        "2026-09-01T00:00:00",
        "2026-09-01T00:00:00.000",
        "2026-09-01 00:00:00",
        "2026-09-01T00:00:00Z",
        "2026-09-01T00:00:00z",
        "2026-09-01T00:00:00+00:00",
        "2026-08-31T20:00:00-04:00",
        "1788220800000",
        " 1788220800000 ",
        SEPT_1_UTC,
        datetime(2026, 9, 1),
        datetime(2026, 9, 1, tzinfo=timezone.utc),
        datetime(2026, 9, 1, 2, tzinfo=timezone(timedelta(hours=2))),
        date(2026, 9, 1),
    ],
)
def test_every_form_of_september_first_is_the_same_instant(value: Any) -> None:
    assert to_unix_ms(value) == SEPT_1_UTC


def test_milliseconds_are_exact() -> None:
    assert to_unix_ms("2026-09-01T12:00:00.123") == SEPT_1_NOON_UTC + 123
    assert to_unix_ms(datetime(2026, 9, 1, 12, 0, 0, 123999)) == SEPT_1_NOON_UTC + 123


def test_none_passes_through_and_bad_values_raise() -> None:
    assert to_unix_ms(None) is None
    for bad in ("yesterday", "", True, 1.5, [1]):
        with pytest.raises(ValueError, match="start"):
            to_unix_ms(bad, "start")


def test_resources_send_naive_times_as_utc() -> None:
    def responder(path: str, q: dict[str, str]) -> dict[str, Any]:
        if path.endswith("/positions") and "/wallets/" in path:
            return envelope({"positions": [], "account": None})
        return envelope([])

    client, api = mock_client(responder)

    client.hyperliquid.trades.list("BTC", start="2026-09-01", end="2026-09-01T12:00:00")
    client.lighter.positions.changes(
        7, start=datetime(2026, 9, 1), end=datetime(2026, 9, 1, 12)
    )
    client.hyperliquid.positions.get(
        "0x1111111111111111111111111111111111111111", timestamp="2026-09-01T12:00:00"
    )
    client.hyperliquid.positions.market("BTC", hour="2026-09-01T12:00:00")
    client.rh_lighter.liquidations.history("BTC", start="2026-09-01", end="2026-09-01T12:00")

    sent = [q for _, q in api.calls]
    assert sent[0]["start"] == str(SEPT_1_UTC) and sent[0]["end"] == str(SEPT_1_NOON_UTC)
    assert sent[1]["start"] == str(SEPT_1_UTC) and sent[1]["end"] == str(SEPT_1_NOON_UTC)
    assert sent[2]["timestamp"] == str(SEPT_1_NOON_UTC)
    assert sent[3]["hour"] == str(SEPT_1_NOON_UTC)
    assert sent[4]["start"] == str(SEPT_1_UTC) and sent[4]["end"] == str(SEPT_1_NOON_UTC)
