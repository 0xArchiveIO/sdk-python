"""Wallet classification API resource (Hyperliquid core and HIP-3)."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Literal, Optional, Union

from ..http import HttpClient
from ..types import WalletClassification, WalletClassifySort


def _snapshot_date(value: Union[str, date, datetime, None]) -> Optional[str]:
    """``YYYY-MM-DD`` for the ``date`` parameter.

    A datetime without a time zone is UTC; an aware one is converted to UTC
    first. A string is sent as given.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is not None and value.tzinfo.utcoffset(value) is not None:
            value = value.astimezone(timezone.utc)
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return value


class WalletsResource:
    """
    Wallet classification: precomputed daily behavior metrics for active wallets.

    One row per wallet with order, fill, cancel, maker, fee, PnL, TWAP,
    priority gas and builder metrics over the day, filtered and sorted server
    side. Page with ``limit`` and ``offset``; ``total`` is the number of
    wallets matching the filters. Each call costs 10 credits, with row-based
    metering on the wallets returned where it applies.

    Example:
        >>> page = client.hyperliquid.wallets.classify(
        ...     sort="total_volume_usd", min_volume_usd=1_000_000, limit=50
        ... )
        >>> for wallet in page.wallets:
        ...     print(wallet.address, wallet.metrics.maker_ratio)
    """

    def __init__(self, http: HttpClient, base_path: str = "/v1/hyperliquid") -> None:
        self._http = http
        self._base_path = base_path

    @staticmethod
    def _params(
        min_orders: Optional[int],
        min_volume_usd: Optional[float],
        sort: Optional[WalletClassifySort],
        order: Optional[Literal["asc", "desc"]],
        limit: Optional[int],
        offset: Optional[int],
        uses_twap: Optional[bool],
        uses_priority_gas: Optional[bool],
        min_cancel_rate: Optional[float],
        max_cancel_rate: Optional[float],
        date: Union[str, date, datetime, None],
    ) -> dict[str, Any]:
        return {
            "min_orders": min_orders,
            "min_volume_usd": min_volume_usd,
            "sort": sort,
            "order": order,
            "limit": limit,
            "offset": offset,
            "uses_twap": uses_twap,
            "uses_priority_gas": uses_priority_gas,
            "min_cancel_rate": min_cancel_rate,
            "max_cancel_rate": max_cancel_rate,
            "date": _snapshot_date(date),
        }

    def classify(
        self,
        *,
        min_orders: Optional[int] = None,
        min_volume_usd: Optional[float] = None,
        sort: Optional[WalletClassifySort] = None,
        order: Optional[Literal["asc", "desc"]] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        uses_twap: Optional[bool] = None,
        uses_priority_gas: Optional[bool] = None,
        min_cancel_rate: Optional[float] = None,
        max_cancel_rate: Optional[float] = None,
        date: Union[str, date, datetime, None] = None,
    ) -> WalletClassification:
        """
        Classify active wallets by their daily behavior.

        Args:
            min_orders: Minimum order count (server default 100).
            min_volume_usd: Minimum fill volume in USD (server default 0).
            sort: Metric to sort by (server default ``total_orders``).
            order: ``"asc"`` or ``"desc"`` (server default ``"desc"``).
            limit: Wallets per page, 1 to 1000 (server default 100).
            offset: Wallets to skip, at most 100000 (server default 0).
            uses_twap: Keep only wallets that did (True) or did not (False) use TWAP.
            uses_priority_gas: Keep only wallets that did or did not pay priority gas.
            min_cancel_rate: Minimum cancel rate, 0.0 to 1.0.
            max_cancel_rate: Maximum cancel rate, 0.0 to 1.0.
            date: Daily snapshot date (default: yesterday, UTC). A ``date``,
                a ``YYYY-MM-DD`` string, or a datetime (a datetime without a
                time zone is UTC).

        Returns:
            WalletClassification with ``wallets``, ``total`` and ``date``.
        """
        data = self._http.get(
            f"{self._base_path}/wallets/classify",
            params=self._params(
                min_orders,
                min_volume_usd,
                sort,
                order,
                limit,
                offset,
                uses_twap,
                uses_priority_gas,
                min_cancel_rate,
                max_cancel_rate,
                date,
            ),
        )
        return WalletClassification.model_validate(data["data"])

    async def aclassify(
        self,
        *,
        min_orders: Optional[int] = None,
        min_volume_usd: Optional[float] = None,
        sort: Optional[WalletClassifySort] = None,
        order: Optional[Literal["asc", "desc"]] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        uses_twap: Optional[bool] = None,
        uses_priority_gas: Optional[bool] = None,
        min_cancel_rate: Optional[float] = None,
        max_cancel_rate: Optional[float] = None,
        date: Union[str, date, datetime, None] = None,
    ) -> WalletClassification:
        """Async version of :meth:`classify`."""
        data = await self._http.aget(
            f"{self._base_path}/wallets/classify",
            params=self._params(
                min_orders,
                min_volume_usd,
                sort,
                order,
                limit,
                offset,
                uses_twap,
                uses_priority_gas,
                min_cancel_rate,
                max_cancel_rate,
                date,
            ),
        )
        return WalletClassification.model_validate(data["data"])

