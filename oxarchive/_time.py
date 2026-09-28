"""Timestamp conversion shared by every resource.

The API takes times as Unix milliseconds. Every method that accepts a
:data:`~oxarchive.types.Timestamp` converts it here, so a time means the same
instant everywhere in the SDK, whatever the local time zone of the machine:

- ``int``: Unix milliseconds, sent unchanged.
- ``datetime`` with a time zone: that instant.
- ``datetime`` without a time zone: read as UTC.
- ``date``: midnight UTC of that day.
- ``str`` of digits: Unix milliseconds.
- any other ``str``: ISO 8601 (a trailing ``Z`` is accepted). Without an
  offset it is read as UTC; a date alone (``"2026-09-01"``) is midnight UTC.
"""

from __future__ import annotations

import numbers
import re
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional

_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)
_ONE_MS = timedelta(milliseconds=1)
_DIGITS = re.compile(r"-?\d+")
_ERROR = "must be Unix milliseconds, an ISO 8601 string, a datetime or a date"


def _datetime_ms(value: datetime) -> int:
    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        value = value.replace(tzinfo=timezone.utc)
    return (value - _EPOCH) // _ONE_MS


def to_unix_ms(ts: Any, name: str = "timestamp") -> Optional[int]:
    """Convert a timestamp to Unix milliseconds, reading times without a zone as UTC.

    ``None`` passes through as ``None``. Anything that is not a timestamp
    raises ``ValueError``.
    """
    if ts is None:
        return None
    if isinstance(ts, bool):
        raise ValueError(f"{name} {_ERROR}")
    if isinstance(ts, int):
        return ts
    if isinstance(ts, numbers.Integral):
        return int(ts)
    if isinstance(ts, datetime):
        return _datetime_ms(ts)
    if isinstance(ts, date):
        return _datetime_ms(datetime(ts.year, ts.month, ts.day))
    if isinstance(ts, str):
        text = ts.strip()
        if _DIGITS.fullmatch(text):
            return int(text)
        if text.endswith(("Z", "z")):
            text = text[:-1] + "+00:00"
        try:
            return _datetime_ms(datetime.fromisoformat(text))
        except ValueError:
            raise ValueError(f"{name} {_ERROR} (got {ts!r})") from None
    raise ValueError(f"{name} {_ERROR} (got {type(ts).__name__})")


__all__ = ["to_unix_ms"]
