"""Exchange-specific client classes."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from .http import HttpClient
from .resources import (
    OrderBookResource,
    TradesResource,
    InstrumentsResource,
    LighterInstrumentsResource,
    Hip3InstrumentsResource,
    FundingResource,
    OpenInterestResource,
    CandlesResource,
    LiquidationsResource,
)
from .types import (
    CoinFreshness,
    CoinSummary,
    CursorResponse,
    DataTypeFreshness,
    LiquidationVolume,
    PriceSnapshot,
    Timestamp,
)


class HyperliquidClient:
    """
    Hyperliquid exchange client.

    Access Hyperliquid market data through the 0xarchive API.

    Example:
        >>> client = oxarchive.Client(api_key="...")
        >>> orderbook = client.hyperliquid.orderbook.get("BTC")
        >>> trades = client.hyperliquid.trades.list("ETH", start=..., end=...)
    """

    def __init__(self, http: HttpClient):
        self._http = http
        base_path = "/v1/hyperliquid"

        self.orderbook = OrderBookResource(http, base_path)
        """Order book data (L2 snapshots from April 2023)"""

        self.trades = TradesResource(http, base_path)
        """Trade/fill history"""

        self.instruments = InstrumentsResource(http, base_path)
        """Trading instruments metadata"""

        self.funding = FundingResource(http, base_path)
        """Funding rates"""

        self.open_interest = OpenInterestResource(http, base_path)
        """Open interest"""

        self.candles = CandlesResource(http, base_path)
        """OHLCV candle data"""

        self.liquidations = LiquidationsResource(http, base_path)
        """Liquidation events (May 2025+)"""

        self.hip3 = Hip3Client(http)
        """HIP-3 builder-deployed perpetuals (February 2026+)"""

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

    # -----------------------------------------------------------------
    # Convenience methods (not tied to a specific resource)
    # -----------------------------------------------------------------

    def get_liquidation_volume(
        self,
        coin: str,
        *,
        start: Optional[Timestamp] = None,
        end: Optional[Timestamp] = None,
        interval: Optional[str] = None,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
    ) -> CursorResponse[list[LiquidationVolume]]:
        """
        Get aggregated liquidation volume for a coin.

        Args:
            coin: Coin symbol (e.g. 'BTC')
            start: Start timestamp (ISO or Unix ms)
            end: End timestamp (ISO or Unix ms)
            interval: Aggregation interval (e.g. '1h', '4h', '1d')
            limit: Max records to return
            cursor: Pagination cursor

        Returns:
            CursorResponse with liquidation volume buckets and next_cursor
        """
        params: dict = {
            "start": self._convert_timestamp(start),
            "end": self._convert_timestamp(end),
            "interval": interval,
            "limit": limit,
            "cursor": cursor,
        }
        data = self._http.get(
            f"/v1/hyperliquid/liquidations/{coin.upper()}/volume",
            params=params,
        )
        return CursorResponse(
            data=[LiquidationVolume.model_validate(item) for item in data["data"]],
            next_cursor=data.get("meta", {}).get("next_cursor"),
        )

    async def aget_liquidation_volume(
        self,
        coin: str,
        *,
        start: Optional[Timestamp] = None,
        end: Optional[Timestamp] = None,
        interval: Optional[str] = None,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
    ) -> CursorResponse[list[LiquidationVolume]]:
        """Async version of get_liquidation_volume()."""
        params: dict = {
            "start": self._convert_timestamp(start),
            "end": self._convert_timestamp(end),
            "interval": interval,
            "limit": limit,
            "cursor": cursor,
        }
        data = await self._http.aget(
            f"/v1/hyperliquid/liquidations/{coin.upper()}/volume",
            params=params,
        )
        return CursorResponse(
            data=[LiquidationVolume.model_validate(item) for item in data["data"]],
            next_cursor=data.get("meta", {}).get("next_cursor"),
        )

    def get_freshness(self, coin: str) -> CoinFreshness:
        """
        Get data freshness for a coin across all data types.

        Returns how recently each data type (orderbook, trades, funding,
        open interest, liquidations) was updated for the given coin.

        Args:
            coin: Coin symbol (e.g. 'BTC')

        Returns:
            CoinFreshness with per-data-type lag information
        """
        data = self._http.get(f"/v1/hyperliquid/freshness/{coin.upper()}")
        return CoinFreshness.model_validate(data["data"])

    async def aget_freshness(self, coin: str) -> CoinFreshness:
        """Async version of get_freshness()."""
        data = await self._http.aget(f"/v1/hyperliquid/freshness/{coin.upper()}")
        return CoinFreshness.model_validate(data["data"])

    def get_summary(self, coin: str) -> CoinSummary:
        """
        Get combined market summary for a coin.

        Returns a single snapshot with price, funding, open interest,
        volume, and liquidation metrics.

        Args:
            coin: Coin symbol (e.g. 'BTC')

        Returns:
            CoinSummary with all market metrics
        """
        data = self._http.get(f"/v1/hyperliquid/summary/{coin.upper()}")
        return CoinSummary.model_validate(data["data"])

    async def aget_summary(self, coin: str) -> CoinSummary:
        """Async version of get_summary()."""
        data = await self._http.aget(f"/v1/hyperliquid/summary/{coin.upper()}")
        return CoinSummary.model_validate(data["data"])

    def get_price_history(
        self,
        coin: str,
        *,
        start: Optional[Timestamp] = None,
        end: Optional[Timestamp] = None,
        interval: Optional[str] = None,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
    ) -> CursorResponse[list[PriceSnapshot]]:
        """
        Get mark/oracle price history for a coin.

        Args:
            coin: Coin symbol (e.g. 'BTC')
            start: Start timestamp (ISO or Unix ms)
            end: End timestamp (ISO or Unix ms)
            interval: Aggregation interval (e.g. '1h', '4h', '1d')
            limit: Max records to return
            cursor: Pagination cursor

        Returns:
            CursorResponse with price snapshots and next_cursor
        """
        params: dict = {
            "start": self._convert_timestamp(start),
            "end": self._convert_timestamp(end),
            "interval": interval,
            "limit": limit,
            "cursor": cursor,
        }
        data = self._http.get(
            f"/v1/hyperliquid/prices/{coin.upper()}",
            params=params,
        )
        return CursorResponse(
            data=[PriceSnapshot.model_validate(item) for item in data["data"]],
            next_cursor=data.get("meta", {}).get("next_cursor"),
        )

    async def aget_price_history(
        self,
        coin: str,
        *,
        start: Optional[Timestamp] = None,
        end: Optional[Timestamp] = None,
        interval: Optional[str] = None,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
    ) -> CursorResponse[list[PriceSnapshot]]:
        """Async version of get_price_history()."""
        params: dict = {
            "start": self._convert_timestamp(start),
            "end": self._convert_timestamp(end),
            "interval": interval,
            "limit": limit,
            "cursor": cursor,
        }
        data = await self._http.aget(
            f"/v1/hyperliquid/prices/{coin.upper()}",
            params=params,
        )
        return CursorResponse(
            data=[PriceSnapshot.model_validate(item) for item in data["data"]],
            next_cursor=data.get("meta", {}).get("next_cursor"),
        )


class Hip3Client:
    """
    HIP-3 builder-deployed perpetuals client.

    Access Hyperliquid HIP-3 builder perps data through the 0xarchive API.
    Free: km:US500 only. Build+: all coins. Orderbook: Pro+.

    Example:
        >>> client = oxarchive.Client(api_key="...")
        >>> orderbook = client.hyperliquid.hip3.orderbook.get("xyz:XYZ100")
        >>> trades = client.hyperliquid.hip3.trades.recent("xyz:XYZ100")
    """

    def __init__(self, http: HttpClient):
        self._http = http
        base_path = "/v1/hyperliquid/hip3"
        coin_transform = lambda c: c  # noqa: E731 — HIP-3 coins are case-sensitive (e.g. "xyz:XYZ100")

        self.instruments = Hip3InstrumentsResource(http, base_path, coin_transform=coin_transform)
        """HIP-3 instruments with latest market data"""

        self.orderbook = OrderBookResource(http, base_path, coin_transform=coin_transform)
        """Order book snapshots (February 2026+)"""

        self.trades = TradesResource(http, base_path, coin_transform=coin_transform)
        """Trade/fill history"""

        self.funding = FundingResource(http, base_path, coin_transform=coin_transform)
        """Funding rates"""

        self.open_interest = OpenInterestResource(http, base_path, coin_transform=coin_transform)
        """Open interest"""

        self.candles = CandlesResource(http, base_path, coin_transform=coin_transform)
        """OHLCV candle data"""

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

    def get_freshness(self, coin: str) -> CoinFreshness:
        """
        Get data freshness for a coin across all data types.

        Args:
            coin: Coin symbol (case-sensitive, e.g. 'km:US500')

        Returns:
            CoinFreshness with per-data-type lag information
        """
        data = self._http.get(f"/v1/hyperliquid/hip3/freshness/{coin}")
        return CoinFreshness.model_validate(data["data"])

    async def aget_freshness(self, coin: str) -> CoinFreshness:
        """Async version of get_freshness()."""
        data = await self._http.aget(f"/v1/hyperliquid/hip3/freshness/{coin}")
        return CoinFreshness.model_validate(data["data"])

    def get_summary(self, coin: str) -> CoinSummary:
        """
        Get combined market summary for a coin.

        Args:
            coin: Coin symbol (case-sensitive, e.g. 'km:US500')

        Returns:
            CoinSummary with all market metrics
        """
        data = self._http.get(f"/v1/hyperliquid/hip3/summary/{coin}")
        return CoinSummary.model_validate(data["data"])

    async def aget_summary(self, coin: str) -> CoinSummary:
        """Async version of get_summary()."""
        data = await self._http.aget(f"/v1/hyperliquid/hip3/summary/{coin}")
        return CoinSummary.model_validate(data["data"])

    def get_price_history(
        self,
        coin: str,
        *,
        start: Optional[Timestamp] = None,
        end: Optional[Timestamp] = None,
        interval: Optional[str] = None,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
    ) -> CursorResponse[list[PriceSnapshot]]:
        """
        Get mark/oracle price history for a coin.

        Args:
            coin: Coin symbol (case-sensitive, e.g. 'km:US500')
            start: Start timestamp (ISO or Unix ms)
            end: End timestamp (ISO or Unix ms)
            interval: Aggregation interval (e.g. '1h', '4h', '1d')
            limit: Max records to return
            cursor: Pagination cursor

        Returns:
            CursorResponse with price snapshots and next_cursor
        """
        params: dict = {
            "start": self._convert_timestamp(start),
            "end": self._convert_timestamp(end),
            "interval": interval,
            "limit": limit,
            "cursor": cursor,
        }
        data = self._http.get(
            f"/v1/hyperliquid/hip3/prices/{coin}",
            params=params,
        )
        return CursorResponse(
            data=[PriceSnapshot.model_validate(item) for item in data["data"]],
            next_cursor=data.get("meta", {}).get("next_cursor"),
        )

    async def aget_price_history(
        self,
        coin: str,
        *,
        start: Optional[Timestamp] = None,
        end: Optional[Timestamp] = None,
        interval: Optional[str] = None,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
    ) -> CursorResponse[list[PriceSnapshot]]:
        """Async version of get_price_history()."""
        params: dict = {
            "start": self._convert_timestamp(start),
            "end": self._convert_timestamp(end),
            "interval": interval,
            "limit": limit,
            "cursor": cursor,
        }
        data = await self._http.aget(
            f"/v1/hyperliquid/hip3/prices/{coin}",
            params=params,
        )
        return CursorResponse(
            data=[PriceSnapshot.model_validate(item) for item in data["data"]],
            next_cursor=data.get("meta", {}).get("next_cursor"),
        )


class LighterClient:
    """
    Lighter.xyz exchange client.

    Access Lighter.xyz market data through the 0xarchive API.

    Example:
        >>> client = oxarchive.Client(api_key="...")
        >>> orderbook = client.lighter.orderbook.get("BTC")
        >>> trades = client.lighter.trades.list("ETH", start=..., end=...)
        >>> instruments = client.lighter.instruments.list()
        >>> print(f"ETH taker fee: {instruments[0].taker_fee}")
    """

    def __init__(self, http: HttpClient):
        self._http = http
        base_path = "/v1/lighter"

        self.orderbook = OrderBookResource(http, base_path)
        """Order book data (L2 snapshots)"""

        self.trades = TradesResource(http, base_path)
        """Trade/fill history"""

        self.instruments = LighterInstrumentsResource(http, base_path)
        """Trading instruments metadata (returns LighterInstrument with fees, min amounts, etc.)"""

        self.funding = FundingResource(http, base_path)
        """Funding rates"""

        self.open_interest = OpenInterestResource(http, base_path)
        """Open interest"""

        self.candles = CandlesResource(http, base_path)
        """OHLCV candle data"""

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

    def get_freshness(self, coin: str) -> CoinFreshness:
        """
        Get data freshness for a coin across all data types.

        Args:
            coin: Coin symbol (e.g. 'BTC')

        Returns:
            CoinFreshness with per-data-type lag information
        """
        data = self._http.get(f"/v1/lighter/freshness/{coin.upper()}")
        return CoinFreshness.model_validate(data["data"])

    async def aget_freshness(self, coin: str) -> CoinFreshness:
        """Async version of get_freshness()."""
        data = await self._http.aget(f"/v1/lighter/freshness/{coin.upper()}")
        return CoinFreshness.model_validate(data["data"])

    def get_summary(self, coin: str) -> CoinSummary:
        """
        Get combined market summary for a coin.

        Args:
            coin: Coin symbol (e.g. 'BTC')

        Returns:
            CoinSummary with all market metrics
        """
        data = self._http.get(f"/v1/lighter/summary/{coin.upper()}")
        return CoinSummary.model_validate(data["data"])

    async def aget_summary(self, coin: str) -> CoinSummary:
        """Async version of get_summary()."""
        data = await self._http.aget(f"/v1/lighter/summary/{coin.upper()}")
        return CoinSummary.model_validate(data["data"])

    def get_price_history(
        self,
        coin: str,
        *,
        start: Optional[Timestamp] = None,
        end: Optional[Timestamp] = None,
        interval: Optional[str] = None,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
    ) -> CursorResponse[list[PriceSnapshot]]:
        """
        Get mark/oracle price history for a coin.

        Args:
            coin: Coin symbol (e.g. 'BTC')
            start: Start timestamp (ISO or Unix ms)
            end: End timestamp (ISO or Unix ms)
            interval: Aggregation interval (e.g. '1h', '4h', '1d')
            limit: Max records to return
            cursor: Pagination cursor

        Returns:
            CursorResponse with price snapshots and next_cursor
        """
        params: dict = {
            "start": self._convert_timestamp(start),
            "end": self._convert_timestamp(end),
            "interval": interval,
            "limit": limit,
            "cursor": cursor,
        }
        data = self._http.get(
            f"/v1/lighter/prices/{coin.upper()}",
            params=params,
        )
        return CursorResponse(
            data=[PriceSnapshot.model_validate(item) for item in data["data"]],
            next_cursor=data.get("meta", {}).get("next_cursor"),
        )

    async def aget_price_history(
        self,
        coin: str,
        *,
        start: Optional[Timestamp] = None,
        end: Optional[Timestamp] = None,
        interval: Optional[str] = None,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
    ) -> CursorResponse[list[PriceSnapshot]]:
        """Async version of get_price_history()."""
        params: dict = {
            "start": self._convert_timestamp(start),
            "end": self._convert_timestamp(end),
            "interval": interval,
            "limit": limit,
            "cursor": cursor,
        }
        data = await self._http.aget(
            f"/v1/lighter/prices/{coin.upper()}",
            params=params,
        )
        return CursorResponse(
            data=[PriceSnapshot.model_validate(item) for item in data["data"]],
            next_cursor=data.get("meta", {}).get("next_cursor"),
        )
