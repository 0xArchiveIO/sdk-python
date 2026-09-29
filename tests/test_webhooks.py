"""Webhooks resource: every route's method, path, query, body and parsing.

Nothing here reaches the network. Requests go through the real ``Client`` and
``HttpClient`` into an ``httpx.MockTransport``, and response bodies are shaped
like the API's JSON.
"""

from __future__ import annotations

import asyncio
import copy
import json
from datetime import date, datetime, timezone
from typing import Any, Callable, Optional

import httpx
import pytest

from oxarchive import (
    Client,
    OxArchiveError,
    WebhookDelivery,
    WebhookDeliveryQueued,
    WebhookDryRun,
    WebhookEndpoint,
    WebhookEndpointCreated,
    WebhookEndpointSecret,
    WebhookEstimate,
    WebhookEventType,
    WebhookLimits,
    WebhookRedelivery,
    WebhookSubscription,
    WebhookSubscriptionCondition,
    WebhookSubscriptionConfig,
    WebhookSubscriptionResume,
    WebhookSubscriptionResumeAll,
    WebhookWatchedAddress,
)

ENDPOINT_ID = "b9807e65-8952-4d32-a877-a45c8b54c5aa"
SUBSCRIPTION_ID = "f5064079-0163-41c6-b606-b04d17e25a04"
DELIVERY_ID = "3c1f0a52-8d6b-4f0e-9b1a-6f2c4d8e9a10"
EVENT_ID = "7d2e4b10-1a2b-4c3d-8e9f-0a1b2c3d4e5f"
ADDRESS_ID = "cebc5b17-a907-4f0a-bbf4-4de2d8c399a9"
WALLET = "0x6b9e773128f453f5c2c60935ee2de2cbc5390a24"
SECRET = "whsec_" + "ab" * 32

# ---------------------------------------------------------------------------
# Fixtures shaped like the API's JSON
# ---------------------------------------------------------------------------

EVENT_TYPE: dict[str, Any] = {
    "type": "market.liquidation",
    "schema_version": 1,
    "live": True,
    "scope": "public",
    "venues": ["hyperliquid", "hip3", "lighter"],
    "filters": ["venue", "symbols"],
    "params": {
        "window_s": {
            "type": "integer",
            "unit": "s",
            "default": 300,
            "min": 60,
            "max": 3600,
            "description": "Rolling window.",
        },
        "threshold_mode": {"type": "string", "default": "usd", "enum": ["usd", "pct_oi"]},
    },
    "metrics": {
        "notional_usd": {"type": "number", "unit": "USD"},
        "side": {"type": "enum", "values": ["long", "short"]},
    },
    "cost_floor": {"metric": "notional_usd", "min": 100, "note": "scan floor"},
    "latency_class": "seconds",
    "description": "A liquidation on a covered venue.",
    "filters_example": {"venue": "hyperliquid", "symbols": ["BTC"]},
    "operators": {
        "any": ["is_empty", "is_not_empty"],
        "number": ["greater_than", "between"],
        "text": ["equal", "contains"],
    },
}

LIMITS: dict[str, Any] = {
    "plan": "pro",
    "plan_label": "Pro",
    "included": True,
    "preview_included": True,
    "endpoints": {"used": 1, "limit": 4, "remaining": 3},
    "subscriptions": {"used": 9, "limit": 40, "remaining": 31},
    "watched_addresses": {"used": 2, "limit": 15, "remaining": 13},
    "deliveries_per_day": {
        "used": 412,
        "limit": 50000,
        "remaining": 49588,
        "unlimited": False,
        "resets_at": "2026-09-30T00:00:00Z",
        "resets_at_note": "The reset time is the budget's, not the pause's.",
    },
    "paused_subscriptions": {
        "count": 2,
        "earliest_paused_at": "2026-09-29T01:15:00Z",
        "reasons": ["deliveries_per_day_cap"],
        "message": "2 rules are paused.",
    },
}

ENDPOINT: dict[str, Any] = {
    "id": ENDPOINT_ID,
    "url": "https://example.com/hooks/0xarchive",
    "description": "Desk alerts",
    "status": "active",
    "consecutive_failures": 0,
    "created_at": "2026-09-21T02:02:04.460276Z",
    "format": "json",
}

CONFIG: dict[str, Any] = {
    "addresses": [WALLET],
    "conditions": [
        {"metric": "notional_usd", "op": "greater_than_or_equal", "value": 250000},
        {"metric": "taker", "op": "equal", "value": True},
    ],
    "min_notional_usd": 250000.0,
    "params": {"max_age_s": 3600},
}

