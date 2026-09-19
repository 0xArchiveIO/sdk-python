"""Webhooks API resource: endpoints, subscriptions, watched wallets, deliveries."""

from __future__ import annotations

from typing import Any, Optional

from ..http import HttpClient
from ..types import (
    WebhookDelivery,
    WebhookDryRun,
    WebhookEndpoint,
    WebhookEstimate,
    WebhookEventTypeDeclaration,
    WebhookRedelivery,
    WebhookSecret,
    WebhookSubscription,
    WebhookTestResult,
    WebhookWatchedAddress,
)


def _with_note(envelope: dict[str, Any]) -> dict[str, Any]:
    """Fold the envelope's top-level advisory into the payload.

    The rotate route puts the new secret in ``data`` and its "previous secret
    remains valid" advisory alongside it, outside ``data``. Merge the two so
    one model carries both, without clobbering a ``note`` the payload may
    grow of its own accord later.
    """
    payload = dict(envelope.get("data") or {})
    note = envelope.get("note")
    if note is not None and "note" not in payload:
        payload["note"] = note
    return payload


class WebhooksResource:
    """
    Webhook management: push delivery of market and account events.

    Three objects, in the order you create them:

    1. An **endpoint** is a URL 0xArchive posts to. Creating one returns a
       signing secret, shown once.
    2. A **subscription** is a rule: one event type, on one endpoint, with
       optional filters, parameters, and conditions.
    3. A **watched address** is a wallet you own or follow. The account-scoped
       event types only fire on wallets you have added here.

    Webhook delivery is a paid feature. Free plans hold no endpoints,
    subscriptions, watched wallets, or deliveries. Free does keep
    :meth:`estimate` and :meth:`dry_run`, so a rule can be designed and sized
    before upgrading. See the README for the per-plan grid.

    Example:
        >>> # 1. Somewhere to deliver
        >>> endpoint = client.webhooks.create_endpoint(
        ...     "https://example.com/hooks/0xarchive",
        ...     description="prod receiver",
        ... )
        >>> store_secret(endpoint.secret)  # shown once, never again
        >>>
        >>> # 2. Size the rule before you buy the deliveries
        >>> estimate = client.webhooks.estimate(
        ...     "market.liquidation",
        ...     config={"venue": "hyperliquid", "min_notional_usd": 250000},
        ...     lookback_days=7,
        ... )
        >>> print(f"~{estimate.per_day_p50:.0f} deliveries a day")
        >>>
        >>> # 3. Turn it on
        >>> sub = client.webhooks.create_subscription(
        ...     endpoint_id=endpoint.id,
        ...     event_type="market.liquidation",
        ...     config={"venue": "hyperliquid", "min_notional_usd": 250000},
        ... )
        >>>
        >>> # 4. Prove the receiver verifies signatures, end to end
        >>> client.webhooks.test_endpoint(endpoint.id)

    Verifying what arrives is :class:`~oxarchive.WebhookVerifier`'s job.
    """

    def __init__(self, http: HttpClient, base_path: str = "/v1/webhooks"):
        self._http = http
        self._base_path = base_path

    # =========================================================================
    # Catalog
    # =========================================================================

    def event_types(self) -> list[WebhookEventTypeDeclaration]:
        """
        List every event type, with the filters, parameters, and metrics it accepts.

        This catalog is the only place event types are declared. Read the
        available operators and thresholds from it rather than hardcoding
        them: a type whose ``live`` is False is published but not yet
        subscribable.

        Returns:
            One declaration per event type.

        Example:
            >>> live = [t for t in client.webhooks.event_types() if t.live]
            >>> for t in live:
            ...     print(t.type, t.scope, t.description)
        """
        data = self._http.get(f"{self._base_path}/event-types")
        return [WebhookEventTypeDeclaration.model_validate(x) for x in data["data"]]

    async def aevent_types(self) -> list[WebhookEventTypeDeclaration]:
        """Async version of :meth:`event_types`."""
        data = await self._http.aget(f"{self._base_path}/event-types")
        return [WebhookEventTypeDeclaration.model_validate(x) for x in data["data"]]

    # =========================================================================
    # Endpoints
    # =========================================================================

    def list_endpoints(self) -> list[WebhookEndpoint]:
        """
        List your delivery endpoints.

        Returns:
            Every endpoint on the account. ``secret`` is always None here; it
            is returned only at create and rotate time.
        """
        data = self._http.get(f"{self._base_path}/endpoints")
        return [WebhookEndpoint.model_validate(x) for x in data["data"]]

    async def alist_endpoints(self) -> list[WebhookEndpoint]:
        """Async version of :meth:`list_endpoints`."""
        data = await self._http.aget(f"{self._base_path}/endpoints")
        return [WebhookEndpoint.model_validate(x) for x in data["data"]]

    def create_endpoint(self, url: str, description: str = "") -> WebhookEndpoint:
        """
        Register a delivery endpoint and get its signing secret.

        The returned ``secret`` is shown ONCE. Store it before you do
        anything else: no later call returns it, and without it you cannot
        verify a delivery. If you lose it, :meth:`rotate_secret` issues a new
        one.

        The URL is checked at create time and again on every dispatch;
        private and loopback destinations are refused. Redirects are not
        followed, so give the final URL.

        Args:
            url: HTTPS destination for deliveries.
            description: Your own label for the endpoint.

        Returns:
            The endpoint, with ``secret`` populated.

        Raises:
            OxArchiveError: The plan allows no more endpoints, or the URL was
                refused.

        Example:
            >>> endpoint = client.webhooks.create_endpoint(
            ...     "https://example.com/hooks/0xarchive"
            ... )
            >>> save_to_secret_store(endpoint.secret)
        """
        data = self._http.post(
            f"{self._base_path}/endpoints",
            json={"url": url, "description": description},
        )
        return WebhookEndpoint.model_validate(data["data"])

    async def acreate_endpoint(self, url: str, description: str = "") -> WebhookEndpoint:
        """Async version of :meth:`create_endpoint`."""
        data = await self._http.apost(
            f"{self._base_path}/endpoints",
            json={"url": url, "description": description},
        )
        return WebhookEndpoint.model_validate(data["data"])

    def delete_endpoint(self, endpoint_id: str) -> None:
        """
        Delete an endpoint.

        Its subscriptions go with it. Deliveries already queued are not sent.

        Args:
            endpoint_id: Endpoint UUID.

        Raises:
            OxArchiveError: No such endpoint on this account.
        """
        self._http.delete(f"{self._base_path}/endpoints/{endpoint_id}")

    async def adelete_endpoint(self, endpoint_id: str) -> None:
        """Async version of :meth:`delete_endpoint`."""
        await self._http.adelete(f"{self._base_path}/endpoints/{endpoint_id}")

    def rotate_secret(self, endpoint_id: str) -> WebhookSecret:
        """
        Issue a new signing secret, keeping the previous one valid for 24 hours.

        During the overlap every delivery carries two ``v1=`` signatures: one
        under the new secret, one under the old. A receiver holding either
        keeps verifying, which is what makes a zero-downtime roll possible.

        The roll is: rotate, add the new secret alongside the old one, deploy,
        then drop the old one before the window closes.

        Two constraints the server imposes:

        - Only ONE previous secret is carried. Rotating twice inside the
          window overwrites it, and the original stops verifying at once.
        - The window is measured server-side. A receiver cannot extend it.

        Args:
            endpoint_id: Endpoint UUID.

        Returns:
            The new secret, shown once.

        Raises:
            OxArchiveError: No such endpoint on this account.

        Example:
            >>> rotated = client.webhooks.rotate_secret(endpoint.id)
            >>> verifier.add_secret(rotated.secret)  # accept both, then deploy
        """
        data = self._http.post(f"{self._base_path}/endpoints/{endpoint_id}/rotate")
        return WebhookSecret.model_validate(_with_note(data))

    async def arotate_secret(self, endpoint_id: str) -> WebhookSecret:
        """Async version of :meth:`rotate_secret`."""
        data = await self._http.apost(f"{self._base_path}/endpoints/{endpoint_id}/rotate")
        return WebhookSecret.model_validate(_with_note(data))

    def enable_endpoint(self, endpoint_id: str) -> None:
        """
        Re-enable an endpoint that was disabled or auto-disabled.

        0xArchive auto-disables an endpoint after 10 consecutive failures
        spanning at least 6 hours. Fix the receiver first: re-enabling a
        receiver that still fails just walks the same ladder again.

        Args:
            endpoint_id: Endpoint UUID.

        Raises:
            OxArchiveError: No such endpoint on this account.
        """
        self._http.post(f"{self._base_path}/endpoints/{endpoint_id}/enable")

    async def aenable_endpoint(self, endpoint_id: str) -> None:
        """Async version of :meth:`enable_endpoint`."""
        await self._http.apost(f"{self._base_path}/endpoints/{endpoint_id}/enable")

    def test_endpoint(self, endpoint_id: str) -> WebhookTestResult:
        """
        Queue a real ``webhook.test`` delivery to an endpoint.

        This is not a simulation. The test event goes through the identical
        dispatch path with the identical signing, so it is a genuine
        end-to-end check of a receiver's verification code.

        Args:
            endpoint_id: Endpoint UUID.

        Returns:
            The queued delivery and event ids.

        Raises:
            OxArchiveError: No such endpoint on this account.

        Example:
            >>> fired = client.webhooks.test_endpoint(endpoint.id)
            >>> log = client.webhooks.deliveries(endpoint.id, limit=1)
            >>> print(log[0].state, log[0].last_status_code)
        """
        data = self._http.post(f"{self._base_path}/endpoints/{endpoint_id}/test")
        return WebhookTestResult.model_validate(data["data"])

    async def atest_endpoint(self, endpoint_id: str) -> WebhookTestResult:
        """Async version of :meth:`test_endpoint`."""
        data = await self._http.apost(f"{self._base_path}/endpoints/{endpoint_id}/test")
        return WebhookTestResult.model_validate(data["data"])

    def deliveries(
        self,
        endpoint_id: str,
        *,
        limit: Optional[int] = None,
    ) -> list[WebhookDelivery]:
        """
        Read an endpoint's delivery log, newest first.

        Args:
            endpoint_id: Endpoint UUID.
            limit: Deliveries to return (server default: 50).

        Returns:
            Delivery records, including the attempt count, the last status
            code, and the stored payload.

        Example:
            >>> failed = [
            ...     d for d in client.webhooks.deliveries(endpoint.id, limit=200)
            ...     if d.state != "delivered"
            ... ]
        """
        data = self._http.get(
            f"{self._base_path}/endpoints/{endpoint_id}/deliveries",
            params={"limit": limit},
        )
        return [WebhookDelivery.model_validate(x) for x in data["data"]]

    async def adeliveries(
        self,
        endpoint_id: str,
        *,
        limit: Optional[int] = None,
    ) -> list[WebhookDelivery]:
        """Async version of :meth:`deliveries`."""
        data = await self._http.aget(
            f"{self._base_path}/endpoints/{endpoint_id}/deliveries",
            params={"limit": limit},
        )
        return [WebhookDelivery.model_validate(x) for x in data["data"]]

    def redeliver(self, delivery_id: str) -> WebhookRedelivery:
        """
        Send a past delivery again.

        The event id is deliberately unchanged, so a receiver that already
        processed the event will dedupe it away. That is the point: use this
        after fixing a receiver that rejected or dropped the event, not to
        force a second processing of one that succeeded.

        Args:
            delivery_id: Delivery UUID, from :meth:`deliveries`.

        Returns:
            The requeued delivery.

        Raises:
            OxArchiveError: No such delivery on this account.

        Note:
            Requeueing succeeds even when the endpoint is disabled; the
            dispatcher then retires the attempt unsent. Re-enable the endpoint
            with :meth:`enable_endpoint` before redelivering into it.
        """
        data = self._http.post(f"{self._base_path}/deliveries/{delivery_id}/redeliver")
        return WebhookRedelivery.model_validate(data["data"])

    async def aredeliver(self, delivery_id: str) -> WebhookRedelivery:
        """Async version of :meth:`redeliver`."""
        data = await self._http.apost(f"{self._base_path}/deliveries/{delivery_id}/redeliver")
        return WebhookRedelivery.model_validate(data["data"])

    # =========================================================================
    # Subscriptions
    # =========================================================================

    def list_subscriptions(self) -> list[WebhookSubscription]:
        """
        List your subscriptions across every endpoint.

        Returns:
            Every rule on the account, with its stored configuration.
        """
        data = self._http.get(f"{self._base_path}/subscriptions")
        return [WebhookSubscription.model_validate(x) for x in data["data"]]

    async def alist_subscriptions(self) -> list[WebhookSubscription]:
        """Async version of :meth:`list_subscriptions`."""
        data = await self._http.aget(f"{self._base_path}/subscriptions")
        return [WebhookSubscription.model_validate(x) for x in data["data"]]

    def create_subscription(
        self,
        endpoint_id: str,
        event_type: str,
        config: Optional[dict[str, Any]] = None,
    ) -> WebhookSubscription:
        """
        Create a rule: deliver one event type to one endpoint.

        Everything in ``config`` is checked against what the event type
        declares in :meth:`event_types`; nothing is silently ignored. An
        undeclared key, an operator that does not apply to a metric, or a
        parameter outside its bounds is refused with the declaration in the
        error. Declared parameter defaults are filled in server-side, so the
        stored configuration comes back more complete than what you sent.

        Run :meth:`dry_run` or :meth:`estimate` with the same ``config``
        first. Both validate it identically, and they tell you how much
        traffic the rule will actually produce.

        Args:
            endpoint_id: Endpoint UUID to deliver to.
            event_type: Event type from the catalog, for example
                ``account.fill``.
            config: Filters, params, and conditions. Keys are event-specific
                and declared in the catalog; commonly ``venue``, ``symbols``,
                ``addresses``, ``params``, and ``conditions``. Sent on the
                wire as ``filters``.

        Returns:
            The created rule, with its normalised configuration.

        Raises:
            OxArchiveError: The plan allows no more subscriptions, the event
                type is unknown or not yet live, or the configuration was
                refused.

        Example:
            >>> sub = client.webhooks.create_subscription(
            ...     endpoint_id=endpoint.id,
            ...     event_type="account.fill",
            ...     config={
            ...         "addresses": ["0x00000000000000000000000000000000000000a1"],
            ...         "conditions": [
            ...             {"metric": "notional_usd", "op": ">=", "value": 25000}
            ...         ],
            ...     },
            ... )
        """
        data = self._http.post(
            f"{self._base_path}/subscriptions",
            json={
                "endpoint_id": endpoint_id,
                "event_type": event_type,
                "filters": config or {},
            },
        )
        return WebhookSubscription.model_validate(data["data"])

    async def acreate_subscription(
        self,
        endpoint_id: str,
        event_type: str,
        config: Optional[dict[str, Any]] = None,
    ) -> WebhookSubscription:
        """Async version of :meth:`create_subscription`."""
        data = await self._http.apost(
            f"{self._base_path}/subscriptions",
            json={
                "endpoint_id": endpoint_id,
                "event_type": event_type,
                "filters": config or {},
            },
        )
        return WebhookSubscription.model_validate(data["data"])

    def update_subscription(
        self,
        subscription_id: str,
        *,
        config: Optional[dict[str, Any]] = None,
        enabled: Optional[bool] = None,
    ) -> WebhookSubscription:
        """
        Edit a rule in place: retune its configuration, or switch it on or off.

        ``config`` REPLACES the stored configuration rather than merging into
        it, so send the whole object. Omit it to change only ``enabled``.

        Args:
            subscription_id: Subscription UUID.
            config: The complete replacement configuration, validated exactly
                as at create time.
            enabled: Your own on/off switch for the rule.

        Returns:
            The updated rule.

        Raises:
            OxArchiveError: No such subscription, or the configuration was
                refused.

        Example:
            >>> client.webhooks.update_subscription(sub.id, enabled=False)
        """
        body: dict[str, Any] = {}
        if config is not None:
            body["filters"] = config
        if enabled is not None:
            body["enabled"] = enabled
        data = self._http.patch(f"{self._base_path}/subscriptions/{subscription_id}", json=body)
        return WebhookSubscription.model_validate(data["data"])

    async def aupdate_subscription(
        self,
        subscription_id: str,
        *,
        config: Optional[dict[str, Any]] = None,
        enabled: Optional[bool] = None,
    ) -> WebhookSubscription:
        """Async version of :meth:`update_subscription`."""
        body: dict[str, Any] = {}
        if config is not None:
            body["filters"] = config
        if enabled is not None:
            body["enabled"] = enabled
        data = await self._http.apatch(
            f"{self._base_path}/subscriptions/{subscription_id}", json=body
        )
        return WebhookSubscription.model_validate(data["data"])

    def delete_subscription(self, subscription_id: str) -> None:
        """
        Delete a rule. Its endpoint is left alone.

        Args:
            subscription_id: Subscription UUID.

        Raises:
            OxArchiveError: No such subscription on this account.
        """
        self._http.delete(f"{self._base_path}/subscriptions/{subscription_id}")

    async def adelete_subscription(self, subscription_id: str) -> None:
        """Async version of :meth:`delete_subscription`."""
        await self._http.adelete(f"{self._base_path}/subscriptions/{subscription_id}")

    def dry_run(
        self,
        event_type: str,
        config: Optional[dict[str, Any]] = None,
        *,
        lookback_s: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> WebhookDryRun:
        """
        Show which recent occurrences a rule WOULD have delivered.

        Nothing is created and nothing is delivered: the configuration is
        validated and normalised exactly as :meth:`create_subscription` would,
        then evaluated against history with the detectors' own matching.

        Available on every plan, Free included, so a rule can be checked
        before there is an endpoint to deliver it to. Types whose scope is
        ``addresses`` preview against your watched wallets, so previewing one
        needs at least one wallet on the list.

        Args:
            event_type: Event type from the catalog. Not every live type is
                dry-runnable yet; the error names the ones that are.
            config: The same configuration you would subscribe with. Sent on
                the wire as ``config``.
            lookback_s: Seconds of history to scan, ending now. 60 to 86400
                (24 hours). Server default: 3600.
            limit: Occurrences to return, newest first. 1 to 200. Server
                default: 100.

        Returns:
            The matches and the window the answer vouches for.

        Raises:
            OxArchiveError: The event type is unknown or not dry-runnable,
                the window or page size is out of bounds, the configuration
                was refused, or the per-minute preview budget is spent
                (dry-runs and estimates share 6 per minute).

        Example:
            >>> preview = client.webhooks.dry_run(
            ...     "market.liquidation",
            ...     {"venue": "hyperliquid", "min_notional_usd": 500000},
            ...     lookback_s=86400,
            ... )
            >>> print(f"{preview.matched} in the last day")
        """
        body: dict[str, Any] = {"event_type": event_type, "config": config or {}}
        if lookback_s is not None:
            body["lookback_s"] = lookback_s
        if limit is not None:
            body["limit"] = limit
        data = self._http.post(f"{self._base_path}/subscriptions/dry-run", json=body)
        return WebhookDryRun.model_validate(data["data"])

    async def adry_run(
        self,
        event_type: str,
        config: Optional[dict[str, Any]] = None,
        *,
        lookback_s: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> WebhookDryRun:
        """Async version of :meth:`dry_run`."""
        body: dict[str, Any] = {"event_type": event_type, "config": config or {}}
        if lookback_s is not None:
            body["lookback_s"] = lookback_s
        if limit is not None:
            body["limit"] = limit
        data = await self._http.apost(f"{self._base_path}/subscriptions/dry-run", json=body)
        return WebhookDryRun.model_validate(data["data"])

    def estimate(
        self,
        event_type: str,
        config: Optional[dict[str, Any]] = None,
        *,
        lookback_days: Optional[int] = None,
    ) -> WebhookEstimate:
        """
        Show how often a rule WOULD have fired, per day, over a historical window.

        This is the call to make before turning a rule on. It returns the
        daily counts, the median and busiest day, and a threshold ladder: the
        rate the same rule would have had at other thresholds. Compare
        ``per_day_p50`` against your plan's deliveries-per-day allowance.

        Available on every plan, Free included. Types whose scope is
        ``addresses`` preview against your watched wallets, so previewing one
        needs at least one wallet on the list.

        Args:
            event_type: Event type from the catalog. Not every live type is
                estimable yet; the error names the ones that are.
            config: The same configuration you would subscribe with. Sent on
                the wire as ``config``.
            lookback_days: Days of history to evaluate, 1 to 30. Server
                default: 7. Some types cap their own window lower, and the
                response says which window it actually covered.

        Returns:
            The daily rate, the threshold ladder, and a sample of matches.

        Raises:
            OxArchiveError: The event type is unknown or not estimable, the
                window is out of bounds, the configuration was refused, or
                the per-minute preview budget is spent (dry-runs and
                estimates share 6 per minute).

        Example:
            >>> est = client.webhooks.estimate("market.liquidation_burst")
            >>> print(f"median {est.per_day_p50:.0f}/day, worst {est.per_day_max}")
            >>> for rung in est.ladder:
            ...     print(f"  at {rung.value:,.0f}: {rung.per_day:.1f}/day")
        """
        body: dict[str, Any] = {"event_type": event_type, "config": config or {}}
        if lookback_days is not None:
            body["lookback_days"] = lookback_days
        data = self._http.post(f"{self._base_path}/subscriptions/estimate", json=body)
        return WebhookEstimate.model_validate(data["data"])

    async def aestimate(
        self,
        event_type: str,
        config: Optional[dict[str, Any]] = None,
        *,
        lookback_days: Optional[int] = None,
    ) -> WebhookEstimate:
        """Async version of :meth:`estimate`."""
        body: dict[str, Any] = {"event_type": event_type, "config": config or {}}
        if lookback_days is not None:
            body["lookback_days"] = lookback_days
        data = await self._http.apost(f"{self._base_path}/subscriptions/estimate", json=body)
        return WebhookEstimate.model_validate(data["data"])

    # =========================================================================
    # Watched addresses
    # =========================================================================

    def list_addresses(self) -> list[WebhookWatchedAddress]:
        """
        List the wallets the account-scoped event types may fire on.

        Returns:
            Every watched wallet on the account.
        """
        data = self._http.get(f"{self._base_path}/addresses")
        return [WebhookWatchedAddress.model_validate(x) for x in data["data"]]

    async def alist_addresses(self) -> list[WebhookWatchedAddress]:
        """Async version of :meth:`list_addresses`."""
        data = await self._http.aget(f"{self._base_path}/addresses")
        return [WebhookWatchedAddress.model_validate(x) for x in data["data"]]

    def add_address(self, address: str, label: str = "") -> WebhookWatchedAddress:
        """
        Watch a wallet, so the account-scoped event types can fire on it.

        Event types whose scope is ``addresses`` only ever fire on wallets
        added here, and a subscription cannot filter on a wallet that is not
        on the list. Add the wallet first, then the rule.

        Re-adding a wallet already on the list is idempotent and does not
        consume another slot. The address is normalised to lowercase.

        Args:
            address: A 0x-prefixed 40-hex-character EVM address.
            label: Your own label, truncated to 64 characters.

        Returns:
            The watched wallet.

        Raises:
            OxArchiveError: The plan allows no more watched wallets, the
                address is malformed, or it is a bridge system address (those
                are a counterparty to every bridge move of their token, not
                an account).

        Example:
            >>> client.webhooks.add_address(
            ...     "0x00000000000000000000000000000000000000a1", label="desk 1"
            ... )
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

        Subscriptions that filtered on it keep their stored configuration;
        they simply stop matching it.

        Args:
            address_id: Watched-address UUID, from :meth:`list_addresses`.

        Raises:
            OxArchiveError: No such watched address on this account.
        """
        self._http.delete(f"{self._base_path}/addresses/{address_id}")

    async def adelete_address(self, address_id: str) -> None:
        """Async version of :meth:`delete_address`."""
        await self._http.adelete(f"{self._base_path}/addresses/{address_id}")
