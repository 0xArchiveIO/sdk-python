"""Exchange-specific client classes."""

from __future__ import annotations

import warnings
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
    OrdersResource,
    L4OrderBookResource,
    L3OrderBookResource,
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


def _resolve_symbol(symbol, kwargs):
    """Shared helper for coin->symbol deprecation in convenience methods."""
    if "coin" in kwargs:
        warnings.warn(
            "'coin' is deprecated, use 'symbol' instead",
            DeprecationWarning,
            stacklevel=3,
        )
        if symbol is None:
            symbol = kwargs.pop("coin")
        else:
            kwargs.pop("coin")
    return symbol


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

        self.orders = OrdersResource(http, base_path)
        """L4 order history, flow, and TP/SL"""

        self.l4_orderbook = L4OrderBookResource(http, base_path)
        """L4 order-level orderbook data"""

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
        symbol: str,
        *,
        start: Optional[Timestamp] = None,
        end: Optional[Timestamp] = None,
        interval: Optional[str] = None,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
        **kwargs,
    ) -> CursorResponse[list[LiquidationVolume]]:
        """
        Get aggregated liquidation volume for a symbol.

        Args:
            symbol: Symbol (e.g. 'BTC')
            start: Start timestamp (ISO or Unix ms)
            end: End timestamp (ISO or Unix ms)
            interval: Aggregation interval (e.g. '1h', '4h', '1d')
            limit: Max records to return
            cursor: Pagination cursor

        Returns:
            CursorResponse with liquidation volume buckets and next_cursor
        """
        symbol = _resolve_symbol(symbol, kwargs)
        params: dict = {
            "start": self._convert_timestamp(start),
            "end": self._convert_timestamp(end),
            "interval": interval,
            "limit": limit,
            "cursor": cursor,
        }
        data = self._http.get(
            f"/v1/hyperliquid/liquidations/{symbol.upper()}/volume",
            params=params,
        )
        return CursorResponse(
            data=[LiquidationVolume.model_validate(item) for item in data["data"]],
            next_cursor=data.get("meta", {}).get("next_cursor"),
        )

    async def aget_liquidation_volume(
        self,
        symbol: str,
        *,
        start: Optional[Timestamp] = None,
        end: Optional[Timestamp] = None,
        interval: Optional[str] = None,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
        **kwargs,
    ) -> CursorResponse[list[LiquidationVolume]]:
        """Async version of get_liquidation_volume()."""
        symbol = _resolve_symbol(symbol, kwargs)
        params: dict = {
            "start": self._convert_timestamp(start),
            "end": self._convert_timestamp(end),
            "interval": interval,
            "limit": limit,
            "cursor": cursor,
        }
        data = await self._http.aget(
            f"/v1/hyperliquid/liquidations/{symbol.upper()}/volume",
            params=params,
        )
        return CursorResponse(
            data=[LiquidationVolume.model_validate(item) for item in data["data"]],
            next_cursor=data.get("meta", {}).get("next_cursor"),
        )

    def get_freshness(self, symbol: str, **kwargs) -> CoinFreshness:
        """
        Get data freshness for a symbol across all data types.

        Returns how recently each data type (orderbook, trades, funding,
        open interest, liquidations) was updated for the given symbol.

        Args:
            symbol: Symbol (e.g. 'BTC')

        Returns:
            CoinFreshness with per-data-type lag information
        """
        symbol = _resolve_symbol(symbol, kwargs)
        data = self._http.get(f"/v1/hyperliquid/freshness/{symbol.upper()}")
        return CoinFreshness.model_validate(data["data"])

    async def aget_freshness(self, symbol: str, **kwargs) -> CoinFreshness:
        """Async version of get_freshness()."""
        symbol = _resolve_symbol(symbol, kwargs)
        data = await self._http.aget(f"/v1/hyperliquid/freshness/{symbol.upper()}")
        return CoinFreshness.model_validate(data["data"])

    def get_summary(self, symbol: str, **kwargs) -> CoinSummary:
        """
        Get combined market summary for a symbol.

        Returns a single snapshot with price, funding, open interest,
        volume, and liquidation metrics.

        Args:
            symbol: Symbol (e.g. 'BTC')

        Returns:
            CoinSummary with all market metrics
        """
        symbol = _resolve_symbol(symbol, kwargs)
        data = self._http.get(f"/v1/hyperliquid/summary/{symbol.upper()}")
        return CoinSummary.model_validate(data["data"])

    async def aget_summary(self, symbol: str, **kwargs) -> CoinSummary:
        """Async version of get_summary()."""
        symbol = _resolve_symbol(symbol, kwargs)
        data = await self._http.aget(f"/v1/hyperliquid/summary/{symbol.upper()}")
        return CoinSummary.model_validate(data["data"])

    def get_price_history(
        self,
        symbol: str,
        *,
        start: Optional[Timestamp] = None,
        end: Optional[Timestamp] = None,
        interval: Optional[str] = None,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
        **kwargs,
    ) -> CursorResponse[list[PriceSnapshot]]:
        """
        Get mark/oracle price history for a symbol.

        Args:
            symbol: Symbol (e.g. 'BTC')
            start: Start timestamp (ISO or Unix ms)
            end: End timestamp (ISO or Unix ms)
            interval: Aggregation interval (e.g. '1h', '4h', '1d')
            limit: Max records to return
            cursor: Pagination cursor

        Returns:
            CursorResponse with price snapshots and next_cursor
        """
        symbol = _resolve_symbol(symbol, kwargs)
        params: dict = {
            "start": self._convert_timestamp(start),
            "end": self._convert_timestamp(end),
            "interval": interval,
            "limit": limit,
            "cursor": cursor,
        }
        data = self._http.get(
            f"/v1/hyperliquid/prices/{symbol.upper()}",
            params=params,
        )
        return CursorResponse(
            data=[PriceSnapshot.model_validate(item) for item in data["data"]],
            next_cursor=data.get("meta", {}).get("next_cursor"),
        )

    async def aget_price_history(
        self,
        symbol: str,
        *,
        start: Optional[Timestamp] = None,
        end: Optional[Timestamp] = None,
        interval: Optional[str] = None,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
        **kwargs,
    ) -> CursorResponse[list[PriceSnapshot]]:
        """Async version of get_price_history()."""
        symbol = _resolve_symbol(symbol, kwargs)
        params: dict = {
            "start": self._convert_timestamp(start),
            "end": self._convert_timestamp(end),
            "interval": interval,
            "limit": limit,
            "cursor": cursor,
        }
        data = await self._http.aget(
            f"/v1/hyperliquid/prices/{symbol.upper()}",
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

        self.liquidations = LiquidationsResource(http, base_path, coin_transform=coin_transform)
        """Liquidation events"""

        self.orders = OrdersResource(http, base_path, coin_transform=coin_transform)
        """L4 order history, flow, and TP/SL"""

        self.l4_orderbook = L4OrderBookResource(http, base_path, coin_transform=coin_transform)
        """L4 order-level orderbook data"""

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

    def get_freshness(self, symbol: str, **kwargs) -> CoinFreshness:
        """
        Get data freshness for a symbol across all data types.

        Args:
            symbol: Symbol (case-sensitive, e.g. 'km:US500')

        Returns:
            CoinFreshness with per-data-type lag information
        """
        symbol = _resolve_symbol(symbol, kwargs)
        data = self._http.get(f"/v1/hyperliquid/hip3/freshness/{symbol}")
        return CoinFreshness.model_validate(data["data"])

    async def aget_freshness(self, symbol: str, **kwargs) -> CoinFreshness:
        """Async version of get_freshness()."""
        symbol = _resolve_symbol(symbol, kwargs)
        data = await self._http.aget(f"/v1/hyperliquid/hip3/freshness/{symbol}")
        return CoinFreshness.model_validate(data["data"])

    def get_summary(self, symbol: str, **kwargs) -> CoinSummary:
        """
        Get combined market summary for a symbol.

        Args:
            symbol: Symbol (case-sensitive, e.g. 'km:US500')

        Returns:
            CoinSummary with all market metrics
        """
        symbol = _resolve_symbol(symbol, kwargs)
        data = self._http.get(f"/v1/hyperliquid/hip3/summary/{symbol}")
        return CoinSummary.model_validate(data["data"])

    async def aget_summary(self, symbol: str, **kwargs) -> CoinSummary:
        """Async version of get_summary()."""
        symbol = _resolve_symbol(symbol, kwargs)
        data = await self._http.aget(f"/v1/hyperliquid/hip3/summary/{symbol}")
        return CoinSummary.model_validate(data["data"])

    def get_price_history(
        self,
        symbol: str,
        *,
        start: Optional[Timestamp] = None,
        end: Optional[Timestamp] = None,
        interval: Optional[str] = None,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
        **kwargs,
    ) -> CursorResponse[list[PriceSnapshot]]:
        """
        Get mark/oracle price history for a symbol.

        Args:
            symbol: Symbol (case-sensitive, e.g. 'km:US500')
            start: Start timestamp (ISO or Unix ms)
            end: End timestamp (ISO or Unix ms)
            interval: Aggregation interval (e.g. '1h', '4h', '1d')
            limit: Max records to return
            cursor: Pagination cursor

        Returns:
            CursorResponse with price snapshots and next_cursor
        """
        symbol = _resolve_symbol(symbol, kwargs)
        params: dict = {
            "start": self._convert_timestamp(start),
            "end": self._convert_timestamp(end),
            "interval": interval,
            "limit": limit,
            "cursor": cursor,
        }
        data = self._http.get(
            f"/v1/hyperliquid/hip3/prices/{symbol}",
            params=params,
        )
        return CursorResponse(
            data=[PriceSnapshot.model_validate(item) for item in data["data"]],
            next_cursor=data.get("meta", {}).get("next_cursor"),
        )

    async def aget_price_history(
        self,
        symbol: str,
        *,
        start: Optional[Timestamp] = None,
        end: Optional[Timestamp] = None,
        interval: Optional[str] = None,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
        **kwargs,
    ) -> CursorResponse[list[PriceSnapshot]]:
        """Async version of get_price_history()."""
        symbol = _resolve_symbol(symbol, kwargs)
        params: dict = {
            "start": self._convert_timestamp(start),
            "end": self._convert_timestamp(end),
            "interval": interval,
            "limit": limit,
            "cursor": cursor,
        }
        data = await self._http.aget(
            f"/v1/hyperliquid/hip3/prices/{symbol}",
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

        self.l3_orderbook = L3OrderBookResource(http, base_path)
        """L3 individual order-level orderbook data"""

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

    def get_freshness(self, symbol: str, **kwargs) -> CoinFreshness:
        """
        Get data freshness for a symbol across all data types.

        Args:
            symbol: Symbol (e.g. 'BTC')

        Returns:
            CoinFreshness with per-data-type lag information
        """
        symbol = _resolve_symbol(symbol, kwargs)
        data = self._http.get(f"/v1/lighter/freshness/{symbol.upper()}")
        return CoinFreshness.model_validate(data["data"])

    async def aget_freshness(self, symbol: str, **kwargs) -> CoinFreshness:
        """Async version of get_freshness()."""
        symbol = _resolve_symbol(symbol, kwargs)
        data = await self._http.aget(f"/v1/lighter/freshness/{symbol.upper()}")
        return CoinFreshness.model_validate(data["data"])

    def get_summary(self, symbol: str, **kwargs) -> CoinSummary:
        """
        Get combined market summary for a symbol.

        Args:
            symbol: Symbol (e.g. 'BTC')

        Returns:
            CoinSummary with all market metrics
        """
        symbol = _resolve_symbol(symbol, kwargs)
        data = self._http.get(f"/v1/lighter/summary/{symbol.upper()}")
        return CoinSummary.model_validate(data["data"])

    async def aget_summary(self, symbol: str, **kwargs) -> CoinSummary:
        """Async version of get_summary()."""
        symbol = _resolve_symbol(symbol, kwargs)
        data = await self._http.aget(f"/v1/lighter/summary/{symbol.upper()}")
        return CoinSummary.model_validate(data["data"])

    def get_price_history(
        self,
        symbol: str,
        *,
        start: Optional[Timestamp] = None,
        end: Optional[Timestamp] = None,
        interval: Optional[str] = None,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
        **kwargs,
    ) -> CursorResponse[list[PriceSnapshot]]:
        """
        Get mark/oracle price history for a symbol.

        Args:
            symbol: Symbol (e.g. 'BTC')
            start: Start timestamp (ISO or Unix ms)
            end: End timestamp (ISO or Unix ms)
            interval: Aggregation interval (e.g. '1h', '4h', '1d')
            limit: Max records to return
            cursor: Pagination cursor

        Returns:
            CursorResponse with price snapshots and next_cursor
        """
        symbol = _resolve_symbol(symbol, kwargs)
        params: dict = {
            "start": self._convert_timestamp(start),
            "end": self._convert_timestamp(end),
            "interval": interval,
            "limit": limit,
            "cursor": cursor,
        }
        data = self._http.get(
            f"/v1/lighter/prices/{symbol.upper()}",
            params=params,
        )
        return CursorResponse(
            data=[PriceSnapshot.model_validate(item) for item in data["data"]],
            next_cursor=data.get("meta", {}).get("next_cursor"),
        )

    async def aget_price_history(
        self,
        symbol: str,
        *,
        start: Optional[Timestamp] = None,
        end: Optional[Timestamp] = None,
        interval: Optional[str] = None,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
        **kwargs,
    ) -> CursorResponse[list[PriceSnapshot]]:
        """Async version of get_price_history()."""
        symbol = _resolve_symbol(symbol, kwargs)
        params: dict = {
            "start": self._convert_timestamp(start),
            "end": self._convert_timestamp(end),
            "interval": interval,
            "limit": limit,
            "cursor": cursor,
        }
        data = await self._http.aget(
            f"/v1/lighter/prices/{symbol.upper()}",
            params=params,
        )
        return CursorResponse(
            data=[PriceSnapshot.model_validate(item) for item in data["data"]],
            next_cursor=data.get("meta", {}).get("next_cursor"),
        )