SUBSCRIPTION: dict[str, Any] = {
    "id": SUBSCRIPTION_ID,
    "endpoint_id": ENDPOINT_ID,
    "event_type": "account.fill",
    "filters": CONFIG,
    "enabled": True,
    "created_at": "2026-09-21T02:04:52.698775Z",
    "status": "active",
    "paused_at": None,
    "pause_reason": None,
    "suppressed_count": 0,
    "suppressed_first_at": None,
    "suppressed_last_at": None,
    "last_paused_at": None,
    "last_resumed_at": None,
    "last_pause_reason": None,
    "last_suppressed_count": 0,
    "last_suppressed_first_at": None,
    "last_suppressed_last_at": None,
}

PAUSED_SUBSCRIPTION: dict[str, Any] = {
    **SUBSCRIPTION,
    "status": "auto_paused",
    "pause_message": "This rule was paused because the account reached its daily limit.",
    "paused_at": "2026-09-29T01:15:00Z",
    "pause_reason": "deliveries_per_day_cap",
    "suppressed_count": 17,
    "suppressed_first_at": "2026-09-29T01:15:02Z",
    "suppressed_last_at": "2026-09-29T02:40:00Z",
}

GAP: dict[str, Any] = {
    "paused_at": "2026-09-29T01:15:00Z",
    "resumed_at": "2026-09-29T03:00:00Z",
    "replay_window": {"start": "2026-09-29T01:15:00Z", "end": "2026-09-29T03:00:00Z"},
    "reason": "deliveries_per_day_cap",
    "pause_message": "Paused at the daily limit.",
    "suppressed_count": 17,
    "counted": True,
    "suppressed_first_at": "2026-09-29T01:15:02Z",
    "suppressed_last_at": "2026-09-29T02:40:00Z",
    "note": "Re-read the window from the REST routes.",
}

DELIVERY: dict[str, Any] = {
    "id": DELIVERY_ID,
    "event_id": EVENT_ID,
    "event_type": "market.liquidation",
    "state": "failed",
    "attempts": 3,
    "last_status_code": 500,
    "last_error": "HTTP 500",
    "last_latency_ms": 142,
    "next_attempt_at": "2026-09-29T02:10:00Z",
    "delivered_at": None,
    "created_at": "2026-09-29T02:00:00Z",
    "payload": {
        "id": EVENT_ID,
        "type": "market.liquidation",
        "schema_version": 1,
        "observed_at": "2026-09-29T02:00:00.500Z",
        "data": {"symbol": "BTC", "notional_usd": 312000.5},
    },
}

REDELIVERY: dict[str, Any] = {
    "delivery_id": DELIVERY_ID,
    "event_id": EVENT_ID,
    "event_type": "market.liquidation",
    "state": "pending",
    "attempts": 0,
    "next_attempt_at": "2026-09-29T02:11:00Z",
}

ADDRESS: dict[str, Any] = {
    "id": ADDRESS_ID,
    "address": WALLET,
    "label": "Desk 1",
    "created_at": "2026-09-21T02:04:12.377291Z",
}

OCCURRENCE: dict[str, Any] = {
    "observed_at_estimate": "2026-09-29T01:59:59.100Z",
    "data": {"symbol": "BTC", "notional_usd": 612000.0, "side": "long"},
}

DRY_RUN: dict[str, Any] = {
    "event_type": "market.liquidation",
    "window": {"from": "2026-09-28T02:00:00Z", "to": "2026-09-29T02:00:00Z"},
    "matched": 37,
    "truncated": True,
    "occurrences": [OCCURRENCE],
}

ESTIMATE: dict[str, Any] = {
    "event_type": "market.liquidation",
    "window": {"from": "2026-09-22T02:00:00Z", "to": "2026-09-29T02:00:00Z"},
    "days": 7,
    "total": 84,
    "per_day": [{"date": "2026-09-23", "count": 12}, {"date": "2026-09-24", "count": 9}],
    "per_day_p50": 11,
    "per_day_max": 26,
    "primary_metric": "notional_usd",
    "ladder": [{"value": 250000, "per_day": 3.4}, {"value": 500000, "per_day": 1.1}],
    "distribution": {"n": 842, "p50": 18400, "p90": 132000, "p99": 910000, "max": 4210000},
    "sample": [OCCURRENCE],
    "basis": {"mode": "sampled", "note": "Scaled from a capped scan."},
}


# ---------------------------------------------------------------------------
# A mocked API that answers by (method, path)
# ---------------------------------------------------------------------------


class Recorded:
    def __init__(self, request: httpx.Request) -> None:
        self.method = request.method
        self.path = request.url.path
        self.raw_path = request.url.raw_path.decode().split("?", 1)[0]
        self.query = dict(request.url.params)
        self.body: Optional[Any] = json.loads(request.content) if request.content else None


