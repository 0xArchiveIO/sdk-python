"""Webhook signature verification.

Deliveries are signed ``HMAC-SHA256(secret, "<t>.<raw body>")`` and sent as
``0xa-signature: t=<unix seconds>,v1=<hex>``, with a second ``v1=`` under the
previous secret during a rotation. These tests sign exactly that way.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any

import pytest

import oxarchive.webhook_signature as webhook_signature
from oxarchive import (
    DEFAULT_TOLERANCE_SECONDS,
    EVENT_ID_HEADER,
    EVENT_TYPE_HEADER,
    SIGNATURE_HEADER,
    WebhookEvent,
    WebhookSignatureError,
    WebhookVerifier,
    parse_signature_header,
    verify_webhook,
    verify_webhook_signature,
)

NOW = 1_790_650_000
NEW_SECRET = "whsec_" + "1f" * 32
OLD_SECRET = "whsec_" + "a0" * 32
EVENT_ID = "7d2e4b10-1a2b-4c3d-8e9f-0a1b2c3d4e5f"

# The exact bytes on the wire. Key order and spacing are deliberately not what
# json.dumps would produce, as a real delivery's need not be.
BODY = (
    b'{"id": "7d2e4b10-1a2b-4c3d-8e9f-0a1b2c3d4e5f", "data": {"symbol": "BTC",'
    b' "notional_usd": 312000.5}, "type": "market.liquidation",'
    b' "observed_at": "2026-09-29T02:00:00.500Z", "schema_version": 1}'
)


def sign(secret: str, body: bytes, t: int = NOW) -> str:
    return hmac.new(secret.encode("utf-8"), f"{t}.".encode() + body, hashlib.sha256).hexdigest()


def headers(*secrets: str, t: int = NOW, body: bytes = BODY) -> dict[str, str]:
    signatures = ",".join(f"v1={sign(s, body, t)}" for s in secrets)
    return {
        SIGNATURE_HEADER: f"t={t},{signatures}",
        EVENT_ID_HEADER: EVENT_ID,
        EVENT_TYPE_HEADER: "market.liquidation",
        "content-type": "application/json",
    }


# ---------------------------------------------------------------------------
# Valid deliveries
# ---------------------------------------------------------------------------


def test_a_valid_delivery_verifies_and_returns_the_event() -> None:
    event = WebhookVerifier(NEW_SECRET).verify(BODY, headers(NEW_SECRET), now=NOW)

    assert isinstance(event, WebhookEvent)
    assert event.id == EVENT_ID
    assert event.type == "market.liquidation"
    assert event.body == BODY
    assert event.payload["data"]["notional_usd"] == 312000.5
    assert event.signature.timestamp == str(NOW)
    assert event.signature.timestamp_seconds == NOW
    assert len(event.signature.signatures) == 1


def test_the_functional_entry_points_agree_with_the_verifier() -> None:
    hdrs = headers(NEW_SECRET)

    event = verify_webhook(BODY, hdrs, NEW_SECRET, now=NOW)
    parsed = verify_webhook_signature(BODY, hdrs[SIGNATURE_HEADER], NEW_SECRET, now=NOW)

    assert event.id == EVENT_ID
    assert parsed.timestamp_seconds == NOW


def test_header_names_are_matched_case_insensitively() -> None:
    hdrs = {k.upper(): v for k, v in headers(NEW_SECRET).items()}

    event = WebhookVerifier(NEW_SECRET).verify(BODY, hdrs, now=NOW)

    assert event.id == EVENT_ID


def test_bytearray_memoryview_and_utf8_text_bodies_verify() -> None:
    verifier = WebhookVerifier(NEW_SECRET)
    hdrs = headers(NEW_SECRET)

    assert verifier.is_valid(bytearray(BODY), hdrs, now=NOW)
    assert verifier.is_valid(memoryview(BODY), hdrs, now=NOW)
    assert verifier.is_valid(BODY.decode("utf-8"), hdrs, now=NOW)


def test_uppercase_hex_in_the_header_is_accepted() -> None:
    hdrs = headers(NEW_SECRET)
    hdrs[SIGNATURE_HEADER] = hdrs[SIGNATURE_HEADER].upper().replace("T=", "t=").replace(
        "V1=", "v1="
    )

    assert WebhookVerifier(NEW_SECRET).is_valid(BODY, hdrs, now=NOW)


def test_the_secret_prefix_is_part_of_the_key() -> None:
    stripped = NEW_SECRET[len("whsec_") :]

    assert not WebhookVerifier(stripped).is_valid(BODY, headers(NEW_SECRET), now=NOW)


# ---------------------------------------------------------------------------
# Tampering
# ---------------------------------------------------------------------------


def test_a_tampered_body_is_rejected() -> None:
    tampered = BODY.replace(b"312000.5", b"912000.5")

    with pytest.raises(WebhookSignatureError) as caught:
        WebhookVerifier(NEW_SECRET).verify(tampered, headers(NEW_SECRET), now=NOW)

    assert caught.value.reason == "signature_mismatch"


def test_a_tampered_timestamp_is_rejected() -> None:
    hdrs = headers(NEW_SECRET)
    hdrs[SIGNATURE_HEADER] = hdrs[SIGNATURE_HEADER].replace(f"t={NOW}", f"t={NOW + 1}")

    with pytest.raises(WebhookSignatureError) as caught:
        WebhookVerifier(NEW_SECRET).verify(BODY, hdrs, now=NOW)

    assert caught.value.reason == "signature_mismatch"


def test_a_wrong_secret_is_rejected() -> None:
    with pytest.raises(WebhookSignatureError) as caught:
        WebhookVerifier(OLD_SECRET).verify(BODY, headers(NEW_SECRET), now=NOW)

    assert caught.value.reason == "signature_mismatch"


def test_a_reserialised_body_does_not_verify() -> None:
    reserialised = json.dumps(json.loads(BODY), separators=(",", ":")).encode()

    assert reserialised != BODY
    assert not WebhookVerifier(NEW_SECRET).is_valid(reserialised, headers(NEW_SECRET), now=NOW)


@pytest.mark.parametrize(
    "signature",
    [
        "zz" * 32,  # not hex
        "ab" * 31,  # too short
        "ab" * 33,  # too long
        "é" * 64,  # non-ASCII: must be a rejection, not a TypeError
    ],
)
def test_malformed_signatures_are_rejections_not_crashes(signature: str) -> None:
    hdrs = headers(NEW_SECRET)
    hdrs[SIGNATURE_HEADER] = f"t={NOW},v1={signature}"

    with pytest.raises(WebhookSignatureError) as caught:
        WebhookVerifier(NEW_SECRET).verify(BODY, hdrs, now=NOW)

    assert caught.value.reason == "signature_mismatch"


# ---------------------------------------------------------------------------
# Rotation: two v1 signatures
# ---------------------------------------------------------------------------


def test_during_a_rotation_a_receiver_holding_either_secret_verifies() -> None:
    hdrs = headers(NEW_SECRET, OLD_SECRET)

    assert WebhookVerifier(NEW_SECRET).is_valid(BODY, hdrs, now=NOW)
    assert WebhookVerifier(OLD_SECRET).is_valid(BODY, hdrs, now=NOW)
    assert WebhookVerifier([NEW_SECRET, OLD_SECRET]).is_valid(BODY, hdrs, now=NOW)


def test_every_v1_is_read_not_just_the_first() -> None:
    parsed = parse_signature_header(headers(NEW_SECRET, OLD_SECRET)[SIGNATURE_HEADER])

    assert parsed.signatures == (sign(NEW_SECRET, BODY), sign(OLD_SECRET, BODY))


def test_the_old_secret_verifies_when_its_signature_comes_second() -> None:
    # A receiver that only reads the first v1 fails here.
    hdrs = headers(NEW_SECRET, OLD_SECRET)

    event = verify_webhook(BODY, hdrs, OLD_SECRET, now=NOW)

    assert event.signature.signatures[1] == sign(OLD_SECRET, BODY)


def test_a_rotation_roll_with_add_and_remove_secret() -> None:
    verifier = WebhookVerifier(OLD_SECRET)
    verifier.add_secret(NEW_SECRET)

    assert verifier.secrets == (NEW_SECRET, OLD_SECRET)
    assert verifier.is_valid(BODY, headers(NEW_SECRET), now=NOW)
    assert verifier.is_valid(BODY, headers(OLD_SECRET), now=NOW)

    verifier.remove_secret(OLD_SECRET)

    assert verifier.secrets == (NEW_SECRET,)
    assert not verifier.is_valid(BODY, headers(OLD_SECRET), now=NOW)
    with pytest.raises(ValueError):
        verifier.remove_secret(NEW_SECRET)


def test_adding_a_secret_twice_keeps_one_copy() -> None:
    verifier = WebhookVerifier(NEW_SECRET)
    verifier.add_secret(NEW_SECRET)

    assert verifier.secrets == (NEW_SECRET,)


# ---------------------------------------------------------------------------
# Replay window
# ---------------------------------------------------------------------------


def test_the_default_replay_window_is_five_minutes() -> None:
    assert DEFAULT_TOLERANCE_SECONDS == 300
    assert WebhookVerifier(NEW_SECRET).tolerance_seconds == 300


def test_an_expired_delivery_is_rejected() -> None:
    stale = headers(NEW_SECRET, t=NOW - 301)

    with pytest.raises(WebhookSignatureError) as caught:
        WebhookVerifier(NEW_SECRET).verify(BODY, stale, now=NOW)

    assert caught.value.reason == "timestamp_out_of_tolerance"


def test_a_delivery_at_the_edge_of_the_window_verifies() -> None:
    assert WebhookVerifier(NEW_SECRET).is_valid(
        BODY, headers(NEW_SECRET, t=NOW - 300), now=NOW
    )


def test_a_timestamp_too_far_in_the_future_is_rejected() -> None:
    with pytest.raises(WebhookSignatureError) as caught:
        WebhookVerifier(NEW_SECRET).verify(BODY, headers(NEW_SECRET, t=NOW + 301), now=NOW)

    assert caught.value.reason == "timestamp_out_of_tolerance"


def test_the_window_is_checked_before_the_signature() -> None:
    # An expired delivery with a valid signature is still rejected as expired.
    stale = headers(NEW_SECRET, t=NOW - 3600)

    with pytest.raises(WebhookSignatureError) as caught:
        verify_webhook(BODY, stale, NEW_SECRET, now=NOW)

    assert caught.value.reason == "timestamp_out_of_tolerance"


def test_a_custom_window_and_zero_to_disable_it() -> None:
    old = headers(NEW_SECRET, t=NOW - 200)

    assert not WebhookVerifier(NEW_SECRET, tolerance_seconds=120).is_valid(BODY, old, now=NOW)
    assert WebhookVerifier(NEW_SECRET, tolerance_seconds=0).is_valid(
        BODY, headers(NEW_SECRET, t=NOW - 10**6), now=NOW
    )


def test_the_real_clock_is_used_when_now_is_not_given(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(webhook_signature.time, "time", lambda: float(NOW + 10))

    assert WebhookVerifier(NEW_SECRET).is_valid(BODY, headers(NEW_SECRET))
    monkeypatch.setattr(webhook_signature.time, "time", lambda: float(NOW + 1000))
    assert not WebhookVerifier(NEW_SECRET).is_valid(BODY, headers(NEW_SECRET))


# ---------------------------------------------------------------------------
# Constant-time comparison
# ---------------------------------------------------------------------------


def test_signatures_are_compared_with_compare_digest(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[Any, Any]] = []
    real = hmac.compare_digest

    def spy(a: Any, b: Any) -> bool:
        calls.append((a, b))
        return real(a, b)

    monkeypatch.setattr(webhook_signature.hmac, "compare_digest", spy)

    assert WebhookVerifier([NEW_SECRET, OLD_SECRET]).is_valid(
        BODY, headers(NEW_SECRET, OLD_SECRET), now=NOW
    )
    # Two secrets by two signatures: every pair is compared, with no early exit.
    assert len(calls) == 4


# ---------------------------------------------------------------------------
# Malformed headers and bad configuration
# ---------------------------------------------------------------------------


def test_a_missing_signature_header_is_rejected() -> None:
    hdrs = headers(NEW_SECRET)
    del hdrs[SIGNATURE_HEADER]

    with pytest.raises(WebhookSignatureError) as caught:
        WebhookVerifier(NEW_SECRET).verify(BODY, hdrs, now=NOW)

    assert caught.value.reason == "missing_header"


@pytest.mark.parametrize(
    "header",
    [
        f"v1={'ab' * 32}",  # no timestamp
        f"t={NOW}",  # no signature
        f"t=abc,v1={'ab' * 32}",  # not an integer
        f"t=١٢٣,v1={'ab' * 32}",  # Unicode digits int() would accept
        f"t=1_000,v1={'ab' * 32}",  # underscores int() would accept
        f"t={'9' * 5000},v1={'ab' * 32}",  # longer than a 64-bit integer
    ],
)
def test_malformed_headers_are_rejected(header: str) -> None:
    hdrs = headers(NEW_SECRET)
    hdrs[SIGNATURE_HEADER] = header

    with pytest.raises(WebhookSignatureError) as caught:
        WebhookVerifier(NEW_SECRET).verify(BODY, hdrs, now=NOW)

    assert caught.value.reason == "malformed_header"


def test_a_verifier_needs_a_text_secret() -> None:
    with pytest.raises(ValueError):
        WebhookVerifier("")
    with pytest.raises(ValueError):
        WebhookVerifier([])
    with pytest.raises(TypeError, match="decode"):
        WebhookVerifier(NEW_SECRET.encode())
    with pytest.raises(TypeError):
        WebhookVerifier([NEW_SECRET, 7])  # type: ignore[list-item]


def test_the_functional_verifier_without_a_secret_is_a_rejection() -> None:
    with pytest.raises(WebhookSignatureError) as caught:
        verify_webhook_signature(BODY, headers(NEW_SECRET)[SIGNATURE_HEADER], [], now=NOW)

    assert caught.value.reason == "no_secrets"


def test_a_body_that_is_not_a_json_object_still_verifies_with_an_empty_payload() -> None:
    body = b"[1, 2, 3]"

    event = verify_webhook(body, headers(NEW_SECRET, body=body), NEW_SECRET, now=NOW)

    assert event.payload == {} and event.body == body
