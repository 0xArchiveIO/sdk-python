"""Exchange-specific client classes."""

from __future__ import annotations

import warnings
from datetime import datetime
from typing import Optional
from urllib.parse import quote

from .http import HttpClient
from .resources import (
    OrderBookResource,
    TradesResource,
    InstrumentsResource,
    LighterInstrumentsResource,
    Hip3InstrumentsResource,
    Hip4InstrumentsResource,
    FundingResource,
    OpenInterestResource,
    CandlesResource,
    LiquidationsResource,
    OrdersResource,
    Hip4OutcomesResource,
    L4OrderBookResource,
    L2OrderBookResource,
    L3OrderBookResource,
)
from .types import (
    CoinFreshness,
    CoinSummary,
    CursorResponse,
    DataTypeFreshness,
    Hip4Outcome,
    Hip4OutcomeAggregate,
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

        # Hyperliquid uses hourly S3 backfill (not live ingestion), so the
        # backend does not expose ``/v1/hyperliquid/trades/{symbol}/recent``.
        # Disable ``recent()`` here so callers get a clear SDK-level error
        # instead of a 404 from the API. HIP-3, HIP-4, and Lighter keep it.
        self.trades = TradesResource(http, base_path, allow_recent=False)
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

        self.l2_orderbook = L2OrderBookResource(http, base_path)
        """L2 full-depth orderbook (derived from L4)"""

        self.hip3 = Hip3Client(http)
        """HIP-3 builder-deployed perpetuals (February 2026+)"""

        self.hip4 = Hip4Client(http)
        """HIP-4 outcome markets (May 2026+)"""

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

        self.l2_orderbook = L2OrderBookResource(http, base_path, coin_transform=coin_transform)
        """L2 full-depth orderbook (derived from L4)"""

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


def _hip4_encode(symbol: str) -> str:
    """Normalize a HIP-4 coin symbol for REST paths.

    The backend now accepts the bare numeric form (``/hip4/orderbook/0``) and
    the ``#``-prefixed form (``/hip4/orderbook/%230``) interchangeably. We send
    the bare form because customers kept tripping on the ``%23`` URL-encoding
    requirement, and because the namespace is already ``/v1/hyperliquid/hip4``
    so the ``#`` is redundant.

    Note: WebSocket subscribes still use the raw ``#N`` form in the JSON body —
    only the REST path is normalized here.
    """
    s = symbol.lstrip("#")
    # Numeric (bare or ``#N``) → bare numeric. Anything else (defensive: future
    # non-numeric coin formats) → URL-encode to keep ``#`` safe in path.
    if s.isdigit():
        return s
    return quote(symbol, safe="")


class Hip4Client:
    """
    HIP-4 outcome markets client.

    Access Hyperliquid HIP-4 binary-outcome market data through the 0xarchive API.
    Build+ for metadata/trades/OI; Pro+ for orderbook and L4. Server enforces tiers.

    Coin format: ``#<10*outcome_id + side>`` (e.g. ``#0`` = outcome 0 / Yes,
    ``#1`` = outcome 0 / No). The SDK accepts either the bare numeric form
    (``"0"``, ``0``) or the ``#``-prefixed form (``"#0"``) and sends the bare
    form on the REST path; the backend routes both to the same record. The
    bare form is the recommended primary in examples. WebSocket ``subscribe``
    payloads still use the raw ``#N`` form (passed through as-is in JSON).

    Note: HIP-4 has no funding, no liquidations, no candles by design (fully
    collateralized binary outcomes), and no oracle feed for outcomes.

    Example:
        >>> client = oxarchive.Client(api_key="...")
        >>> outcomes = client.hyperliquid.hip4.outcomes.list()
        >>> # Bare form (recommended):
        >>> orderbook = client.hyperliquid.hip4.orderbook.get("0")
        >>> trades = client.hyperliquid.hip4.trades.recent("0")
        >>> # `#`-prefixed form also works:
        >>> orderbook = client.hyperliquid.hip4.orderbook.get("#0")
    """

    def __init__(self, http: HttpClient):
        self._http = http
        base_path = "/v1/hyperliquid/hip4"

        self.instruments = Hip4InstrumentsResource(http, base_path)
        """HIP-4 per-side instruments (one row per ``#N``)."""

        self.outcomes = Hip4OutcomesResource(http, base_path)
        """HIP-4 outcome-level metadata (one row per outcome_id)."""

        self.orderbook = OrderBookResource(http, base_path, coin_transform=_hip4_encode)
        """L2 order book snapshots (Pro+)."""

        self.trades = TradesResource(http, base_path, coin_transform=_hip4_encode)
        """Trade/fill history (Build+)."""

        self.open_interest = OpenInterestResource(http, base_path, coin_transform=_hip4_encode)
        """Per-side open interest (Build+). For paired/aggregated OI use ``outcomes.get()``."""

        self.orders = OrdersResource(http, base_path, coin_transform=_hip4_encode)
        """L4 order history, flow, and TP/SL (Pro+)."""

        self.l4_orderbook = L4OrderBookResource(http, base_path, coin_transform=_hip4_encode)
        """L4 order-level orderbook data (Pro+)."""

        self.l2_orderbook = L2OrderBookResource(http, base_path, coin_transform=_hip4_encode)
        """L2 full-depth orderbook (derived from L4)."""

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
    # Discovery / metadata flat helpers
    # -----------------------------------------------------------------

    def get_instruments(self) -> list[Hip4Outcome]:
        """List all HIP-4 per-side instruments."""
        return self.instruments.list()

    async def aget_instruments(self) -> list[Hip4Outcome]:
        """Async version of get_instruments()."""
        return await self.instruments.alist()

    def get_instrument(self, symbol: str) -> Hip4Outcome:
        """Get a single per-side instrument by symbol (e.g. '#0')."""
        return self.instruments.get(symbol)

    async def aget_instrument(self, symbol: str) -> Hip4Outcome:
        """Async version of get_instrument()."""
        return await self.instruments.aget(symbol)

    def list_outcomes(
        self,
        *,
        is_settled: Optional[bool] = None,
        slug: Optional[str] = None,
        cursor: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> CursorResponse[list[Hip4OutcomeAggregate]]:
        """List outcome markets. Response excludes ``aggregated_oi``.

        Args:
            is_settled: Filter by settlement state. None returns all.
            slug: Filter by per-outcome OR per-side slug. When matched, the
                response is a list of one (compose with ``is_settled``).
            cursor: Pagination cursor.
            limit: Page size.
        """
        return self.outcomes.list(
            is_settled=is_settled, slug=slug, cursor=cursor, limit=limit
        )

    async def alist_outcomes(
        self,
        *,
        is_settled: Optional[bool] = None,
        slug: Optional[str] = None,
        cursor: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> CursorResponse[list[Hip4OutcomeAggregate]]:
        """Async version of list_outcomes()."""
        return await self.outcomes.alist(
            is_settled=is_settled, slug=slug, cursor=cursor, limit=limit
        )

    def get_outcome(self, outcome_id: int) -> Hip4OutcomeAggregate:
        """Get a single outcome by id. Includes ``aggregated_oi``."""
        return self.outcomes.get(outcome_id)

    async def aget_outcome(self, outcome_id: int) -> Hip4OutcomeAggregate:
        """Async version of get_outcome()."""
        return await self.outcomes.aget(outcome_id)

    def get_outcome_by_slug(self, slug: str) -> Hip4OutcomeAggregate:
        """Look up an outcome by its synthesized slug.

        Accepts the per-outcome slug (``btc-above-78213-may-04-0600``) or a
        per-side slug (``btc-above-78213-yes-may-04-0600``). Returns
        :class:`Hip4OutcomeAggregate` with ``aggregated_oi`` populated.
        """
        return self.outcomes.get_by_slug(slug)

    async def aget_outcome_by_slug(self, slug: str) -> Hip4OutcomeAggregate:
        """Async version of get_outcome_by_slug()."""
        return await self.outcomes.aget_by_slug(slug)

    # -----------------------------------------------------------------
    # Market-data flat helpers (mirror HIP-3 surface)
    # -----------------------------------------------------------------

    def get_orderbook(self, symbol: str, **kwargs):
        """Get current L2 orderbook snapshot for a HIP-4 symbol (e.g. '#0')."""
        return self.orderbook.get(symbol, **kwargs)

    async def aget_orderbook(self, symbol: str, **kwargs):
        """Async version of get_orderbook()."""
        return await self.orderbook.aget(symbol, **kwargs)

    def get_orderbook_history(self, symbol: str, **kwargs):
        """Get L2 orderbook history (Pro+)."""
        return self.orderbook.history(symbol, **kwargs)

    async def aget_orderbook_history(self, symbol: str, **kwargs):
        """Async version of get_orderbook_history()."""
        return await self.orderbook.ahistory(symbol, **kwargs)

    def get_trades(self, symbol: str, **kwargs):
        """Get full trade/fill history with cursor pagination (Build+)."""
        return self.trades.list(symbol, **kwargs)

    async def aget_trades(self, symbol: str, **kwargs):
        """Async version of get_trades()."""
        return await self.trades.alist(symbol, **kwargs)

    def get_trades_recent(self, symbol: str, limit: Optional[int] = None, **kwargs):
        """Get most recent trades (latest first)."""
        return self.trades.recent(symbol, limit=limit, **kwargs)

    async def aget_trades_recent(self, symbol: str, limit: Optional[int] = None, **kwargs):
        """Async version of get_trades_recent()."""
        return await self.trades.arecent(symbol, limit=limit, **kwargs)

    def get_open_interest(self, symbol: str, **kwargs):
        """Get per-side OI history (Build+). Use get_outcome() for paired aggregates."""
        return self.open_interest.history(symbol, **kwargs)

    async def aget_open_interest(self, symbol: str, **kwargs):
        """Async version of get_open_interest()."""
        return await self.open_interest.ahistory(symbol, **kwargs)

    def get_open_interest_current(self, symbol: str, **kwargs):
        """Get latest per-side OI snapshot."""
        return self.open_interest.current(symbol, **kwargs)

    async def aget_open_interest_current(self, symbol: str, **kwargs):
        """Async version of get_open_interest_current()."""
        return await self.open_interest.acurrent(symbol, **kwargs)

    def get_freshness(self, symbol: str) -> CoinFreshness:
        """Get data freshness for a HIP-4 symbol across data types."""
        encoded = _hip4_encode(symbol)
        data = self._http.get(f"/v1/hyperliquid/hip4/freshness/{encoded}")
        return CoinFreshness.model_validate(data["data"])

    async def aget_freshness(self, symbol: str) -> CoinFreshness:
        """Async version of get_freshness()."""
        encoded = _hip4_encode(symbol)
        data = await self._http.aget(f"/v1/hyperliquid/hip4/freshness/{encoded}")
        return CoinFreshness.model_validate(data["data"])

    def get_summary(self, symbol: str) -> CoinSummary:
        """Get 24h market summary for a HIP-4 symbol.

        Note: ``mark_price`` on the response is an implied probability in [0, 1]
        for HIP-4, not a USD price. Field name mirrors upstream Hyperliquid.
        """
        encoded = _hip4_encode(symbol)
        data = self._http.get(f"/v1/hyperliquid/hip4/summary/{encoded}")
        return CoinSummary.model_validate(data["data"])

    async def aget_summary(self, symbol: str) -> CoinSummary:
        """Async version of get_summary()."""
        encoded = _hip4_encode(symbol)
        data = await self._http.aget(f"/v1/hyperliquid/hip4/summary/{encoded}")
        return CoinSummary.model_validate(data["data"])

    def get_prices(
        self,
        symbol: str,
        *,
        start: Optional[Timestamp] = None,
        end: Optional[Timestamp] = None,
        interval: Optional[str] = None,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
    ) -> CursorResponse[list[PriceSnapshot]]:
        """Get mid-price history for a HIP-4 symbol.

        Note: ``mark_price``/``mid_price`` on the response are implied
        probabilities in [0, 1], not USD prices.
        """
        encoded = _hip4_encode(symbol)
        params = {
            "start": self._convert_timestamp(start),
            "end": self._convert_timestamp(end),
            "interval": interval,
            "limit": limit,
            "cursor": cursor,
        }
        data = self._http.get(f"/v1/hyperliquid/hip4/prices/{encoded}", params=params)
        return CursorResponse(
            data=[PriceSnapshot.model_validate(item) for item in data["data"]],
            next_cursor=data.get("meta", {}).get("next_cursor"),
        )

    async def aget_prices(
        self,
        symbol: str,
        *,
        start: Optional[Timestamp] = None,
        end: Optional[Timestamp] = None,
        interval: Optional[str] = None,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
    ) -> CursorResponse[list[PriceSnapshot]]:
        """Async version of get_prices()."""
        encoded = _hip4_encode(symbol)
        params = {
            "start": self._convert_timestamp(start),
            "end": self._convert_timestamp(end),
            "interval": interval,
            "limit": limit,
            "cursor": cursor,
        }
        data = await self._http.aget(f"/v1/hyperliquid/hip4/prices/{encoded}", params=params)
        return CursorResponse(
            data=[PriceSnapshot.model_validate(item) for item in data["data"]],
            next_cursor=data.get("meta", {}).get("next_cursor"),
        )

    def get_order_history(self, symbol: str, **kwargs):
        """Get order lifecycle history (Pro+)."""
        return self.orders.history(symbol, **kwargs)

    async def aget_order_history(self, symbol: str, **kwargs):
        """Async version of get_order_history()."""
        return await self.orders.ahistory(symbol, **kwargs)

    def get_order_flow(self, symbol: str, **kwargs):
        """Get time-bucketed order-flow aggregates (Pro+)."""
        return self.orders.flow(symbol, **kwargs)

    async def aget_order_flow(self, symbol: str, **kwargs):
        """Async version of get_order_flow()."""
        return await self.orders.aflow(symbol, **kwargs)

    def get_tpsl(self, symbol: str, **kwargs):
        """Get TP/SL orders (Pro+)."""
        return self.orders.tpsl(symbol, **kwargs)

    async def aget_tpsl(self, symbol: str, **kwargs):
        """Async version of get_tpsl()."""
        return await self.orders.atpsl(symbol, **kwargs)

    def get_l4_orderbook(self, symbol: str, **kwargs):
        """Get full L4 reconstruction (current) (Pro+)."""
        return self.l4_orderbook.get(symbol, **kwargs)

    async def aget_l4_orderbook(self, symbol: str, **kwargs):
        """Async version of get_l4_orderbook()."""
        return await self.l4_orderbook.aget(symbol, **kwargs)

    def get_l4_diffs(self, symbol: str, **kwargs):
        """Get L4 diffs (event stream) with cursor pagination (Pro+)."""
        return self.l4_orderbook.diffs(symbol, **kwargs)

    async def aget_l4_diffs(self, symbol: str, **kwargs):
        """Async version of get_l4_diffs()."""
        return await self.l4_orderbook.adiffs(symbol, **kwargs)

    def get_l4_history(self, symbol: str, **kwargs):
        """Get L4 checkpoint history (Build+, hard cap limit=10)."""
        return self.l4_orderbook.history(symbol, **kwargs)

    async def aget_l4_history(self, symbol: str, **kwargs):
        """Async version of get_l4_history()."""
        return await self.l4_orderbook.ahistory(symbol, **kwargs)


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