def webhook_client(
    answer: Any, status: int = 200
) -> tuple[Client, list[Recorded]]:
    """A client whose every request is answered with ``answer`` and recorded."""
    seen: list[Recorded] = []

    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(Recorded(request))
        return httpx.Response(status, json=copy.deepcopy(answer))

    client = Client(api_key="0xa_test", base_url="https://api.example.test")
    transport = httpx.MockTransport(handle)
    http = client._http
    http._client = httpx.Client(
        base_url=http.base_url, headers=http._get_headers(), transport=transport
    )
    http._async_client = httpx.AsyncClient(
        base_url=http.base_url, headers=http._get_headers(), transport=transport
    )
    return client, seen


def ok(data: Any, **extra: Any) -> dict[str, Any]:
    return {"success": True, "data": data, **extra}


def _utc(text: str) -> datetime:
    return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(timezone.utc)


# ---------------------------------------------------------------------------
# Every operation, sync and async: method, path, query, body
# ---------------------------------------------------------------------------

Call = Callable[[Client], Any]

ROUTES: list[tuple[str, Call, Call, str, str, dict[str, str], Optional[dict[str, Any]], Any]] = [
    (
        "event_types",
        lambda c: c.webhooks.event_types(),
        lambda c: c.webhooks.aevent_types(),
        "GET",
        "/v1/webhooks/event-types",
        {},
        None,
        ok([EVENT_TYPE]),
    ),
    (
        "limits",
        lambda c: c.webhooks.limits(),
        lambda c: c.webhooks.alimits(),
        "GET",
        "/v1/webhooks/limits",
        {},
        None,
        ok(LIMITS),
    ),
    (
        "list_endpoints",
        lambda c: c.webhooks.list_endpoints(),
        lambda c: c.webhooks.alist_endpoints(),
        "GET",
        "/v1/webhooks/endpoints",
        {},
        None,
        ok([ENDPOINT]),
    ),
    (
        "create_endpoint",
        lambda c: c.webhooks.create_endpoint(ENDPOINT["url"], description="Desk alerts"),
        lambda c: c.webhooks.acreate_endpoint(ENDPOINT["url"], description="Desk alerts"),
        "POST",
        "/v1/webhooks/endpoints",
        {},
        {"url": ENDPOINT["url"], "description": "Desk alerts"},
        ok({**ENDPOINT, "secret": SECRET}, note="Store the secret now; it is not shown again."),
    ),
    (
        "delete_endpoint",
        lambda c: c.webhooks.delete_endpoint(ENDPOINT_ID),
        lambda c: c.webhooks.adelete_endpoint(ENDPOINT_ID),
        "DELETE",
        f"/v1/webhooks/endpoints/{ENDPOINT_ID}",
        {},
        None,
        {"success": True},
    ),
    (
        "enable_endpoint",
        lambda c: c.webhooks.enable_endpoint(ENDPOINT_ID),
        lambda c: c.webhooks.aenable_endpoint(ENDPOINT_ID),
        "POST",
        f"/v1/webhooks/endpoints/{ENDPOINT_ID}/enable",
        {},
        None,
        {"success": True},
    ),
    (
        "rotate_secret",
        lambda c: c.webhooks.rotate_secret(ENDPOINT_ID),
        lambda c: c.webhooks.arotate_secret(ENDPOINT_ID),
        "POST",
        f"/v1/webhooks/endpoints/{ENDPOINT_ID}/rotate",
        {},
        None,
        ok({"secret": SECRET}, note="Previous secret remains valid for 24 hours."),
    ),
    (
        "test_endpoint",
        lambda c: c.webhooks.test_endpoint(ENDPOINT_ID),
        lambda c: c.webhooks.atest_endpoint(ENDPOINT_ID),
        "POST",
        f"/v1/webhooks/endpoints/{ENDPOINT_ID}/test",
        {},
        None,
        ok({"delivery_id": DELIVERY_ID, "event_id": EVENT_ID}),
    ),
    (
        "list_deliveries",
        lambda c: c.webhooks.list_deliveries(ENDPOINT_ID, limit=200),
        lambda c: c.webhooks.alist_deliveries(ENDPOINT_ID, limit=200),
        "GET",
        f"/v1/webhooks/endpoints/{ENDPOINT_ID}/deliveries",
        {"limit": "200"},
        None,
        ok([DELIVERY]),
    ),
    (
        "redeliver",
        lambda c: c.webhooks.redeliver(DELIVERY_ID),
        lambda c: c.webhooks.aredeliver(DELIVERY_ID),
        "POST",
        f"/v1/webhooks/deliveries/{DELIVERY_ID}/redeliver",
        {},
        None,
        ok(REDELIVERY, note="The record is reset in place."),
    ),
    (
        "list_subscriptions",
        lambda c: c.webhooks.list_subscriptions(),
        lambda c: c.webhooks.alist_subscriptions(),
        "GET",
        "/v1/webhooks/subscriptions",
        {},
        None,
        ok([SUBSCRIPTION, PAUSED_SUBSCRIPTION]),
    ),
    (
        "create_subscription",
        lambda c: c.webhooks.create_subscription(ENDPOINT_ID, "account.fill", CONFIG),
        lambda c: c.webhooks.acreate_subscription(ENDPOINT_ID, "account.fill", CONFIG),
        "POST",
        "/v1/webhooks/subscriptions",
        {},
        {"endpoint_id": ENDPOINT_ID, "event_type": "account.fill", "filters": CONFIG},
        ok(SUBSCRIPTION),
    ),
    (
        "update_subscription",
        lambda c: c.webhooks.update_subscription(SUBSCRIPTION_ID, config=CONFIG, enabled=False),
        lambda c: c.webhooks.aupdate_subscription(
            SUBSCRIPTION_ID, config=CONFIG, enabled=False
        ),
        "PATCH",
        f"/v1/webhooks/subscriptions/{SUBSCRIPTION_ID}",
        {},
        {"filters": CONFIG, "enabled": False},
        ok({**SUBSCRIPTION, "enabled": False}),
    ),
    (
        "delete_subscription",
        lambda c: c.webhooks.delete_subscription(SUBSCRIPTION_ID),
        lambda c: c.webhooks.adelete_subscription(SUBSCRIPTION_ID),
        "DELETE",
        f"/v1/webhooks/subscriptions/{SUBSCRIPTION_ID}",
        {},
        None,
        {"success": True},
    ),
    (
        "resume_subscription",
        lambda c: c.webhooks.resume_subscription(SUBSCRIPTION_ID),
        lambda c: c.webhooks.aresume_subscription(SUBSCRIPTION_ID),
        "POST",
        f"/v1/webhooks/subscriptions/{SUBSCRIPTION_ID}/resume",
        {},
        None,
        ok(SUBSCRIPTION, gap=GAP),
    ),
    (
        "resume_all_subscriptions",
        lambda c: c.webhooks.resume_all_subscriptions(),
        lambda c: c.webhooks.aresume_all_subscriptions(),
        "POST",
        "/v1/webhooks/subscriptions/resume",
        {},
        None,
        ok([SUBSCRIPTION], resumed_count=1, gap=GAP),
    ),
    (
        "dry_run",
        lambda c: c.webhooks.dry_run(
            "market.liquidation", {"venue": "hyperliquid"}, lookback_s=86400, limit=5
        ),
        lambda c: c.webhooks.adry_run(
            "market.liquidation", {"venue": "hyperliquid"}, lookback_s=86400, limit=5
        ),
        "POST",
        "/v1/webhooks/subscriptions/dry-run",
        {},
        {
            "event_type": "market.liquidation",
            "config": {"venue": "hyperliquid"},
            "lookback_s": 86400,
            "limit": 5,
        },
        ok(DRY_RUN),
    ),
    (
        "estimate",
        lambda c: c.webhooks.estimate(
            "market.liquidation", {"min_notional_usd": 250000}, lookback_days=7
        ),
        lambda c: c.webhooks.aestimate(
            "market.liquidation", {"min_notional_usd": 250000}, lookback_days=7
        ),
        "POST",
        "/v1/webhooks/subscriptions/estimate",
        {},
        {
            "event_type": "market.liquidation",
            "config": {"min_notional_usd": 250000},
            "lookback_days": 7,
        },
        ok(ESTIMATE),
    ),
    (
        "list_addresses",
        lambda c: c.webhooks.list_addresses(),
        lambda c: c.webhooks.alist_addresses(),
        "GET",
        "/v1/webhooks/addresses",
        {},
        None,
        ok([ADDRESS], limit=15),
    ),
    (
        "add_address",
        lambda c: c.webhooks.add_address(WALLET, label="Desk 1"),
        lambda c: c.webhooks.aadd_address(WALLET, label="Desk 1"),
        "POST",
        "/v1/webhooks/addresses",
        {},
        {"address": WALLET, "label": "Desk 1"},
        ok(ADDRESS, limit=15),
    ),
    (
        "delete_address",
        lambda c: c.webhooks.delete_address(ADDRESS_ID),
        lambda c: c.webhooks.adelete_address(ADDRESS_ID),
        "DELETE",
        f"/v1/webhooks/addresses/{ADDRESS_ID}",
        {},
        None,
        {"success": True},
    ),
]


