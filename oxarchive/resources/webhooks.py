"""Webhooks API resource: endpoints, subscriptions, watched wallets, deliveries."""

from __future__ import annotations

from typing import Any, Optional, Union
from urllib.parse import quote

from pydantic import BaseModel

from ..http import HttpClient
from ..types import (
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
    WebhookSubscriptionConfig,
    WebhookSubscriptionResume,
    WebhookSubscriptionResumeAll,
    WebhookWatchedAddress,
)

WebhookConfig = Union[WebhookSubscriptionConfig, dict[str, Any]]
"""A subscription configuration: a :class:`WebhookSubscriptionConfig` or a plain dict."""


def _segment(value: str) -> str:
    """One path segment. Identifiers are UUIDs; anything else is encoded, never a path."""
    return quote(str(value), safe="")


def _config_body(config: WebhookConfig) -> dict[str, Any]:
    """The JSON object sent for a configuration.

    A model is dumped without the fields left unset or ``None``, and keeps any
    extra keys (declared parameters written at the top level). A dict is sent
    as given.
    """
    if isinstance(config, BaseModel):
        return config.model_dump(mode="json", exclude_none=True)
    return dict(config)


def _with_note(envelope: dict[str, Any]) -> dict[str, Any]:
    """Fold the envelope's top-level ``note`` into the payload.

    Create, rotate and redeliver put an advisory next to ``data`` rather than
    inside it. Merging the two lets one model carry both, without clobbering a
    ``note`` the payload may carry of its own.
    """
    payload = dict(envelope.get("data") or {})
    note = envelope.get("note")
    if note is not None and "note" not in payload:
        payload["note"] = note
    return payload


def _resume(envelope: dict[str, Any]) -> WebhookSubscriptionResume:
    return WebhookSubscriptionResume.model_validate(
        {
            "subscription": envelope.get("data") or {},
            "gap": envelope.get("gap"),
            "note": envelope.get("note"),
        }
    )


def _resume_all(envelope: dict[str, Any]) -> WebhookSubscriptionResumeAll:
    return WebhookSubscriptionResumeAll.model_validate(
        {
            "subscriptions": envelope.get("data") or [],
            "resumed_count": envelope.get("resumed_count", 0),
            "gap": envelope.get("gap"),
            "note": envelope.get("note"),
        }
    )


