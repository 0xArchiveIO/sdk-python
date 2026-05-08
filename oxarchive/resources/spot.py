"""Hyperliquid spot pair / TWAP API resources.

Spot lives at ``/v1/hyperliquid/spot`` and uses dashed canonical symbols
(e.g. ``HYPE-USDC``, ``PURR-USDC``). The server resolves dashed to wire
format (``PURR/USDC`` or ``@107``) internally, so SDK callers always pass
the dashed form.

Spot has no funding, no open interest, no liquidations, and no candles by
design. Trades go back to 2025-03-22; orderbook / L4 / TWAP / orders are
live-only from 2026-05-05.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from ..http import HttpClient
from ..types import CursorResponse, SpotPair, SpotTwapStatus, Timestamp


class SpotPairsResource:
    """
    Hyperliquid spot pairs resource.

    Example:
        >>> # List all spot pairs
        >>> pairs = client.spot.pairs.list()
        >>>
        >>> # Get a specific pair (dashed canonical form)
        >>> hype = client.spot.pairs.get("HYPE-USDC")
        >>> print(f"HYPE-USDC asset_id: {hype.asset_id}")
    """

    def __init__(self, http: HttpClient, base_path: str = "/v1/hyperliquid/spot"):
        self._http = http
        self._base_path = base_path

    def list(self) -> list[SpotPair]:
        """List all spot trading pairs."""
        data = self._http.get(f"{self._base_path}/pairs")
        return [SpotPair.model_validate(item) for item in data["data"]]

    async def alist(self) -> list[SpotPair]:
        """Async version of list()."""
        data = await self._http.aget(f"{self._base_path}/pairs")
        return [SpotPair.model_validate(item) for item in data["data"]]

    def get(self, symbol: str) -> SpotPair:
        """
        Get a specific spot pair by dashed canonical symbol.

        Args:
            symbol: The pair symbol in dashed canonical form (e.g. ``HYPE-USDC``,
                ``PURR-USDC``). Symbol is upper-cased before sending.
        """
        data = self._http.get(f"{self._base_path}/pairs/{symbol.upper()}")
        return SpotPair.model_validate(data["data"])

    async def aget(self, symbol: str) -> SpotPair:
        """Async version of get()."""
        data = await self._http.aget(f"{self._base_path}/pairs/{symbol.upper()}")
        return SpotPair.model_validate(data["data"])


class SpotTwapResource:
    """
    Hyperliquid spot TWAP status resource.

    Two query modes:
      * by symbol: ``/v1/hyperliquid/spot/twap/{symbol}`` returns TWAP statuses
        for all users on that pair.
      * by user: ``/v1/hyperliquid/spot/twap/user/{user}`` returns TWAP statuses
        for that wallet across all pairs.

    Example:
        >>> recent = client.spot.twap.by_symbol("HYPE-USDC", start=..., end=...)
        >>> mine = client.spot.twap.by_user("0xabc...", start=..., end=...)
    """

    def __init__(self, http: HttpClient, base_path: str = "/v1/hyperliquid/spot"):
        self._http = http
        self._base_path = base_path

    def _convert_timestamp(self, ts: Optional[Timestamp]) -> Optional[int]:
        """Convert timestamp to Unix milliseconds."""
        if ts is None:
            return None
        if isinstance(ts, int):
            return ts
        if isinstance(ts, datetime):
            return int(ts.timestamp() * 1000)
        if isinstance(ts, str):
            try:
                dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                return int(dt.timestamp() * 1000)
            except ValueError:
                return int(ts)
        return None

    def by_symbol(
        self,
        symbol: str,
        *,
        start: Optional[Timestamp] = None,
        end: Optional[Timestamp] = None,
        cursor: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> CursorResponse[list[SpotTwapStatus]]:
        """
        Get TWAP status records for a spot pair.

        Args:
            symbol: Pair symbol in dashed canonical form (e.g. ``HYPE-USDC``).
            start: Optional start timestamp.
            end: Optional end timestamp.
            cursor: Pagination cursor.
            limit: Page size.
        """
        data = self._http.get(
            f"{self._base_path}/twap/{symbol.upper()}",
            params={
                "start": self._convert_timestamp(start),
                "end": self._convert_timestamp(end),
                "cursor": cursor,
                "limit": limit,
            },
        )
        return CursorResponse(
            data=[SpotTwapStatus.model_validate(item) for item in data["data"]],
            next_cursor=data.get("meta", {}).get("next_cursor"),
        )

    async def aby_symbol(
        self,
        symbol: str,
        *,
        start: Optional[Timestamp] = None,
        end: Optional[Timestamp] = None,
        cursor: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> CursorResponse[list[SpotTwapStatus]]:
        """Async version of by_symbol()."""
        data = await self._http.aget(
            f"{self._base_path}/twap/{symbol.upper()}",
            params={
                "start": self._convert_timestamp(start),
                "end": self._convert_timestamp(end),
                "cursor": cursor,
                "limit": limit,
            },
        )
        return CursorResponse(
            data=[SpotTwapStatus.model_validate(item) for item in data["data"]],
            next_cursor=data.get("meta", {}).get("next_cursor"),
        )

    def by_user(
        self,
        user: str,
        *,
        start: Optional[Timestamp] = None,
        end: Optional[Timestamp] = None,
        cursor: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> CursorResponse[list[SpotTwapStatus]]:
        """
        Get TWAP status records for a wallet address across all pairs.

        Args:
            user: Wallet address (e.g. ``0x1234...``).
            start: Optional start timestamp.
            end: Optional end timestamp.
            cursor: Pagination cursor.
            limit: Page size.
        """
        data = self._http.get(
            f"{self._base_path}/twap/user/{user}",
            params={
                "start": self._convert_timestamp(start),
                "end": self._convert_timestamp(end),
                "cursor": cursor,
                "limit": limit,
            },
        )
        return CursorResponse(
            data=[SpotTwapStatus.model_validate(item) for item in data["data"]],
            next_cursor=data.get("meta", {}).get("next_cursor"),
        )

    async def aby_user(
        self,
        user: str,
        *,
        start: Optional[Timestamp] = None,
        end: Optional[Timestamp] = None,
        cursor: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> CursorResponse[list[SpotTwapStatus]]:
        """Async version of by_user()."""
        data = await self._http.aget(
            f"{self._base_path}/twap/user/{user}",
            params={
                "start": self._convert_timestamp(start),
                "end": self._convert_timestamp(end),
                "cursor": cursor,
                "limit": limit,
            },
        )
        return CursorResponse(
            data=[SpotTwapStatus.model_validate(item) for item in data["data"]],
            next_cursor=data.get("meta", {}).get("next_cursor"),
        )