def test_every_spec_operation_has_a_route_here() -> None:
    assert len(ROUTES) == 21
    assert len({(method, path) for _, _, _, method, path, _, _, _ in ROUTES}) == 21


@pytest.mark.parametrize(
    "name, sync_call, _async_call, method, path, query, body, answer",
    ROUTES,
    ids=[r[0] for r in ROUTES],
)
def test_sync_request_shape(
    name: str,
    sync_call: Call,
    _async_call: Call,
    method: str,
    path: str,
    query: dict[str, str],
    body: Optional[dict[str, Any]],
    answer: Any,
) -> None:
    client, seen = webhook_client(answer)

    sync_call(client)

    assert len(seen) == 1
    assert (seen[0].method, seen[0].path, seen[0].query) == (method, path, query)
    assert seen[0].body == body


@pytest.mark.parametrize(
    "name, sync_call, async_call, method, path, query, body, answer",
    ROUTES,
    ids=[r[0] for r in ROUTES],
)
def test_async_matches_sync(
    name: str,
    sync_call: Call,
    async_call: Call,
    method: str,
    path: str,
    query: dict[str, str],
    body: Optional[dict[str, Any]],
    answer: Any,
) -> None:
    client, seen = webhook_client(answer)

    sync_result = sync_call(client)
    async_result = asyncio.run(async_call(client))

    assert len(seen) == 2
    assert (seen[1].method, seen[1].path, seen[1].query, seen[1].body) == (
        method,
        path,
        query,
        body,
    )
    assert async_result == sync_result


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