class WebhooksResource:
    """
    Webhooks: push delivery of market, account and platform events.

    Three objects, in the order you create them:

    1. An **endpoint** is an HTTPS URL 0xArchive posts to. Creating one returns
       its signing secret, once.
    2. A **subscription** is a rule: one event type, on one endpoint, with an
       optional configuration of filters, parameters and conditions.
    3. A **watched address** is a wallet. Event types whose ``scope`` is
       ``"addresses"`` report only on wallets on this list.

    Webhook delivery needs a paid plan; :meth:`limits` reports what the plan
    allows and what is in use. :meth:`estimate` and :meth:`dry_run` are
    available on every plan, Free included, so a rule can be sized before it
    is created. Verify what arrives with :class:`~oxarchive.WebhookVerifier`.

    Every method has an async version prefixed with ``a``.

    Example:
        >>> endpoint = client.webhooks.create_endpoint(
        ...     "https://example.com/hooks/0xarchive", description="Desk alerts"
        ... )
        >>> store_secret(endpoint.secret)  # shown once
        >>> est = client.webhooks.estimate(
        ...     "market.liquidation",
        ...     {"venue": "hyperliquid", "min_notional_usd": 250000},
        ...     lookback_days=7,
        ... )
        >>> print(est.per_day_p50, est.per_day_max)
        >>> sub = client.webhooks.create_subscription(
        ...     endpoint.id,
        ...     "market.liquidation",
        ...     {"venue": "hyperliquid", "min_notional_usd": 250000},
        ... )
        >>> client.webhooks.test_endpoint(endpoint.id)
    """

    def __init__(self, http: HttpClient, base_path: str = "/v1/webhooks"):
        self._http = http
        self._base_path = base_path

    # =========================================================================
    # Catalog and limits
    # =========================================================================

    def event_types(self) -> list[WebhookEventType]:
        """
        List every event type with the filters, parameters, metrics and operators it accepts.

        Subscriptions are validated against these declarations, so read them
        from here rather than hardcoding them. A type whose ``live`` is False
        is published but does not yet accept subscriptions.

        Example:
            >>> for t in client.webhooks.event_types():
            ...     if t.live:
            ...         print(t.type, t.scope, t.latency_class)
        """
        data = self._http.get(f"{self._base_path}/event-types")
        return [WebhookEventType.model_validate(x) for x in data["data"]]

    async def aevent_types(self) -> list[WebhookEventType]:
        """Async version of :meth:`event_types`."""
        data = await self._http.aget(f"{self._base_path}/event-types")
        return [WebhookEventType.model_validate(x) for x in data["data"]]

    def limits(self) -> WebhookLimits:
        """
        Get what the plan allows for webhooks and what is in use.

        Reports the endpoint, subscription and watched wallet caps, today's
        delivery budget and when it resets, and how many subscriptions are
        paused. The budget resets on its own and a paused subscription does
        not, which is why the paused count is reported next to it. On a plan
        without webhook delivery, ``included`` is False, every cap is zero and
        ``notice`` says what to do.

        Example:
            >>> limits = client.webhooks.limits()
            >>> print(limits.deliveries_per_day.remaining, limits.paused_subscriptions.count)
        """
        data = self._http.get(f"{self._base_path}/limits")
        return WebhookLimits.model_validate(data["data"])

    async def alimits(self) -> WebhookLimits:
        """Async version of :meth:`limits`."""
        data = await self._http.aget(f"{self._base_path}/limits")
        return WebhookLimits.model_validate(data["data"])

    # =========================================================================
    # Endpoints
    # =========================================================================

    def list_endpoints(self) -> list[WebhookEndpoint]:
        """List your delivery endpoints, oldest first. Secrets are never included."""
        data = self._http.get(f"{self._base_path}/endpoints")
        return [WebhookEndpoint.model_validate(x) for x in data["data"]]

    async def alist_endpoints(self) -> list[WebhookEndpoint]:
        """Async version of :meth:`list_endpoints`."""
        data = await self._http.aget(f"{self._base_path}/endpoints")
        return [WebhookEndpoint.model_validate(x) for x in data["data"]]

    def create_endpoint(self, url: str, description: str = "") -> WebhookEndpointCreated:
        """
        Register an HTTPS destination and get its signing secret.

        The returned ``secret`` is shown once. Store it before anything else:
        no later call returns it, and without it a delivery cannot be
        verified. If it is lost, :meth:`rotate_secret` issues a new one.
        Destinations that resolve to a private or internal address are
        refused, at creation and again on every delivery.

        Args:
            url: HTTPS destination for deliveries.
            description: Your own label for the endpoint.

        Returns:
            The endpoint, with ``secret`` populated.

        Raises:
            OxArchiveError: The plan has no webhook delivery or is at its
                endpoint cap, or the URL was refused.
        """
        data = self._http.post(
            f"{self._base_path}/endpoints",
            json={"url": url, "description": description},
        )
        return WebhookEndpointCreated.model_validate(_with_note(data))

    async def acreate_endpoint(self, url: str, description: str = "") -> WebhookEndpointCreated:
        """Async version of :meth:`create_endpoint`."""
        data = await self._http.apost(
            f"{self._base_path}/endpoints",
            json={"url": url, "description": description},
        )
        return WebhookEndpointCreated.model_validate(_with_note(data))

    def delete_endpoint(self, endpoint_id: str) -> None:
        """
        Delete an endpoint and every subscription pointing at it.

        Raises:
            OxArchiveError: No such endpoint on this account.
        """
        self._http.delete(f"{self._base_path}/endpoints/{_segment(endpoint_id)}")

    async def adelete_endpoint(self, endpoint_id: str) -> None:
        """Async version of :meth:`delete_endpoint`."""
        await self._http.adelete(f"{self._base_path}/endpoints/{_segment(endpoint_id)}")

    def enable_endpoint(self, endpoint_id: str) -> None:
        """
        Put an endpoint back into service.

        Use it after you switched the endpoint off, or after a long run of
        failed deliveries switched it off for you (``status ==
        "auto_disabled"``). Fix the receiver first. Deliveries resume on the
        next matching event; nothing that happened while it was off is
        replayed.

        Raises:
            OxArchiveError: No such endpoint on this account.
        """
        self._http.post(f"{self._base_path}/endpoints/{_segment(endpoint_id)}/enable")

    async def aenable_endpoint(self, endpoint_id: str) -> None:
        """Async version of :meth:`enable_endpoint`."""
        await self._http.apost(f"{self._base_path}/endpoints/{_segment(endpoint_id)}/enable")

    def rotate_secret(self, endpoint_id: str) -> WebhookEndpointSecret:
        """
        Issue a new signing secret; the previous one keeps verifying for 24 hours.

        During the overlap every delivery carries two ``v1=`` signatures, one
        per secret, so a receiver holding either keeps verifying. Roll over
        by rotating, accepting both secrets, deploying, then dropping the old
        one before the 24 hours are up. Only one previous secret is kept:
        rotating twice inside the window retires the original at once.

        Returns:
            The new secret, shown once.

        Example:
            >>> rotated = client.webhooks.rotate_secret(endpoint_id)
            >>> verifier.add_secret(rotated.secret)  # accept both, then deploy
        """
        data = self._http.post(f"{self._base_path}/endpoints/{_segment(endpoint_id)}/rotate")
        return WebhookEndpointSecret.model_validate(_with_note(data))

    async def arotate_secret(self, endpoint_id: str) -> WebhookEndpointSecret:
        """Async version of :meth:`rotate_secret`."""
        data = await self._http.apost(
            f"{self._base_path}/endpoints/{_segment(endpoint_id)}/rotate"
        )
        return WebhookEndpointSecret.model_validate(_with_note(data))

    def test_endpoint(self, endpoint_id: str) -> WebhookDeliveryQueued:
        """
        Queue a ``webhook.test`` delivery to an endpoint.

        It is a real signed delivery through the same path as every other, so
        it checks a receiver and its signature verification end to end. It
        counts against today's delivery budget, and it is refused on a plan
        without webhook delivery or once the budget is spent. A refusal here
        never pauses a subscription.

        Returns:
            The queued delivery and event identifiers.

        Example:
            >>> queued = client.webhooks.test_endpoint(endpoint_id)
            >>> log = client.webhooks.list_deliveries(endpoint_id, limit=1)
            >>> print(log[0].state, log[0].last_status_code)
        """
        data = self._http.post(f"{self._base_path}/endpoints/{_segment(endpoint_id)}/test")
        return WebhookDeliveryQueued.model_validate(data["data"])

    async def atest_endpoint(self, endpoint_id: str) -> WebhookDeliveryQueued:
        """Async version of :meth:`test_endpoint`."""
        data = await self._http.apost(
            f"{self._base_path}/endpoints/{_segment(endpoint_id)}/test"
        )
        return WebhookDeliveryQueued.model_validate(data["data"])

    # =========================================================================
    # Deliveries
    # =========================================================================

    def list_deliveries(
        self,
        endpoint_id: str,
        *,
        limit: Optional[int] = None,
    ) -> list[WebhookDelivery]:
        """
        Read an endpoint's delivery log, newest first.

        Each record carries the event payload as sent, the attempt count, the
        status the receiver returned and the timing of the last attempt.

        Args:
            endpoint_id: Endpoint identifier.
            limit: Deliveries to return, 1 to 200 (server default 50). Values
                outside the range are clamped by the server.
        """
        data = self._http.get(
            f"{self._base_path}/endpoints/{_segment(endpoint_id)}/deliveries",
            params={"limit": limit},
        )
        return [WebhookDelivery.model_validate(x) for x in data["data"]]

    async def alist_deliveries(
        self,
        endpoint_id: str,
        *,
        limit: Optional[int] = None,
    ) -> list[WebhookDelivery]:
        """Async version of :meth:`list_deliveries`."""
        data = await self._http.aget(
            f"{self._base_path}/endpoints/{_segment(endpoint_id)}/deliveries",
            params={"limit": limit},
        )
        return [WebhookDelivery.model_validate(x) for x in data["data"]]

    def redeliver(self, delivery_id: str) -> WebhookRedelivery:
        """
        Send a past delivery again.

        The delivery and event identifiers are unchanged, so a receiver that
        already processed the event can deduplicate it. The record is reset in
        place: the retry window and attempt counter start again. A repeat is
        a real signed delivery and counts against today's budget.

        Raises:
            OxArchiveError: No such delivery (404); the endpoint is switched
                off, so nothing would be sent, or today's budget is spent
                (409). Re-enable the endpoint with :meth:`enable_endpoint`
                first.
        """
        data = self._http.post(f"{self._base_path}/deliveries/{_segment(delivery_id)}/redeliver")
        return WebhookRedelivery.model_validate(_with_note(data))

    async def aredeliver(self, delivery_id: str) -> WebhookRedelivery:
        """Async version of :meth:`redeliver`."""
        data = await self._http.apost(
            f"{self._base_path}/deliveries/{_segment(delivery_id)}/redeliver"
        )
        return WebhookRedelivery.model_validate(_with_note(data))

    # =========================================================================
    # Subscriptions
    # =========================================================================

    def list_subscriptions(self) -> list[WebhookSubscription]:
        """
        List your subscriptions across every endpoint.

        Each carries its stored configuration and its pause state. A paused
        rule has ``status == "auto_paused"`` and a ``pause_message`` saying
        why and what clears it.
        """
        data = self._http.get(f"{self._base_path}/subscriptions")
        return [WebhookSubscription.model_validate(x) for x in data["data"]]

    async def alist_subscriptions(self) -> list[WebhookSubscription]:
        """Async version of :meth:`list_subscriptions`."""
        data = await self._http.aget(f"{self._base_path}/subscriptions")
        return [WebhookSubscription.model_validate(x) for x in data["data"]]

    @staticmethod
    def _create_body(
        endpoint_id: str, event_type: str, config: Optional[WebhookConfig]
    ) -> dict[str, Any]:
        body: dict[str, Any] = {"endpoint_id": endpoint_id, "event_type": event_type}
        if config is not None:
            body["filters"] = _config_body(config)
        return body

    def create_subscription(
        self,
        endpoint_id: str,
        event_type: str,
        config: Optional[WebhookConfig] = None,
    ) -> WebhookSubscription:
        """
        Subscribe an endpoint to an event type.

        The configuration is checked against the event type's declaration
        (see :meth:`event_types`) before anything is stored, so an unknown
        key, an undeclared parameter, an out of range value or a condition on
        a metric the event does not carry is refused rather than dropped.
        Addresses in the configuration must already be on your watched list.
        Without a configuration the rule matches every occurrence of the type.
        Run :meth:`estimate` or :meth:`dry_run` with the same configuration
        first to see how much it would deliver.

        Args:
            endpoint_id: Endpoint that receives the deliveries.
            event_type: Event type from the catalog, for example ``"account.fill"``.
            config: Filters, parameters and conditions, as a dict or a
                :class:`~oxarchive.WebhookSubscriptionConfig`. Sent as
                ``filters``.

        Returns:
            The created rule with its normalised configuration.

        Raises:
            OxArchiveError: The plan has no webhook delivery or is at its
                subscription cap, the endpoint is not yours, the event type is
                unknown or not live, or the configuration was refused.

        Example:
            >>> sub = client.webhooks.create_subscription(
            ...     endpoint_id,
            ...     "account.fill",
            ...     {
            ...         "addresses": ["0x6b9e773128f453f5c2c60935ee2de2cbc5390a24"],
            ...         "conditions": [
            ...             {"metric": "notional_usd", "op": ">=", "value": 25000}
            ...         ],
            ...     },
            ... )
        """
        data = self._http.post(
            f"{self._base_path}/subscriptions",
            json=self._create_body(endpoint_id, event_type, config),
        )
        return WebhookSubscription.model_validate(data["data"])

    async def acreate_subscription(
        self,
        endpoint_id: str,
        event_type: str,
        config: Optional[WebhookConfig] = None,
    ) -> WebhookSubscription:
        """Async version of :meth:`create_subscription`."""
        data = await self._http.apost(
            f"{self._base_path}/subscriptions",
            json=self._create_body(endpoint_id, event_type, config),
        )
        return WebhookSubscription.model_validate(data["data"])

    @staticmethod
    def _update_body(config: Optional[WebhookConfig], enabled: Optional[bool]) -> dict[str, Any]:
        if config is None and enabled is None:
            raise ValueError("update_subscription needs config, enabled, or both")
        body: dict[str, Any] = {}
        if config is not None:
            body["filters"] = _config_body(config)
        if enabled is not None:
            body["enabled"] = enabled
        return body

    def update_subscription(
        self,
        subscription_id: str,
        *,
        config: Optional[WebhookConfig] = None,
        enabled: Optional[bool] = None,
    ) -> WebhookSubscription:
        """
        Edit a rule in place.

        A ``config`` replaces the stored configuration rather than merging into
        it, so send the whole object; it is validated as at create. ``enabled``
        switches the rule on or off without touching its configuration. A
        field left as ``None`` is not sent and is left alone.

        Args:
            subscription_id: Subscription identifier.
            config: The complete replacement configuration. Sent as ``filters``.
            enabled: Your own on and off switch for the rule.

        Raises:
            ValueError: Neither ``config`` nor ``enabled`` was given.
            OxArchiveError: No such subscription, or the configuration was refused.

        Example:
            >>> client.webhooks.update_subscription(sub.id, enabled=False)
        """
        data = self._http.patch(
            f"{self._base_path}/subscriptions/{_segment(subscription_id)}",
            json=self._update_body(config, enabled),
        )
        return WebhookSubscription.model_validate(data["data"])

    async def aupdate_subscription(
        self,
        subscription_id: str,
        *,
        config: Optional[WebhookConfig] = None,
        enabled: Optional[bool] = None,
    ) -> WebhookSubscription:
        """Async version of :meth:`update_subscription`."""
        data = await self._http.apatch(
            f"{self._base_path}/subscriptions/{_segment(subscription_id)}",
            json=self._update_body(config, enabled),
        )
        return WebhookSubscription.model_validate(data["data"])

    def delete_subscription(self, subscription_id: str) -> None:
        """
        Delete a rule. Its endpoint and any other rule pointing at it are untouched.

        Raises:
            OxArchiveError: No such subscription on this account.
        """
        self._http.delete(f"{self._base_path}/subscriptions/{_segment(subscription_id)}")

    async def adelete_subscription(self, subscription_id: str) -> None:
        """Async version of :meth:`delete_subscription`."""
        await self._http.adelete(f"{self._base_path}/subscriptions/{_segment(subscription_id)}")

    def resume_subscription(self, subscription_id: str) -> WebhookSubscriptionResume:
        """
        Put one paused rule back into service.

        Nothing is buffered while a rule is paused, so the result carries the
        window that was missed (``gap``) instead of replaying it: when it
        began and ended, how much of it was counted, and what can be re-read
        from the REST routes. A rule that is already serving is left as it
        is, with ``gap`` None and a ``note``. Your own ``enabled`` switch is
        never changed.

        Raises:
            OxArchiveError: No such subscription (404), or resuming would be
                undone at once because the plan has no webhook delivery or
                today's budget is spent (400 or 409).

        Example:
            >>> result = client.webhooks.resume_subscription(sub.id)
            >>> if result.gap:
            ...     print(result.gap.replay_window.start, result.gap.replay_window.end)
        """
        data = self._http.post(
            f"{self._base_path}/subscriptions/{_segment(subscription_id)}/resume"
        )
        return _resume(data)

    async def aresume_subscription(self, subscription_id: str) -> WebhookSubscriptionResume:
        """Async version of :meth:`resume_subscription`."""
        data = await self._http.apost(
            f"{self._base_path}/subscriptions/{_segment(subscription_id)}/resume"
        )
        return _resume(data)

    def resume_all_subscriptions(self) -> WebhookSubscriptionResumeAll:
        """
        Put every paused rule on the account back into service in one call.

        The daily delivery limit is counted per account while a pause is
        written per rule, so one busy rule can pause them all; this brings the
        account back without a call per rule. The result lists the resumed
        rules and the window they missed. If nothing is paused, nothing
        changes and ``note`` says so.

        Raises:
            OxArchiveError: Resuming would be undone at once because the plan
                has no webhook delivery or today's budget is spent (400 or 409).
        """
        data = self._http.post(f"{self._base_path}/subscriptions/resume")
        return _resume_all(data)

    async def aresume_all_subscriptions(self) -> WebhookSubscriptionResumeAll:
        """Async version of :meth:`resume_all_subscriptions`."""
        data = await self._http.apost(f"{self._base_path}/subscriptions/resume")
        return _resume_all(data)

    # =========================================================================
    # Previews
    # =========================================================================

    @staticmethod
    def _dry_run_body(
        event_type: str,
        config: Optional[WebhookConfig],
        lookback_s: Optional[int],
        limit: Optional[int],
    ) -> dict[str, Any]:
        body: dict[str, Any] = {"event_type": event_type}
        if config is not None:
            body["config"] = _config_body(config)
        if lookback_s is not None:
            body["lookback_s"] = lookback_s
        if limit is not None:
            body["limit"] = limit
        return body

    def dry_run(
        self,
        event_type: str,
        config: Optional[WebhookConfig] = None,
        *,
        lookback_s: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> WebhookDryRun:
        """
        Show which recent occurrences a configuration would have delivered.

        The configuration is validated and normalised exactly as at create,
        then evaluated against recent history. Nothing is stored and nothing
        is delivered. Available on every plan, Free included, and metered like
        the market data it returns. Not every event type can be dry-run; a
        type that cannot is refused with the list of those that can. An
        address scoped type needs at least one watched wallet. Dry-runs and
        estimates share a limit of six a minute per account.

        Args:
            event_type: Event type from the catalog.
            config: The configuration you would subscribe with. Sent as ``config``.
            lookback_s: Seconds of history to scan, ending now: 60 to 86400
                (server default 3600).
            limit: Occurrences to return, newest first: 1 to 200 (server
                default 100).

        Example:
            >>> preview = client.webhooks.dry_run(
            ...     "market.liquidation",
            ...     {"venue": "hyperliquid", "min_notional_usd": 500000},
            ...     lookback_s=86400,
            ... )
            >>> print(preview.matched, preview.window.from_, preview.window.to)
        """
        data = self._http.post(
            f"{self._base_path}/subscriptions/dry-run",
            json=self._dry_run_body(event_type, config, lookback_s, limit),
        )
        return WebhookDryRun.model_validate(data["data"])

    async def adry_run(
        self,
        event_type: str,
        config: Optional[WebhookConfig] = None,
        *,
        lookback_s: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> WebhookDryRun:
        """Async version of :meth:`dry_run`."""
        data = await self._http.apost(
            f"{self._base_path}/subscriptions/dry-run",
            json=self._dry_run_body(event_type, config, lookback_s, limit),
        )
        return WebhookDryRun.model_validate(data["data"])

    @staticmethod
    def _estimate_body(
        event_type: str,
        config: Optional[WebhookConfig],
        lookback_days: Optional[int],
    ) -> dict[str, Any]:
        body: dict[str, Any] = {"event_type": event_type}
        if config is not None:
            body["config"] = _config_body(config)
        if lookback_days is not None:
            body["lookback_days"] = lookback_days
        return body

    def estimate(
        self,
        event_type: str,
        config: Optional[WebhookConfig] = None,
        *,
        lookback_days: Optional[int] = None,
    ) -> WebhookEstimate:
        """
        Show how often a configuration would have fired, per day, over a past window.

        Returns the total, a count per day, the median and busiest day, the
        distribution of the event's primary metric, a ladder of the daily
        rate at other thresholds, and a sample of real matches, so a
        threshold can be chosen against history. Compare ``per_day_p50`` and
        ``per_day_max`` with the plan's daily delivery budget. Available on
        every plan, Free included, and metered like the market data it
        returns. A type that cannot be estimated is refused with the list of
        those that can; an address scoped type needs at least one watched
        wallet. Dry-runs and estimates share a limit of six a minute.

        Args:
            event_type: Event type from the catalog.
            config: The configuration you would subscribe with. Sent as ``config``.
            lookback_days: Days of history to evaluate, ending now: 1 to 30
                (server default 7). Some types cap their own window lower;
                ``days`` on the result says what was covered.

        Example:
            >>> est = client.webhooks.estimate("market.liquidation_burst")
            >>> for rung in est.ladder:
            ...     print(rung.value, rung.per_day)
        """
        data = self._http.post(
            f"{self._base_path}/subscriptions/estimate",
            json=self._estimate_body(event_type, config, lookback_days),
        )
        return WebhookEstimate.model_validate(data["data"])

    async def aestimate(
        self,
        event_type: str,
        config: Optional[WebhookConfig] = None,
        *,
        lookback_days: Optional[int] = None,
    ) -> WebhookEstimate:
        """Async version of :meth:`estimate`."""
        data = await self._http.apost(
            f"{self._base_path}/subscriptions/estimate",
            json=self._estimate_body(event_type, config, lookback_days),
        )
        return WebhookEstimate.model_validate(data["data"])

    # =========================================================================
    # Watched addresses
    # =========================================================================

    def list_addresses(self) -> list[WebhookWatchedAddress]:
        """List the wallets address scoped event types report on."""
        data = self._http.get(f"{self._base_path}/addresses")
        return [WebhookWatchedAddress.model_validate(x) for x in data["data"]]

    async def alist_addresses(self) -> list[WebhookWatchedAddress]:
        """Async version of :meth:`list_addresses`."""
        data = await self._http.aget(f"{self._base_path}/addresses")
        return [WebhookWatchedAddress.model_validate(x) for x in data["data"]]

    def add_address(self, address: str, label: str = "") -> WebhookWatchedAddress:
        """
        Watch a wallet so address scoped event types can report on it.

        Add the wallet before a subscription that names it. Adding a wallet
        that is already watched changes nothing and does not count against
        the cap again. The address is stored lowercase. Hyperliquid bridge
        system addresses are refused: such an address is a counterparty to
        every bridge movement of its token rather than an account.

        Args:
            address: A 0x prefixed, 40 hex character wallet address.
            label: Your own label, at most 64 characters.

        Raises:
            OxArchiveError: The plan has no webhook delivery or is at its
                watched wallet cap, or the address was refused.
        """
        data = self._http.post(
            f"{self._base_path}/addresses",
            json={"address": address, "label": label},
        )
        return WebhookWatchedAddress.model_validate(data["data"])

    async def aadd_address(self, address: str, label: str = "") -> WebhookWatchedAddress:
        """Async version of :meth:`add_address`."""
        data = await self._http.apost(
            f"{self._base_path}/addresses",
            json={"address": address, "label": label},
        )
        return WebhookWatchedAddress.model_validate(data["data"])

    def delete_address(self, address_id: str) -> None:
        """
        Stop watching a wallet.

        Subscriptions that named it keep their stored configuration, so remove
        the address from those rules too if they should no longer reference it.

        Args:
            address_id: Watched address identifier, from :meth:`list_addresses`.
        """
        self._http.delete(f"{self._base_path}/addresses/{_segment(address_id)}")

    async def adelete_address(self, address_id: str) -> None:
        """Async version of :meth:`delete_address`."""
        await self._http.adelete(f"{self._base_path}/addresses/{_segment(address_id)}")
