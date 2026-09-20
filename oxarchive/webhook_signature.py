"""Verification for inbound 0xArchive webhook deliveries.

0xArchive signs every delivery with HMAC-SHA256 over the exact bytes it puts
on the wire. This module verifies that signature, enforces a replay window,
and hands back the parsed event.

The one rule that matters: verify the RAW REQUEST BODY, before any JSON
parser touches it. The body 0xArchive sends is rendered by PostgreSQL, so its
key order and spacing match neither the emitter's struct order nor any JSON
library's default output. Re-serialising a parsed dict produces different
bytes and the signature will never match.

Example (Flask)::

    from flask import Flask, request
    from oxarchive import WebhookVerifier, WebhookSignatureError

    app = Flask(__name__)
    verifier = WebhookVerifier(os.environ["OXARCHIVE_WEBHOOK_SECRET"])

    @app.post("/webhooks/0xarchive")
    def receive():
        try:
            event = verifier.verify(request.get_data(), request.headers)
        except WebhookSignatureError:
            # A bad signature is never worth retrying. Answer 4xx so the
            # delivery is not replayed at you for 24 hours.
            return "", 400
        if already_processed(event.id):   # delivery is at-least-once
            return "", 200
        enqueue(event)                    # do the real work out of band
        return "", 200

Example (FastAPI)::

    @app.post("/webhooks/0xarchive")
    async def receive(request: Request):
        event = verifier.verify(await request.body(), request.headers)
        ...

Both read the raw body. ``request.get_json()`` and a Pydantic model do not.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import re
import time
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Optional, Sequence, Union

__all__ = [
    "DEFAULT_TOLERANCE_SECONDS",
    "SIGNATURE_HEADER",
    "EVENT_ID_HEADER",
    "EVENT_TYPE_HEADER",
    "WebhookSignature",
    "WebhookEvent",
    "WebhookSignatureError",
    "WebhookVerifier",
    "parse_signature_header",
    "verify_webhook_signature",
    "verify_webhook",
]

SIGNATURE_HEADER = "0xa-signature"
"""Header carrying the timestamp and one or more HMAC signatures."""

EVENT_ID_HEADER = "0xa-event-id"
"""Header carrying the event UUID. Deduplicate on this value."""

EVENT_TYPE_HEADER = "0xa-event-type"
"""Header carrying the event type, for example ``account.fill``."""

DEFAULT_TOLERANCE_SECONDS = 300
"""Default replay window, in seconds (5 minutes).