def test_event_types_parse_params_metrics_and_cost_floor() -> None:
    client, _ = webhook_client(ok([EVENT_TYPE]))

    [event_type] = client.webhooks.event_types()

    assert isinstance(event_type, WebhookEventType)
    assert event_type.type == "market.liquidation" and event_type.live is True
    assert event_type.params["window_s"].default == 300
    assert event_type.params["window_s"].max == 3600
    assert event_type.params["threshold_mode"].enum == ["usd", "pct_oi"]
    assert event_type.metrics["notional_usd"].unit == "USD"
    assert event_type.metrics["side"].values == ["long", "short"]
    assert event_type.cost_floor is not None
    assert (event_type.cost_floor.metric, event_type.cost_floor.min) == ("notional_usd", 100)
    assert event_type.cost_floor.model_extra == {"note": "scan floor"}
    assert event_type.operators["text"] == ["equal", "contains"]


def test_event_type_without_a_cost_floor() -> None:
    client, _ = webhook_client(ok([{**EVENT_TYPE, "cost_floor": None}]))

    assert client.webhooks.event_types()[0].cost_floor is None


def test_limits_parse_caps_budget_and_paused_count() -> None:
    client, _ = webhook_client(ok(LIMITS))

    limits = client.webhooks.limits()

    assert isinstance(limits, WebhookLimits)
    assert limits.plan == "pro" and limits.included and limits.preview_included
    assert (limits.endpoints.used, limits.endpoints.limit, limits.endpoints.remaining) == (1, 4, 3)
    assert limits.deliveries_per_day.remaining == 49588
    assert limits.deliveries_per_day.resets_at == _utc("2026-09-30T00:00:00Z")
    assert limits.paused_subscriptions.count == 2
    assert limits.paused_subscriptions.reasons == ["deliveries_per_day_cap"]
    assert limits.notice is None


def test_limits_on_a_plan_without_delivery_and_without_a_daily_ceiling() -> None:
    unlimited = copy.deepcopy(LIMITS)
    unlimited["deliveries_per_day"].update(limit=None, remaining=None, unlimited=True)
    unlimited["paused_subscriptions"] = {"count": 0, "earliest_paused_at": None, "reasons": []}
    unlimited["notice"] = "Webhook delivery is not included on the Free plan."
    client, _ = webhook_client(ok(unlimited))

    limits = client.webhooks.limits()

    assert limits.deliveries_per_day.limit is None
    assert limits.deliveries_per_day.unlimited is True
    assert limits.paused_subscriptions.earliest_paused_at is None
    assert limits.notice is not None


def test_endpoints_keep_unknown_fields_and_never_carry_a_secret() -> None:
    client, _ = webhook_client(ok([ENDPOINT]))

    [endpoint] = client.webhooks.list_endpoints()

    assert isinstance(endpoint, WebhookEndpoint)
    assert not isinstance(endpoint, WebhookEndpointCreated)
    assert endpoint.created_at == _utc("2026-09-21T02:02:04.460276Z")
    assert endpoint.model_extra == {"format": "json"}
    assert not hasattr(endpoint, "secret")


