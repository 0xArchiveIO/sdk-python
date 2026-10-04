"""Trades API resource."""

from __future__ import annotations

from typing import Literal, Optional, Union

from .._time import to_unix_ms
from ..http import HttpClient
from ..types import CursorResponse, OxArchiveError, ResponseMeta, Timestamp, Trade

TradeSide = Literal["buy", "sell"]
"""Trade side filter: ``"buy"`` keeps rows with ``side == "B"``, ``"sell"`` keeps
rows with ``side == "A"``."""


class TradesResource:
    """
    Trades API resource.

    ``history()`` pages the trade tape of a window (``list()`` is the same
    method under its earlier name); ``recent()`` returns the latest trades.
    Both take ``side="buy"`` or ``side="sell"``, which the API applies before
    paging, so a full page holds ``limit`` matching trades.

    Example:
        >>> # Get the last hour of trades with cursor-based pagination (recommended)
        >>> end = datetime.now(timezone.utc)
        >>> start = end - timedelta(hours=1)
        >>> result = client.hyperliquid.trades.history("BTC", start=start, end=end)
        >>> trades = result.data
        >>>
        >>> # Get all pages
        >>> while result.has_more:
        ...     result = client.hyperliquid.trades.history(
        ...         "BTC", start=start, end=end, cursor=result.next_cursor
        ...     )
        ...     trades.extend(result.data)
        >>>
        >>> # Only buys
        >>> buys = client.hyperliquid.trades.history("BTC", start=..., end=..., side="buy")
        >>>
        >>> # Get recent trades (HIP-3, HIP-4, spot and Lighter)
        >>> recent = client.lighter.trades.recent("BTC")
    """

    def __init__(
        self,
        http: HttpClient,
        base_path: str = "/v1",
        coin_transform=str.upper,
        *,
        allow_recent: bool = True,
    ):
        self._http = http
        self._base_path = base_path
        self._coin_transform = coin_transform
        # Hyperliquid has hourly fills backfill, not real-time, so the backend
        # does not expose ``/trades/{symbol}/recent`` for the bare Hyperliquid
        # namespace. Setting ``allow_recent=False`` makes the SDK fail fast
        # with a clear pointer instead of letting the user 404 against the API.
        self._allow_recent = allow_recent

    _convert_timestamp = staticmethod(to_unix_ms)

    @staticmethod
    def _cursor(cursor: Optional[Timestamp]) -> Optional[Union[str, int]]:
        """The ``cursor`` query value.

        A trades cursor is opaque: a string such as ``"1790640000578_218303497631402"``
        (Hyperliquid, HIP-3, HIP-4 and spot) or ``"1790540000288_32247366750_1"``
        (Lighter), sent back exactly as the API returned it. A string or an
        integer is passed through unchanged; only a datetime is converted.
        """
        if cursor is None or isinstance(cursor, (str, int)):
            return cursor
        return to_unix_ms(cursor, "cursor")

    def list(
        self,
        symbol: str,
        *,
        start: Timestamp,
        end: Timestamp,
        cursor: Optional[Timestamp] = None,
        limit: Optional[int] = None,
        side: Optional[TradeSide] = None,
        **kwargs,
    ) -> CursorResponse[list[Trade]]:
        """
        Get trade history for a symbol using cursor-based pagination.

        Also available as :meth:`history`. While ``has_more`` is true, pass
        ``next_cursor`` back as ``cursor`` with the other arguments unchanged.

        Args:
            symbol: The symbol (e.g., 'BTC', 'ETH')
            start: Start timestamp (required)
            end: End timestamp (required)
            cursor: The previous response's next_cursor, passed back unchanged
            limit: Maximum number of results (default: 100, max: 1000)
            side: ``"buy"`` or ``"sell"`` to keep only that side (``side ==
                "B"`` or ``"A"``). The API filters before paging, and the
                cursor pages the filtered tape.

        Returns:
            CursorResponse with trades and next_cursor for pagination. On
            Lighter (mainnet and Robinhood Chain), ``meta.finalized_through`` is
            the canonical boundary: ``end`` is clamped to it, and
            ``meta.requested_end`` / ``meta.clamped_to`` are set when it was.

        Example:
            >>> # First page
            >>> result = client.trades.list("BTC", start=start, end=end, limit=1000)
            >>> trades = result.data
            >>>
            >>> # Subsequent pages
            >>> while result.has_more:
            ...     result = client.trades.list(
            ...         "BTC", start=start, end=end, cursor=result.next_cursor, limit=1000
            ...     )
            ...     trades.extend(result.data)
        """
        symbol = self._resolve_symbol(symbol, kwargs)
        data = self._http.get(
            f"{self._base_path}/trades/{self._coin_transform(symbol)}",
            params={
                "start": self._convert_timestamp(start),
                "end": self._convert_timestamp(end),
                "cursor": self._cursor(cursor),
                "limit": limit,
                "side": side,
            },
        )
        return CursorResponse(
            data=[Trade.model_validate(item) for item in data["data"]],
            next_cursor=data.get("meta", {}).get("next_cursor"),
            meta=ResponseMeta.model_validate(data.get("meta") or {}),
        )

    async def alist(
        self,
        symbol: str,
        *,
        start: Timestamp,
        end: Timestamp,
        cursor: Optional[Timestamp] = None,
        limit: Optional[int] = None,
        side: Optional[TradeSide] = None,
        **kwargs,
    ) -> CursorResponse[list[Trade]]:
        """
        Async version of list() (also available as :meth:`ahistory`).
        """
        symbol = self._resolve_symbol(symbol, kwargs)
        data = await self._http.aget(
            f"{self._base_path}/trades/{self._coin_transform(symbol)}",
            params={
                "start": self._convert_timestamp(start),
                "end": self._convert_timestamp(end),
                "cursor": self._cursor(cursor),
                "limit": limit,
                "side": side,
            },
        )
        return CursorResponse(
            data=[Trade.model_validate(item) for item in data["data"]],
            next_cursor=data.get("meta", {}).get("next_cursor"),
            meta=ResponseMeta.model_validate(data.get("meta") or {}),
        )

    history = list
    """Trade history for a window, one page at a time: the same method as
    :meth:`list`, under the name every paged series uses."""

    ahistory = alist
    """Async version of :meth:`history` (the same method as :meth:`alist`)."""

    def recent(
        self,
        symbol: str,
        limit: Optional[int] = None,
        *,
        side: Optional[TradeSide] = None,
        **kwargs,
    ) -> list[Trade]:
        """
        Get most recent trades for a symbol.

        Note: This method is available for HIP-3
        (``client.hyperliquid.hip3.trades.recent()``), HIP-4
        (``client.hyperliquid.hip4.trades.recent()``), Hyperliquid spot
        (``client.spot.trades.recent()``) and Lighter
        (``client.lighter.trades.recent()`` and
        ``client.rh_lighter.trades.recent()``, the preliminary tier). The API
        does not serve it for Hyperliquid core, so
        ``client.hyperliquid.trades.recent()`` raises :class:`OxArchiveError`
        with ``error_code == "unsupported_for_venue"`` before sending; use
        ``client.hyperliquid.trades.history()`` there.

        Args:
            symbol: The symbol (e.g., 'BTC', 'ETH')
            limit: Number of trades to return (default: 100)
            side: ``"buy"`` or ``"sell"`` to keep only that side.

        Returns:
            List of recent trades. The response meta is not returned: on
            Lighter, use ``trades.list()`` for ``meta.finalized_through``.
        """
        if not self._allow_recent:
            raise OxArchiveError(
                "trades.recent() is not offered for Hyperliquid core. Use "
                "client.hyperliquid.trades.history(symbol, start=..., end=...) "
                "for trade history, or recent() on "
                "client.hyperliquid.hip3.trades, client.hyperliquid.hip4.trades, "
                "client.spot.trades, client.lighter.trades or "
                "client.rh_lighter.trades.",
                404,
                error_code="unsupported_for_venue",
            )
        symbol = self._resolve_symbol(symbol, kwargs)
        data = self._http.get(
            f"{self._base_path}/trades/{self._coin_transform(symbol)}/recent",
            params={"limit": limit, "side": side},
        )
        return [Trade.model_validate(item) for item in data["data"]]

    async def arecent(
        self,
        symbol: str,
        limit: Optional[int] = None,
        *,
        side: Optional[TradeSide] = None,
        **kwargs,
    ) -> list[Trade]:
        """Async version of recent()."""
        if not self._allow_recent:
            raise OxArchiveError(
                "trades.arecent() is not offered for Hyperliquid core. Use "
                "client.hyperliquid.trades.ahistory(symbol, start=..., end=...) "
                "for trade history, or arecent() on "
                "client.hyperliquid.hip3.trades, client.hyperliquid.hip4.trades, "
                "client.spot.trades, client.lighter.trades or "
                "client.rh_lighter.trades.",
                404,
                error_code="unsupported_for_venue",
            )
        symbol = self._resolve_symbol(symbol, kwargs)
        data = await self._http.aget(
            f"{self._base_path}/trades/{self._coin_transform(symbol)}/recent",
            params={"limit": limit, "side": side},
        )
        return [Trade.model_validate(item) for item in data["data"]]

    @staticmethod
    def _resolve_symbol(symbol, kwargs):
        import warnings

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