0xArchive re-signs with a fresh timestamp on every attempt, including retries
and manual redeliveries, so a legitimate delivery is never stale by more than
network and clock skew. A tight window is safe here.
"""

_SIGNATURE_SCHEME = "v1"

# The server emits `t` as a plain decimal integer and each `v1` as 64
# lowercase hex characters. Both patterns are enforced rather than assumed,
# because the header is attacker-controlled and Python is generous in ways
# that turn a rejection into a crash: `int()` happily parses Unicode digits,
# underscores, and surrounding whitespace, and `hmac.compare_digest` raises
# TypeError on a string with any non-ASCII character in it. A receiver that
# raises where it should have returned 4xx answers 5xx instead, and a 5xx is
# the one response that makes 0xArchive replay the delivery for 24 hours.
#
# The digit count is bounded for the same reason. Python 3.11 and later
# refuse `int()` on a string of more than 4300 digits, so an unbounded pattern
# waves `t=` followed by five thousand nines through the shape check and into
# a ValueError. Nineteen digits is the full width of the signed 64-bit integer
# the server puts there. A real timestamp is ten.
_DECIMAL_INTEGER = re.compile(r"\A-?[0-9]{1,19}\Z")
_LOWER_HEX = re.compile(r"\A[0-9a-f]+\Z")


class WebhookSignatureError(Exception):
    """A delivery failed verification.

    Respond to the sender with a 4xx status when this is raised. A 5xx tells
    0xArchive to retry, which replays the same unverifiable delivery at you
    for up to 24 hours.

    Attributes:
        reason: Machine-readable cause. One of ``missing_header``,
            ``malformed_header``, ``timestamp_out_of_tolerance``,
            ``no_secrets``, or ``signature_mismatch``.
    """

    def __init__(self, message: str, reason: str):
        super().__init__(message)
        self.message = message
        self.reason = reason


@dataclass(frozen=True)
class WebhookSignature:
    """The parsed contents of the ``0xa-signature`` header."""

    timestamp: str
    """The timestamp exactly as it appeared in the header.

    This literal substring is what goes back into the signed string. Never
    reformat it: parse a copy for the freshness check instead.
    """

    timestamp_seconds: int
    """``timestamp`` as an integer. Unix SECONDS, not milliseconds."""

    signatures: tuple[str, ...]
    """Every ``v1=`` value in the header, lowercased.

    Normally one. Two during a secret rotation overlap, where the second is
    the same payload signed with the previous secret.
    """


@dataclass(frozen=True)
class WebhookEvent:
    """A delivery whose signature has been verified."""

    id: str
    """The event UUID, from ``0xa-event-id``.

    Stable across retries and across manual redelivery. This is the value to
    deduplicate on: delivery is at-least-once.
    """

    type: str
    """The event type, from ``0xa-event-type``, for example ``account.fill``."""

    body: bytes
    """The exact bytes that were signed and verified."""

    signature: WebhookSignature
    """The verified signature envelope."""

    payload: dict[str, Any] = field(default_factory=dict)
    """The body parsed as JSON.

    Read the event data from here. Do not re-serialise it and expect the
    bytes to match ``body``.
    """


def _as_bytes(body: Union[bytes, bytearray, memoryview, str]) -> bytes:
    """Coerce a body to the bytes that were signed.

    A ``str`` is encoded as UTF-8, which is what the server emitted. Passing
    raw bytes straight through avoids the question entirely and is preferred.
    """
    if isinstance(body, str):
        return body.encode("utf-8")
    if isinstance(body, (bytearray, memoryview)):
        return bytes(body)
    return body


def _lookup_header(headers: Mapping[str, Any], name: str) -> Optional[str]:
    """Case-insensitive header lookup.

    HTTP header names are case-insensitive and 0xArchive emits them
    lowercase, but proxies and frameworks re-case freely, so nothing here
    depends on the emitted spelling.
    """
    getter = getattr(headers, "get", None)
    if getter is not None:
        # Multidicts such as Werkzeug's and Starlette's are already
        # case-insensitive; try the cheap path first.
        found = getter(name)
        if found is not None:
            return str(found)

    wanted = name.lower()
    for key, value in headers.items():
        if str(key).lower() == wanted:
            return str(value)
    return None


def _normalise_secrets(secret: Union[str, Iterable[str]]) -> tuple[str, ...]:
    """Accept one secret or several, and drop empties.

    Anything that is not text is refused here, where it surfaces as a startup
    error with a message that names the fix. A secret read as bytes is the
    case worth naming: ``bytes`` is iterable, so it used to fall through as a
    sequence of integers, build a verifier that looked healthy, and then raise
    ``AttributeError`` inside the HMAC on every delivery, which is a 5xx and
    therefore 24 hours of retries.
    """
    if isinstance(secret, str):
        candidates: Sequence[Any] = [secret]
    elif isinstance(secret, (bytes, bytearray, memoryview)):
        candidates = [secret]
    else:
        candidates = list(secret)

    for item in candidates:
        if isinstance(item, (bytes, bytearray, memoryview)):
            raise TypeError(
                "A signing secret must be a string. Decode it first: "
                'secret.decode("utf-8").'
            )
        if not isinstance(item, str):
            raise TypeError(
                f"A signing secret must be a string, not {type(item).__name__}."
            )
    return tuple(s for s in candidates if s)


def parse_signature_header(header: str) -> WebhookSignature:
    """Parse a ``0xa-signature`` header value.

    The grammar is ``t=<unix seconds>,v1=<64 hex>[,v1=<64 hex>]``: comma
    separated, no spaces. Every ``v1`` is collected, not just the first. A
    header with only the first signature read is the classic rotation bug:
    it works until the day someone rotates a secret, then fails intermittently
    for 24 hours.

    Args:
        header: The raw header value.

    Returns:
        The parsed timestamp and every signature in the header.

    Raises:
        WebhookSignatureError: The header is malformed, has no timestamp, has
            a non-integer timestamp, or carries no ``v1`` signature.
    """
    timestamp: Optional[str] = None
    signatures: list[str] = []

    for element in header.split(","):
        key, sep, value = element.strip().partition("=")
        if not sep:
            continue
        if key == "t" and timestamp is None:
            timestamp = value
        elif key == _SIGNATURE_SCHEME:
            signatures.append(value.lower())

    if timestamp is None:
        raise WebhookSignatureError(
            f"{SIGNATURE_HEADER} has no 't=' timestamp.", "malformed_header"
        )
    if not signatures:
        raise WebhookSignatureError(
            f"{SIGNATURE_HEADER} has no 'v1=' signature.", "malformed_header"
        )
    if not _DECIMAL_INTEGER.match(timestamp):
        raise WebhookSignatureError(
            f"{SIGNATURE_HEADER} timestamp '{timestamp}' is not a decimal integer.",
            "malformed_header",
        )
    timestamp_seconds = int(timestamp)

    return WebhookSignature(
        timestamp=timestamp,
        timestamp_seconds=timestamp_seconds,
        signatures=tuple(signatures),
    )


def verify_webhook_signature(
    body: Union[bytes, bytearray, memoryview, str],
    signature_header: str,
    secret: Union[str, Iterable[str]],
    *,
    tolerance_seconds: int = DEFAULT_TOLERANCE_SECONDS,
    now: Optional[float] = None,
) -> WebhookSignature:
    """Verify a signature header against a body and one or more secrets.

    The signed string is ``<timestamp>.<body>``: the literal timestamp from
    the header, one ASCII full stop, then the raw body bytes. Nothing else is
    covered, so neither the event id, the event type, the destination URL, nor
    any other header is authenticated.

    Args:
        body: The RAW request body. Bytes are preferred; a ``str`` is encoded
            as UTF-8. Never pass a re-serialised dict.
        signature_header: The ``0xa-signature`` header value.
        secret: The endpoint signing secret (``whsec_`` followed by 64 hex
            characters), or several of them. Pass both the new and the
            previous secret while a rotation window is open. The ``whsec_``
            prefix is part of the key: do not strip it, and do not decode the
            hex.
        tolerance_seconds: Replay window in seconds, compared as an absolute
            difference so a receiver clock running behind the server still
            verifies. Pass ``0`` to disable the check, which is only
            reasonable when replaying a captured delivery in a test.
        now: Unix seconds to treat as the current time. For tests.

    Returns:
        The verified signature envelope.

    Raises:
        WebhookSignatureError: No secrets were supplied, the header is
            malformed, the timestamp is outside the tolerance, or no
            signature matched.
    """
    secrets = _normalise_secrets(secret)
    if not secrets:
        raise WebhookSignatureError("No signing secret was supplied.", "no_secrets")

    parsed = parse_signature_header(signature_header)

    if tolerance_seconds > 0:
        current = time.time() if now is None else now
        drift = abs(int(current) - parsed.timestamp_seconds)
        if drift > tolerance_seconds:
            raise WebhookSignatureError(
                f"Delivery timestamp is {drift}s away from now, outside the "
                f"{tolerance_seconds}s tolerance.",
                "timestamp_out_of_tolerance",
            )

    signed_payload = parsed.timestamp.encode("ascii") + b"." + _as_bytes(body)

    matched = False
    for key in secrets:
        expected = hmac.new(
            key.encode("utf-8"), signed_payload, hashlib.sha256
        ).hexdigest()
        for candidate in parsed.signatures:
            # A candidate that is not exactly as long as the digest, or is
            # not lowercase hex, cannot match. Screen it out here rather than
            # handing it to compare_digest, which raises TypeError on any
            # non-ASCII string: a malformed signature must be a rejection,
            # never an exception the receiver did not plan for.
            if len(candidate) != len(expected) or not _LOWER_HEX.match(candidate):
                continue
            # compare_digest rather than ==, so a mismatch does not leak the
            # position of the first differing character through timing. The
            # loop does not break early: at most two secrets by two
            # signatures, so finishing it costs nothing.
            if hmac.compare_digest(candidate, expected):
                matched = True
    if not matched:
        raise WebhookSignatureError(
            "No signature in the header matched the supplied secrets.",
            "signature_mismatch",
        )

    return parsed


def verify_webhook(
    body: Union[bytes, bytearray, memoryview, str],
    headers: Mapping[str, Any],
    secret: Union[str, Iterable[str]],
    *,
    tolerance_seconds: int = DEFAULT_TOLERANCE_SECONDS,
    now: Optional[float] = None,
) -> WebhookEvent:
    """Verify a delivery and return the parsed event.

    Args:
        body: The RAW request body, ideally as bytes.
        headers: The request headers. Any mapping works; the lookup is
            case-insensitive.
        secret: One signing secret, or several during a rotation window.
        tolerance_seconds: Replay window in seconds. Defaults to 5 minutes.
        now: Unix seconds to treat as the current time. For tests.

    Returns:
        The verified event, with its id, type, raw bytes, and parsed payload.

    Raises:
        WebhookSignatureError: The ``0xa-signature`` header is missing or
            malformed, the timestamp is stale, or no signature matched.
    """
    signature_header = _lookup_header(headers, SIGNATURE_HEADER)
    if not signature_header:
        raise WebhookSignatureError(
            f"Request has no {SIGNATURE_HEADER} header.", "missing_header"
        )

    raw = _as_bytes(body)
    signature = verify_webhook_signature(
        raw,
        signature_header,
        secret,
        tolerance_seconds=tolerance_seconds,
        now=now,
    )

    try:
        payload = json.loads(raw.decode("utf-8")) if raw else {}
    except (UnicodeDecodeError, ValueError):
        payload = {}
    if not isinstance(payload, dict):
        payload = {}

    return WebhookEvent(
        id=_lookup_header(headers, EVENT_ID_HEADER) or "",
        type=_lookup_header(headers, EVENT_TYPE_HEADER) or "",
        body=raw,
        signature=signature,
        payload=payload,
    )


class WebhookVerifier:
    """Holds the signing secrets for one endpoint and verifies deliveries.

    Rotating a secret is a three-step move, and this class is built for the
    middle step. ``POST /v1/webhooks/endpoints/{id}/rotate`` returns the new
    secret and keeps the previous one valid for 24 hours, signing every
    delivery with both. Hold both here, deploy, then drop the old one before
    the window closes.

    Two constraints the server imposes, worth knowing before you script a
    rotation:

    - Only ONE previous secret is carried. Rotating twice inside the window
      overwrites it and the original stops verifying immediately.
    - The window is measured on the server. A receiver cannot extend it.

    Example::

        verifier = WebhookVerifier(current_secret)

        # Mid-rotation: accept both until the old one is retired.
        verifier = WebhookVerifier([new_secret, previous_secret])

        event = verifier.verify(raw_body_bytes, request.headers)
    """

    def __init__(
        self,
        secret: Union[str, Iterable[str]],
        *,
        tolerance_seconds: int = DEFAULT_TOLERANCE_SECONDS,
    ):
        """Create a verifier.

        Args:
            secret: One signing secret, or several to accept during a
                rotation window.
            tolerance_seconds: Replay window in seconds. Defaults to 5
                minutes.

        Raises:
            ValueError: No non-empty secret was supplied.
            TypeError: A secret was supplied that is not a string.
        """
        secrets = _normalise_secrets(secret)
        if not secrets:
            raise ValueError(
                "WebhookVerifier needs at least one signing secret. Endpoint "
                "secrets are returned once, by POST /v1/webhooks/endpoints and "
                "by POST /v1/webhooks/endpoints/{id}/rotate."
            )
        self._secrets = secrets
        self.tolerance_seconds = tolerance_seconds

    @property
    def secrets(self) -> tuple[str, ...]:
        """The secrets this verifier will accept, in the order supplied."""
        return self._secrets

    def add_secret(self, secret: str) -> None:
        """Start accepting another secret, newest first.

        Call this with the secret returned by a rotation, before deploying
        the code that stops using the old one.

        Args:
            secret: The additional signing secret.

        Raises:
            ValueError: The secret is empty.
            TypeError: The secret is not a string.
        """
        normalised = _normalise_secrets([secret])
        if not normalised:
            raise ValueError("Signing secret must not be empty.")
        if normalised[0] not in self._secrets:
            self._secrets = (normalised[0],) + self._secrets

    def remove_secret(self, secret: str) -> None:
        """Stop accepting a secret, once its rotation window has closed.

        Args:
            secret: The signing secret to drop.

        Raises:
            ValueError: Dropping it would leave no secrets at all.
        """
        remaining = tuple(s for s in self._secrets if s != secret)
        if not remaining:
            raise ValueError("A verifier must keep at least one signing secret.")
        self._secrets = remaining

    def verify(
        self,
        body: Union[bytes, bytearray, memoryview, str],
        headers: Mapping[str, Any],
        *,
        now: Optional[float] = None,
    ) -> WebhookEvent:
        """Verify a delivery and return the parsed event.

        Args:
            body: The RAW request body, ideally as bytes.
            headers: The request headers, looked up case-insensitively.
            now: Unix seconds to treat as the current time. For tests.

        Returns:
            The verified event.

        Raises:
            WebhookSignatureError: The delivery did not verify. Answer 4xx.
        """
        return verify_webhook(
            body,
            headers,
            self._secrets,
            tolerance_seconds=self.tolerance_seconds,
            now=now,
        )

    def is_valid(
        self,
        body: Union[bytes, bytearray, memoryview, str],
        headers: Mapping[str, Any],
        *,
        now: Optional[float] = None,
    ) -> bool:
        """Verify a delivery, returning a bool instead of raising.

        Prefer :meth:`verify`: the exception carries a ``reason`` that tells
        a stale clock apart from a wrong secret, and you usually want that in
        the log line.

        Args:
            body: The RAW request body.
            headers: The request headers.
            now: Unix seconds to treat as the current time. For tests.

        Returns:
            True when the delivery verified.
        """
        try:
            self.verify(body, headers, now=now)
        except WebhookSignatureError:
            return False
        return True