def test_create_endpoint_returns_the_secret_and_the_note() -> None:
    client, _ = webhook_client(
        ok({**ENDPOINT, "secret": SECRET}, note="Store the secret now; it is not shown again.")
    )

    created = client.webhooks.create_endpoint("https://example.com/hooks/0xarchive")

    assert isinstance(created, WebhookEndpointCreated)
    assert isinstance(created, WebhookEndpoint)
    assert created.secret == SECRET
    assert created.note == "Store the secret now; it is not shown again."


def test_create_endpoint_sends_an_empty_description_by_default() -> None:
    client, seen = webhook_client(ok({**ENDPOINT, "secret": SECRET}))

    client.webhooks.create_endpoint("https://example.com/hooks/0xarchive")

    assert seen[0].body == {"url": "https://example.com/hooks/0xarchive", "description": ""}


def test_rotate_secret_folds_the_envelope_note_into_the_model() -> None:
    client, _ = webhook_client(ok({"secret": SECRET}, note="Previous secret remains valid."))

    rotated = client.webhooks.rotate_secret(ENDPOINT_ID)

    assert isinstance(rotated, WebhookEndpointSecret)
    assert rotated.secret == SECRET
    assert rotated.note == "Previous secret remains valid."


def test_a_note_inside_data_is_not_overwritten_by_the_envelope_note() -> None:
    client, _ = webhook_client(ok({"secret": SECRET, "note": "inner"}, note="outer"))

    assert client.webhooks.rotate_secret(ENDPOINT_ID).note == "inner"


def test_writes_that_return_an_ack_return_none() -> None:
    client, _ = webhook_client({"success": True})

    assert client.webhooks.delete_endpoint(ENDPOINT_ID) is None
    assert client.webhooks.enable_endpoint(ENDPOINT_ID) is None
    assert client.webhooks.delete_subscription(SUBSCRIPTION_ID) is None
    assert client.webhooks.delete_address(ADDRESS_ID) is None


def test_test_endpoint_returns_the_queued_ids() -> None:
    client, _ = webhook_client(ok({"delivery_id": DELIVERY_ID, "event_id": EVENT_ID}))

    queued = client.webhooks.test_endpoint(ENDPOINT_ID)

    assert isinstance(queued, WebhookDeliveryQueued)
    assert (queued.delivery_id, queued.event_id) == (DELIVERY_ID, EVENT_ID)


def test_deliveries_parse_state_timing_and_payload() -> None:
    client, seen = webhook_client(ok([DELIVERY]))

    [delivery] = client.webhooks.list_deliveries(ENDPOINT_ID)

    assert seen[0].query == {}
    assert isinstance(delivery, WebhookDelivery)
    assert delivery.state == "failed" and delivery.attempts == 3
    assert delivery.last_status_code == 500 and delivery.last_latency_ms == 142
    assert delivery.delivered_at is None
    assert delivery.next_attempt_at == _utc("2026-09-29T02:10:00Z")
    assert delivery.payload["data"]["notional_usd"] == 312000.5


def test_redeliver_keeps_the_ids_and_the_note() -> None:
    client, _ = webhook_client(ok(REDELIVERY, note="The record is reset in place."))

    redelivery = client.webhooks.redeliver(DELIVERY_ID)

    assert isinstance(redelivery, WebhookRedelivery)
    assert redelivery.event_id == EVENT_ID and redelivery.state == "pending"
    assert redelivery.attempts == 0
    assert redelivery.note == "The record is reset in place."


def test_redeliver_to_a_switched_off_endpoint_raises_with_the_reason() -> None:
    client, _ = webhook_client(
        {
            "code": 409,
            "error": "This delivery's endpoint is disabled, so nothing would be sent.",
            "request_id": "3f2a9c71-5b0e-4d68-9a4c-7e1d2b6f8a05",
        },
        status=409,
    )

    with pytest.raises(OxArchiveError) as caught:
        client.webhooks.redeliver(DELIVERY_ID)

    assert caught.value.code == 409
    assert "disabled" in caught.value.message
    assert caught.value.request_id == "3f2a9c71-5b0e-4d68-9a4c-7e1d2b6f8a05"


def test_subscriptions_parse_config_and_pause_state() -> None:
    client, _ = webhook_client(ok([SUBSCRIPTION, PAUSED_SUBSCRIPTION]))

    active, paused = client.webhooks.list_subscriptions()

    assert isinstance(active, WebhookSubscription)
    assert active.status == "active" and active.pause_message is None
    assert active.config is active.filters
    assert isinstance(active.filters, WebhookSubscriptionConfig)
    assert active.filters.addresses == [WALLET]
    assert active.filters.params == {"max_age_s": 3600}
    assert active.filters.min_notional_usd == 250000.0
    condition = active.filters.conditions[0] if active.filters.conditions else None
    assert isinstance(condition, WebhookSubscriptionCondition)
    assert (condition.metric, condition.op, condition.value) == (
        "notional_usd",
        "greater_than_or_equal",
        250000,
    )
    assert paused.status == "auto_paused"
    assert paused.pause_reason == "deliveries_per_day_cap"
    assert paused.pause_message is not None
    assert paused.paused_at == _utc("2026-09-29T01:15:00Z")
    assert paused.suppressed_count == 17


