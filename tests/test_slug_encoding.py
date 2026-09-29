"""HIP-4 outcome by slug: the slug is URL-encoded as one path segment."""

import asyncio

from tests._mock_api import envelope, mock_client

SLUG = "june-fed-rate-change-no change: #2/3"
ENCODED = "/v1/hyperliquid/hip4/outcomes/by-slug/june-fed-rate-change-no%20change%3A%20%232%2F3"


def test_get_by_slug_encodes_the_slug() -> None:
    client, api = mock_client(lambda p, q: envelope({"outcome_id": 1, "sides": []}))
    try:
        client.hyperliquid.hip4.outcomes.get_by_slug(SLUG)
    except Exception:
        pass  # response parsing is not under test; the request path is
    try:
        asyncio.run(client.hyperliquid.hip4.outcomes.aget_by_slug(SLUG))
    except Exception:
        pass
    assert api.raw_paths[:2] == [ENCODED, ENCODED]