def test_top_level_declared_params_in_a_stored_config_are_kept() -> None:
    stored = {"venue": "hyperliquid", "threshold_mode": "pct_oi", "threshold_pct": 1}
    client, _ = webhook_client(ok([{**SUBSCRIPTION, "filters": stored}]))

    [sub] = client.webhooks.list_subscriptions()

    assert sub.filters.venue == "hyperliquid"
    assert sub.filters.model_extra == {"threshold_mode": "pct_oi", "threshold_pct": 1}


def test_create_subscription_without_config_sends_no_filters() -> None:
    client, seen = webhook_client(ok(SUBSCRIPTION))

    client.webhooks.create_subscription(ENDPOINT_ID, "market.listed")

    assert seen[0].body == {"endpoint_id": ENDPOINT_ID, "event_type": "market.listed"}


def test_a_config_model_is_sent_without_unset_fields_and_keeps_extras() -> None:
    config = WebhookSubscriptionConfig(
        venue=["hyperliquid", "hip3"],
        conditions=[
            WebhookSubscriptionCondition(metric="notional_usd", op=">=", value=100000),
            WebhookSubscriptionCondition(metric="liquidated_user", op="is_not_empty"),
        ],
        threshold_mode="usd",  # type: ignore[call-arg]
    )
    client, seen = webhook_client(ok(SUBSCRIPTION))

    client.webhooks.create_subscription(ENDPOINT_ID, "market.liquidation", config)

    assert seen[0].body == {
        "endpoint_id": ENDPOINT_ID,
        "event_type": "market.liquidation",
        "filters": {
            "venue": ["hyperliquid", "hip3"],
            "conditions": [
                {"metric": "notional_usd", "op": ">=", "value": 100000},
                {"metric": "liquidated_user", "op": "is_not_empty"},
            ],
            "threshold_mode": "usd",
        },
    }


def test_update_subscription_sends_only_the_fields_given() -> None:
    client, seen = webhook_client(ok({**SUBSCRIPTION, "enabled": False}))

    updated = client.webhooks.update_subscription(SUBSCRIPTION_ID, enabled=False)
    client.webhooks.update_subscription(SUBSCRIPTION_ID, config={"symbols": ["BTC"]})

    assert updated.enabled is False
    assert seen[0].body == {"enabled": False}
    assert seen[1].body == {"filters": {"symbols": ["BTC"]}}


def test_update_subscription_with_nothing_to_change_is_refused_before_sending() -> None:
    client, seen = webhook_client(ok(SUBSCRIPTION))

    with pytest.raises(ValueError, match="config, enabled, or both"):
        client.webhooks.update_subscription(SUBSCRIPTION_ID)
    with pytest.raises(ValueError, match="config, enabled, or both"):
        asyncio.run(client.webhooks.aupdate_subscription(SUBSCRIPTION_ID))

    assert seen == []


def test_resume_subscription_returns_the_rule_and_the_missed_window() -> None:
    client, _ = webhook_client(ok(SUBSCRIPTION, gap=GAP))

    result = client.webhooks.resume_subscription(SUBSCRIPTION_ID)

    assert isinstance(result, WebhookSubscriptionResume)
    assert result.subscription.id == SUBSCRIPTION_ID
    assert result.note is None
    gap = result.gap
    assert gap is not None and gap.counted is True
    assert gap.suppressed_count == 17
    assert gap.replay_window.start == _utc("2026-09-29T01:15:00Z")
    assert gap.replay_window.end == _utc("2026-09-29T03:00:00Z")
    assert gap.reason == "deliveries_per_day_cap"


def test_resuming_a_serving_rule_changes_nothing() -> None:
    client, _ = webhook_client(
        ok(SUBSCRIPTION, gap=None, note="This subscription was already active, so nothing changed.")
    )

    result = client.webhooks.resume_subscription(SUBSCRIPTION_ID)

    assert result.gap is None
    assert result.note is not None and "already active" in result.note


def test_resume_all_lists_the_rules_and_an_uncounted_gap() -> None:
    gap = {
        **GAP,
        "reason": None,
        "reasons": ["deliveries_per_day_cap", "plan_no_webhooks"],
        "suppressed_count": None,
        "counted": False,
        "uncounted_subscriptions": 1,
    }
    client, _ = webhook_client(ok([SUBSCRIPTION, SUBSCRIPTION], resumed_count=2, gap=gap))

    result = client.webhooks.resume_all_subscriptions()

    assert isinstance(result, WebhookSubscriptionResumeAll)
    assert result.resumed_count == 2 and len(result.subscriptions) == 2
    assert result.gap is not None
    assert result.gap.counted is False and result.gap.suppressed_count is None
    assert result.gap.reasons == ["deliveries_per_day_cap", "plan_no_webhooks"]
    assert result.gap.uncounted_subscriptions == 1


def test_resume_all_with_nothing_paused() -> None:
    client, _ = webhook_client(
        ok([], resumed_count=0, gap=None, note="Nothing on this account is paused.")
    )

    result = client.webhooks.resume_all_subscriptions()

    assert result.subscriptions == [] and result.resumed_count == 0
    assert result.gap is None and result.note is not None


def test_resume_at_the_daily_limit_raises_409() -> None:
    client, _ = webhook_client(
        {"code": 409, "error": "You are still at today's delivery limit."}, status=409
    )

    with pytest.raises(OxArchiveError) as caught:
        client.webhooks.resume_all_subscriptions()

    assert caught.value.code == 409


def test_dry_run_parses_the_window_and_occurrences() -> None:
    client, seen = webhook_client(ok(DRY_RUN))

    preview = client.webhooks.dry_run("market.liquidation")

    assert seen[0].body == {"event_type": "market.liquidation"}
    assert isinstance(preview, WebhookDryRun)
    assert preview.matched == 37 and preview.truncated is True
    assert preview.window.from_ == _utc("2026-09-28T02:00:00Z")
    assert preview.window.to == _utc("2026-09-29T02:00:00Z")
    assert preview.occurrences[0].observed_at_estimate == _utc("2026-09-29T01:59:59.100Z")
    assert preview.occurrences[0].data["side"] == "long"


def test_estimate_parses_days_ladder_distribution_and_basis() -> None:
    client, seen = webhook_client(ok(ESTIMATE))

    est = client.webhooks.estimate(
        "market.liquidation", WebhookSubscriptionConfig(min_notional_usd=250000)
    )

    assert seen[0].body == {
        "event_type": "market.liquidation",
        "config": {"min_notional_usd": 250000.0},
    }
    assert isinstance(est, WebhookEstimate)
    assert est.days == 7 and est.total == 84
    assert est.per_day[0].date == date(2026, 9, 23) and est.per_day[0].count == 12
    assert est.per_day_p50 == 11 and est.per_day_max == 26
    assert [(r.value, r.per_day) for r in est.ladder] == [(250000, 3.4), (500000, 1.1)]
    assert est.distribution is not None and est.distribution.p99 == 910000
    assert est.basis.mode == "sampled" and est.basis.note is not None
    assert est.sample[0].data["notional_usd"] == 612000.0


def test_estimate_without_a_primary_metric() -> None:
    bare = {**ESTIMATE, "primary_metric": None, "ladder": [], "distribution": None}
    client, _ = webhook_client(ok(bare))

    est = client.webhooks.estimate("market.listed")

    assert est.primary_metric is None and est.ladder == [] and est.distribution is None


def test_watched_addresses_parse() -> None:
    lister, _ = webhook_client(ok([ADDRESS], limit=15))
    adder, _ = webhook_client(ok(ADDRESS, limit=15))

    [watched] = lister.webhooks.list_addresses()
    added = adder.webhooks.add_address(WALLET)

    assert isinstance(watched, WebhookWatchedAddress)
    assert (watched.id, watched.address, watched.label) == (ADDRESS_ID, WALLET, "Desk 1")
    assert watched.created_at == _utc("2026-09-21T02:04:12.377291Z")
    assert added.address == WALLET


def test_add_address_sends_an_empty_label_by_default() -> None:
    client, seen = webhook_client(ok(ADDRESS))

    client.webhooks.add_address(WALLET)

    assert seen[0].body == {"address": WALLET, "label": ""}


def test_identifiers_are_encoded_as_one_path_segment() -> None:
    client, seen = webhook_client({"success": True})

    client.webhooks.delete_endpoint("../subscriptions")

    assert seen[0].raw_path == "/v1/webhooks/endpoints/..%2Fsubscriptions"


def test_a_refused_plan_raises_with_the_server_message() -> None:
    client, _ = webhook_client(
        {"code": 400, "error": "Webhook delivery is not included on the Free plan."}, status=400
    )

    with pytest.raises(OxArchiveError) as caught:
        asyncio.run(client.webhooks.acreate_endpoint("https://example.com/hooks"))

    assert caught.value.code == 400
    assert "Free plan" in caught.value.message
