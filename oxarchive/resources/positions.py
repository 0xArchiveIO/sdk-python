"""Account positions API resources.

Account positions are served for Hyperliquid core, HIP-3, Lighter and Lighter
on Robinhood Chain:

- ``client.hyperliquid.positions`` and ``client.hyperliquid.hip3.positions``
  key accounts by 0x wallet address.
- ``client.lighter.positions`` and ``client.rh_lighter.positions`` key
  accounts by integer Lighter account index. ``client.lighter.accounts``
  resolves an L1 address to its account indices (Lighter mainnet only).

Every method returns a :class:`~oxarchive.types.CursorResponse` whose ``meta``
carries the snapshot context (``as_of``, ``snapshot_ts``, ``source``,
``quality``, ``stale``, ``built_through``, ``finalized_through``, ``totals``).
Paginated routes return ``next_cursor``; pass it back as ``cursor`` with the
other arguments unchanged, or use the ``iterate_*`` helpers, which do that for
you. A cursor is bound to the request that produced it: changing any other
argument, or a snapshot that has since been replaced, is refused (HTTP 400 or
409). Restart without a cursor in that case.

Position rows are billed like trades, 1,000 rows per credit. The account
summary routes and the Lighter L1 resolver are billed at the per-request
minimum.
"""

from __future__ import annotations

from datetime import datetime
from typing import (
    Any,
    AsyncIterator,
    Callable,
    Iterator,
    Literal,
    Optional,
    TypeVar,
    Union,
)
from urllib.parse import quote

from ..http import HttpClient
from ..types import (
    AccountSummary,
    CursorResponse,
    LighterL1Account,
    LighterL1Accounts,
    MarketPosition,
    MarketPositionsSummary,
    Position,
    PositionChange,
    ResponseMeta,
    Timestamp,
    WalletPositions,
)

D = TypeVar("D")
R = TypeVar("R")

PositionSide = Literal["long", "short"]
"""Side filter for the market routes."""

HOUR_MS = 3_600_000

Params = dict[str, Any]


def _to_ms(ts: Optional[Timestamp]) -> Optional[int]:
    """Convert a timestamp (Unix ms, ISO string or datetime) to Unix milliseconds."""
    if ts is None:
        return None
    if isinstance(ts, bool):
        raise ValueError("timestamps must be Unix milliseconds, ISO strings or datetimes")
    if isinstance(ts, int):
        return ts
    if isinstance(ts, datetime):
        return int(ts.timestamp() * 1000)
    if isinstance(ts, str):
        try:
            parsed = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            return int(parsed.timestamp() * 1000)
        except ValueError:
            return int(ts)
    raise ValueError("timestamps must be Unix milliseconds, ISO strings or datetimes")


def _hour_ms(hour: Timestamp) -> int:
    """An exact UTC hour in Unix milliseconds, or ``ValueError``."""
    ms = _to_ms(hour)
    if ms is None or ms < 0 or ms % HOUR_MS != 0:
        raise ValueError("hour must be an exact UTC hour (for example 2026-09-25T12:00:00Z)")
    return ms


def _page(payload: dict[str, Any], parse: Callable[[Any], D]) -> CursorResponse[D]:
    meta = ResponseMeta.model_validate(payload.get("meta") or {})
    return CursorResponse(data=parse(payload["data"]), next_cursor=meta.next_cursor, meta=meta)


def _list_of(model: Any) -> Callable[[Any], list[Any]]:
    def parse(data: Any) -> list[Any]:
        return [model.model_validate(item) for item in data]

    return parse


_positions = _list_of(Position)
_changes = _list_of(PositionChange)
_market_rows = _list_of(MarketPosition)
_summaries = _list_of(MarketPositionsSummary)
_accounts = _list_of(AccountSummary)


def _wallet(data: Any) -> WalletPositions:
    return WalletPositions.model_validate(data)


def _l1_accounts(data: Any) -> LighterL1Accounts:
    return LighterL1Accounts.model_validate(data)


class _Endpoint:
    """One GET request: path, query and how to parse ``data``."""

    __slots__ = ("path", "params", "parse")

    def __init__(self, path: str, params: Params, parse: Callable[[Any], Any]) -> None:
        self.path = path
        self.params = params
        self.parse = parse


class _PositionsBase:
    def __init__(
        self,
        http: HttpClient,
        base_path: str,
        coin_transform: Callable[[str], str],
    ) -> None:
        self._http = http
        self._base_path = base_path
        self._coin_transform = coin_transform

    def _symbol_path(self, symbol: str) -> str:
        return quote(self._coin_transform(symbol), safe="")

    def _symbol_param(self, symbol: Optional[str]) -> Optional[str]:
        return None if symbol is None else self._coin_transform(symbol)

    # ---- transport -------------------------------------------------------

    def _fetch(self, ep: _Endpoint) -> CursorResponse[Any]:
        return _page(self._http.get(ep.path, params=dict(ep.params)), ep.parse)

    async def _afetch(self, ep: _Endpoint) -> CursorResponse[Any]:
        return _page(await self._http.aget(ep.path, params=dict(ep.params)), ep.parse)

    def _iterate(self, ep: _Endpoint, rows: Callable[[Any], list[R]]) -> Iterator[R]:
        params = dict(ep.params)
        while True:
            page = self._fetch(_Endpoint(ep.path, params, ep.parse))
            yield from rows(page.data)
            if not page.next_cursor:
                return
            params["cursor"] = page.next_cursor

    async def _aiterate(self, ep: _Endpoint, rows: Callable[[Any], list[R]]) -> AsyncIterator[R]:
        params = dict(ep.params)
        while True:
            page = await self._afetch(_Endpoint(ep.path, params, ep.parse))
            for row in rows(page.data):
                yield row
            if not page.next_cursor:
                return
            params["cursor"] = page.next_cursor

    # ---- market routes (shared by every venue) ---------------------------

    def _market_ep(
        self,
        symbol: str,
        hour: Optional[Timestamp],
        side: Optional[PositionSide],
        min_value: Optional[float],
        include_system: Optional[bool],
        cursor: Optional[str],
        limit: Optional[int],
    ) -> _Endpoint:
        return _Endpoint(
            f"{self._base_path}/positions/{self._symbol_path(symbol)}",
            {
                "hour": None if hour is None else _hour_ms(hour),
                "side": side,
                "min_value": min_value,
                "include_system": include_system,
                "cursor": cursor,
                "limit": limit,
            },
            _market_rows,
        )

    def _summary_ep(
        self,
        symbol: str,
        start: Optional[Timestamp],
        end: Optional[Timestamp],
        include_system: Optional[bool],
        cursor: Optional[str],
        limit: Optional[int],
    ) -> _Endpoint:
        return _Endpoint(
            f"{self._base_path}/positions/{self._symbol_path(symbol)}/summary",
            {
                "start": _to_ms(start),
                "end": _to_ms(end),
                "include_system": include_system,
                "cursor": cursor,
                "limit": limit,
            },
            _summaries,
        )

    def _bulk_ep(
        self,
        hour: Timestamp,
        include_system: Optional[bool],
        cursor: Optional[str],
        limit: Optional[int],
    ) -> _Endpoint:
        return _Endpoint(
            f"{self._base_path}/positions",
            {
                "hour": _hour_ms(hour),
                "include_system": include_system,
                "cursor": cursor,
                "limit": limit,
            },
            _market_rows,
        )


def _identity(symbol: str) -> str:
    return symbol


def _upper(symbol: str) -> str:
    return symbol.upper()


class HyperliquidPositionsResource(_PositionsBase):
    """Account positions for Hyperliquid core or HIP-3.

    Available as ``client.hyperliquid.positions`` (core) and
    ``client.hyperliquid.hip3.positions`` (HIP-3, where ``dex`` narrows a wallet
    to one dex). Accounts are 0x wallet addresses.

    Coverage: the change log starts 2025-05-25 on core and 2025-10-13 on HIP-3,
    hourly history starts 2026-06-07, and the live snapshot refreshes every
    5 minutes.

    Example:
        >>> now = client.hyperliquid.positions.get("0xabc...")
        >>> for p in now.data.positions:
        ...     print(p.symbol, p.side, p.size, p.unrealized_pnl)
        >>> print(now.meta.as_of, now.meta.quality)
        >>>
        >>> # State at an instant (an exact hour serves the hourly snapshot)
        >>> then = client.hyperliquid.positions.get("0xabc...", timestamp="2026-09-01T12:00:00Z")
        >>>
        >>> # Every change in a window, following cursors
        >>> for leg in client.hyperliquid.positions.iterate_changes(
        ...     "0xabc...", start="2026-09-01", end="2026-09-02"
        ... ):
        ...     print(leg.timestamp, leg.event_type, leg.start_position, leg.end_position)
    """

    def __init__(self, http: HttpClient, base_path: str = "/v1/hyperliquid", *, hip3: bool = False):
        super().__init__(http, base_path, _identity if hip3 else _upper)
        self._hip3 = hip3

    def _dex(self, dex: Optional[str]) -> Optional[str]:
        if dex is not None and not self._hip3:
            raise ValueError(
                "dex applies to HIP-3 positions only (client.hyperliquid.hip3.positions)"
            )
        return dex

    def _wallet_path(self, address: str, suffix: str) -> str:
        return f"{self._base_path}/wallets/{quote(address, safe='')}/{suffix}"

    # ---- endpoint specs --------------------------------------------------

    def _get_ep(
        self,
        address: str,
        timestamp: Optional[Timestamp],
        symbol: Optional[str],
        dex: Optional[str],
        cursor: Optional[str],
        limit: Optional[int],
    ) -> _Endpoint:
        return _Endpoint(
            self._wallet_path(address, "positions"),
            {
                "timestamp": _to_ms(timestamp),
                "symbol": self._symbol_param(symbol),
                "dex": self._dex(dex),
                "cursor": cursor,
                "limit": limit,
            },
            _wallet,
        )

    def _range_ep(
        self,
        address: str,
        suffix: str,
        start: Timestamp,
        end: Timestamp,
        symbol: Optional[str],
        dex: Optional[str],
        cursor: Optional[str],
        limit: Optional[int],
        parse: Callable[[Any], Any],
    ) -> _Endpoint:
        return _Endpoint(
            self._wallet_path(address, suffix),
            {
                "start": _to_ms(start),
                "end": _to_ms(end),
                "symbol": self._symbol_param(symbol),
                "dex": self._dex(dex),
                "cursor": cursor,
                "limit": limit,
            },
            parse,
        )

    # ---- wallet: current or as-of ----------------------------------------

    def get(
        self,
        address: str,
        *,
        timestamp: Optional[Timestamp] = None,
        symbol: Optional[str] = None,
        dex: Optional[str] = None,
        cursor: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> CursorResponse[WalletPositions]:
        """Open positions of a wallet, now or at an instant.

        Without ``timestamp``: the latest live snapshot (``meta.stale`` is
        ``True`` with a ``meta.notice`` when it is older than 12 minutes).

        With ``timestamp``: the state after every event before that instant.
        An exact UTC hour with a committed hourly snapshot serves that snapshot
        (``meta.source == "snapshot"``); any other instant is reconstructed
        (``meta.source == "reconstructed"``: size, entry and ``opened_at`` are
        exact, mark fields are at the instant, snapshot-only fields are
        ``None``). The instant is clamped to ``meta.built_through``
        (``meta.clamped_to`` says when it was). An instant before coverage
        returns no positions with ``account_seen == "outside_coverage"``.

        Args:
            address: 0x wallet address.
            timestamp: As-of instant; omit for the latest live snapshot.
            symbol: Only this market.
            dex: HIP-3 only: only this dex. On HIP-3, the account summary is
                included only when ``dex`` (or a ``symbol``) names one dex.
            cursor: ``next_cursor`` of the previous page.
            limit: Rows per page (default 500, max 5,000).

        Returns:
            ``CursorResponse`` whose ``data`` is :class:`WalletPositions`
            (``positions``, ``account``, ``account_seen``).
        """
        return self._fetch(self._get_ep(address, timestamp, symbol, dex, cursor, limit))

    async def aget(
        self,
        address: str,
        *,
        timestamp: Optional[Timestamp] = None,
        symbol: Optional[str] = None,
        dex: Optional[str] = None,
        cursor: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> CursorResponse[WalletPositions]:
        """Async version of :meth:`get`."""
        return await self._afetch(self._get_ep(address, timestamp, symbol, dex, cursor, limit))

    # ---- wallet: hourly history ------------------------------------------

    def history(
        self,
        address: str,
        *,
        start: Timestamp,
        end: Timestamp,
        symbol: Optional[str] = None,
        dex: Optional[str] = None,
        cursor: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> CursorResponse[list[Position]]:
        """Hourly position rows of a wallet in ``[start, end)``.

        Each row carries ``snapshot_ts``, the hour it describes. Hourly
        history starts 2026-06-07.

        Args:
            address: 0x wallet address.
            start: Inclusive start.
            end: Exclusive end.
            symbol: Only this market.
            dex: HIP-3 only: only this dex.
            cursor: ``next_cursor`` of the previous page.
            limit: Rows per page (default 500, max 5,000).
        """
        return self._fetch(
            self._range_ep(
                address, "positions/history", start, end, symbol, dex, cursor, limit, _positions
            )
        )

    async def ahistory(
        self,
        address: str,
        *,
        start: Timestamp,
        end: Timestamp,
        symbol: Optional[str] = None,
        dex: Optional[str] = None,
        cursor: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> CursorResponse[list[Position]]:
        """Async version of :meth:`history`."""
        return await self._afetch(
            self._range_ep(
                address, "positions/history", start, end, symbol, dex, cursor, limit, _positions
            )
        )

    def iterate_history(
        self,
        address: str,
        *,
        start: Timestamp,
        end: Timestamp,
        symbol: Optional[str] = None,
        dex: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> Iterator[Position]:
        """Yield every hourly position row of :meth:`history`, following cursors."""
        return self._iterate(
            self._range_ep(
                address, "positions/history", start, end, symbol, dex, None, limit, _positions
            ),
            _positions_rows,
        )

    def aiterate_history(
        self,
        address: str,
        *,
        start: Timestamp,
        end: Timestamp,
        symbol: Optional[str] = None,
        dex: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> AsyncIterator[Position]:
        """Async version of :meth:`iterate_history`."""
        return self._aiterate(
            self._range_ep(
                address, "positions/history", start, end, symbol, dex, None, limit, _positions
            ),
            _positions_rows,
        )

    # ---- wallet: change log ----------------------------------------------

    def changes(
        self,
        address: str,
        *,
        start: Timestamp,
        end: Timestamp,
        symbol: Optional[str] = None,
        dex: Optional[str] = None,
        cursor: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> CursorResponse[list[PositionChange]]:
        """Position change-log legs of a wallet in ``[start, end)``.

        ``end`` is clamped to ``meta.built_through``. Legs before
        ``meta.finalized_through`` are final; later legs carry
        ``finalized == False``. The change log starts 2025-05-25 on core and
        2025-10-13 on HIP-3.

        Args:
            address: 0x wallet address.
            start: Inclusive start.
            end: Exclusive end.
            symbol: Only this market.
            dex: HIP-3 only: only this dex.
            cursor: ``next_cursor`` of the previous page.
            limit: Rows per page (default 500, max 5,000).
        """
        return self._fetch(
            self._range_ep(
                address, "positions/changes", start, end, symbol, dex, cursor, limit, _changes
            )
        )

    async def achanges(
        self,
        address: str,
        *,
        start: Timestamp,
        end: Timestamp,
        symbol: Optional[str] = None,
        dex: Optional[str] = None,
        cursor: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> CursorResponse[list[PositionChange]]:
        """Async version of :meth:`changes`."""
        return await self._afetch(
            self._range_ep(
                address, "positions/changes", start, end, symbol, dex, cursor, limit, _changes
            )
        )

    def iterate_changes(
        self,
        address: str,
        *,
        start: Timestamp,
        end: Timestamp,
        symbol: Optional[str] = None,
        dex: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> Iterator[PositionChange]:
        """Yield every change-log leg of :meth:`changes`, following cursors."""
        return self._iterate(
            self._range_ep(
                address, "positions/changes", start, end, symbol, dex, None, limit, _changes
            ),
            _change_rows,
        )

    def aiterate_changes(
        self,
        address: str,
        *,
        start: Timestamp,
        end: Timestamp,
        symbol: Optional[str] = None,
        dex: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> AsyncIterator[PositionChange]:
        """Async version of :meth:`iterate_changes`."""
        return self._aiterate(
            self._range_ep(
                address, "positions/changes", start, end, symbol, dex, None, limit, _changes
            ),
            _change_rows,
        )

    # ---- wallet: account summary -----------------------------------------

    def account(
        self, address: str, *, dex: Optional[str] = None
    ) -> CursorResponse[list[AccountSummary]]:
        """Account summary of a wallet at the latest live snapshot.

        One row on Hyperliquid core; one row per dex on HIP-3 (or just ``dex``).
        Billed at the per-request minimum.
        """
        return self._fetch(
            _Endpoint(self._wallet_path(address, "account"), {"dex": self._dex(dex)}, _accounts)
        )

    async def aaccount(
        self, address: str, *, dex: Optional[str] = None
    ) -> CursorResponse[list[AccountSummary]]:
        """Async version of :meth:`account`."""
        return await self._afetch(
            _Endpoint(self._wallet_path(address, "account"), {"dex": self._dex(dex)}, _accounts)
        )

    def account_history(
        self,
        address: str,
        *,
        start: Timestamp,
        end: Timestamp,
        dex: Optional[str] = None,
        cursor: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> CursorResponse[list[AccountSummary]]:
        """Hourly account summaries of a wallet in ``[start, end)``.

        Billed at the per-request minimum.

        Args:
            address: 0x wallet address.
            start: Inclusive start.
            end: Exclusive end.
            dex: HIP-3 only: only this dex.
            cursor: ``next_cursor`` of the previous page.
            limit: Rows per page (default 500, max 5,000).
        """
        return self._fetch(
            self._range_ep(
                address, "account/history", start, end, None, dex, cursor, limit, _accounts
            )
        )

    async def aaccount_history(
        self,
        address: str,
        *,
        start: Timestamp,
        end: Timestamp,
        dex: Optional[str] = None,
        cursor: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> CursorResponse[list[AccountSummary]]:
        """Async version of :meth:`account_history`."""
        return await self._afetch(
            self._range_ep(
                address, "account/history", start, end, None, dex, cursor, limit, _accounts
            )
        )

    def iterate_account_history(
        self,
        address: str,
        *,
        start: Timestamp,
        end: Timestamp,
        dex: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> Iterator[AccountSummary]:
        """Yield every hourly account summary of :meth:`account_history`, following cursors."""
        return self._iterate(
            self._range_ep(
                address, "account/history", start, end, None, dex, None, limit, _accounts
            ),
            _account_rows,
        )

    def aiterate_account_history(
        self,
        address: str,
        *,
        start: Timestamp,
        end: Timestamp,
        dex: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> AsyncIterator[AccountSummary]:
        """Async version of :meth:`iterate_account_history`."""
        return self._aiterate(
            self._range_ep(
                address, "account/history", start, end, None, dex, None, limit, _accounts
            ),
            _account_rows,
        )

    # ---- market routes ---------------------------------------------------

    def market(
        self,
        symbol: str,
        *,
        hour: Optional[Timestamp] = None,
        side: Optional[PositionSide] = None,
        min_value: Optional[float] = None,
        cursor: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> CursorResponse[list[MarketPosition]]:
        """Every open position in one market, largest ``position_value`` first.

        Reads the latest live snapshot, or the hourly snapshot at ``hour``
        (echoed as ``meta.snapshot_ts``). The first page carries
        ``meta.totals`` (a :class:`MarketPositionsSummary` over the whole
        filtered set).

        Args:
            symbol: Market symbol (HIP-3 symbols are case-sensitive, e.g. ``xyz:TSLA``).
            hour: An exact UTC hour with a committed snapshot; omit for live.
            side: ``"long"`` or ``"short"``.
            min_value: Minimum position value in USD.
            cursor: ``next_cursor`` of the previous page.
            limit: Rows per page (default 100, max 2,000).
        """
        return self._fetch(self._market_ep(symbol, hour, side, min_value, None, cursor, limit))

    async def amarket(
        self,
        symbol: str,
        *,
        hour: Optional[Timestamp] = None,
        side: Optional[PositionSide] = None,
        min_value: Optional[float] = None,
        cursor: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> CursorResponse[list[MarketPosition]]:
        """Async version of :meth:`market`."""
        return await self._afetch(
            self._market_ep(symbol, hour, side, min_value, None, cursor, limit)
        )

    def iterate_market(
        self,
        symbol: str,
        *,
        hour: Optional[Timestamp] = None,
        side: Optional[PositionSide] = None,
        min_value: Optional[float] = None,
        limit: Optional[int] = None,
    ) -> Iterator[MarketPosition]:
        """Yield every position of :meth:`market`, following cursors (one snapshot)."""
        return self._iterate(
            self._market_ep(symbol, hour, side, min_value, None, None, limit), _market_position_rows
        )

    def aiterate_market(
        self,
        symbol: str,
        *,
        hour: Optional[Timestamp] = None,
        side: Optional[PositionSide] = None,
        min_value: Optional[float] = None,
        limit: Optional[int] = None,
    ) -> AsyncIterator[MarketPosition]:
        """Async version of :meth:`iterate_market`."""
        return self._aiterate(
            self._market_ep(symbol, hour, side, min_value, None, None, limit), _market_position_rows
        )

    def market_summary(
        self,
        symbol: str,
        *,
        start: Optional[Timestamp] = None,
        end: Optional[Timestamp] = None,
        cursor: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> CursorResponse[list[MarketPositionsSummary]]:
        """Long/short aggregates of one market.

        Without ``start`` and ``end``: one summary at the latest live snapshot.
        With them: one summary per hourly snapshot in ``[start, end)``, at most
        168 hours per page.

        Args:
            symbol: Market symbol.
            start: Inclusive start of the hourly series.
            end: Exclusive end of the hourly series.
            cursor: ``next_cursor`` of the previous page.
            limit: Summaries per page (default 100, at most 168).
        """
        return self._fetch(self._summary_ep(symbol, start, end, None, cursor, limit))

    async def amarket_summary(
        self,
        symbol: str,
        *,
        start: Optional[Timestamp] = None,
        end: Optional[Timestamp] = None,
        cursor: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> CursorResponse[list[MarketPositionsSummary]]:
        """Async version of :meth:`market_summary`."""
        return await self._afetch(self._summary_ep(symbol, start, end, None, cursor, limit))

    def iterate_market_summary(
        self,
        symbol: str,
        *,
        start: Timestamp,
        end: Timestamp,
        limit: Optional[int] = None,
    ) -> Iterator[MarketPositionsSummary]:
        """Yield every hourly summary of :meth:`market_summary` in ``[start, end)``."""
        return self._iterate(self._summary_ep(symbol, start, end, None, None, limit), _summary_rows)

    def aiterate_market_summary(
        self,
        symbol: str,
        *,
        start: Timestamp,
        end: Timestamp,
        limit: Optional[int] = None,
    ) -> AsyncIterator[MarketPositionsSummary]:
        """Async version of :meth:`iterate_market_summary`."""
        return self._aiterate(
            self._summary_ep(symbol, start, end, None, None, limit), _summary_rows
        )

    def all(
        self,
        hour: Timestamp,
        *,
        cursor: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> CursorResponse[list[MarketPosition]]:
        """Every open position across every market at one hourly snapshot (bulk).

        Args:
            hour: An exact UTC hour with a committed snapshot.
            cursor: ``next_cursor`` of the previous page.
            limit: Rows per page (default 1,000, max 2,000).
        """
        return self._fetch(self._bulk_ep(hour, None, cursor, limit))

    async def aall(
        self,
        hour: Timestamp,
        *,
        cursor: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> CursorResponse[list[MarketPosition]]:
        """Async version of :meth:`all`."""
        return await self._afetch(self._bulk_ep(hour, None, cursor, limit))

    def iterate_all(
        self, hour: Timestamp, *, limit: Optional[int] = None
    ) -> Iterator[MarketPosition]:
        """Yield every position of :meth:`all` at ``hour``, following cursors."""
        return self._iterate(self._bulk_ep(hour, None, None, limit), _market_position_rows)

    def aiterate_all(
        self, hour: Timestamp, *, limit: Optional[int] = None
    ) -> AsyncIterator[MarketPosition]:
        """Async version of :meth:`iterate_all`."""
        return self._aiterate(self._bulk_ep(hour, None, None, limit), _market_position_rows)


AccountIndex = Union[int, str]
"""A Lighter account index: an integer, or a string of digits."""


def _account_index(account_index: AccountIndex, l1_hint: bool) -> str:
    """Validate a Lighter account index and render it for the path."""
    if isinstance(account_index, bool):
        raise ValueError("account_index must be an integer Lighter account index")
    if isinstance(account_index, int):
        if account_index < 0:
            raise ValueError("account_index must be a non-negative integer")
        return str(account_index)
    text = str(account_index).strip()
    if text.isdigit():
        return text
    hint = " Resolve an L1 address with client.lighter.accounts.by_l1(address)." if l1_hint else ""
    raise ValueError(f"account_index must be an integer Lighter account index.{hint}")


class LighterPositionsResource(_PositionsBase):
    """Account positions for Lighter (``client.lighter.positions``) and Lighter
    on Robinhood Chain (``client.rh_lighter.positions``).

    Accounts are integer Lighter account indices (on mainnet,
    ``client.lighter.accounts.by_l1()`` resolves an L1 address to them).
    Perp markets only. System accounts (settlement, insurance) are left out
    of the market routes unless ``include_system=True``, and are labelled by
    ``account_kind`` everywhere.

    Coverage: from 2025-01-17 on Lighter mainnet and from 2026-06-26 on
    Robinhood Chain, with hourly history over the same range and a live
    snapshot every 2 minutes.

    Example:
        >>> now = client.lighter.positions.get(281474976623827)
        >>> for p in now.data.positions:
        ...     print(p.symbol, p.side, p.size, p.quality)
    """

    def __init__(
        self, http: HttpClient, base_path: str = "/v1/lighter", *, l1_resolver: bool = True
    ):
        super().__init__(http, base_path, _upper)
        self._l1_hint = l1_resolver

    def _account_path(self, account_index: AccountIndex, suffix: str) -> str:
        index = _account_index(account_index, self._l1_hint)
        return f"{self._base_path}/accounts/{index}/{suffix}"

    def _get_ep(
        self,
        account_index: AccountIndex,
        timestamp: Optional[Timestamp],
        symbol: Optional[str],
        cursor: Optional[str],
        limit: Optional[int],
    ) -> _Endpoint:
        return _Endpoint(
            self._account_path(account_index, "positions"),
            {
                "timestamp": _to_ms(timestamp),
                "symbol": self._symbol_param(symbol),
                "cursor": cursor,
                "limit": limit,
            },
            _wallet,
        )

    def _range_ep(
        self,
        account_index: AccountIndex,
        suffix: str,
        start: Timestamp,
        end: Timestamp,
        symbol: Optional[str],
        cursor: Optional[str],
        limit: Optional[int],
        parse: Callable[[Any], Any],
    ) -> _Endpoint:
        return _Endpoint(
            self._account_path(account_index, suffix),
            {
                "start": _to_ms(start),
                "end": _to_ms(end),
                "symbol": self._symbol_param(symbol),
                "cursor": cursor,
                "limit": limit,
            },
            parse,
        )

    # ---- account: current or as-of ---------------------------------------

    def get(
        self,
        account_index: AccountIndex,
        *,
        timestamp: Optional[Timestamp] = None,
        symbol: Optional[str] = None,
        cursor: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> CursorResponse[WalletPositions]:
        """Open positions of a Lighter account, now or at an instant.

        Same semantics as the Hyperliquid route: the latest live snapshot
        without ``timestamp``; with it, the state after every event before
        that instant (an exact hour serves the hourly snapshot, anything else
        is reconstructed and clamped to ``meta.built_through``). Rows carry
        ``finalized``: ``True`` once every event behind them is final.

        Args:
            account_index: Integer Lighter account index.
            timestamp: As-of instant; omit for the latest live snapshot.
            symbol: Only this market.
            cursor: ``next_cursor`` of the previous page.
            limit: Rows per page (default 500, max 5,000).

        Returns:
            ``CursorResponse`` whose ``data`` is :class:`WalletPositions`.
        """
        return self._fetch(self._get_ep(account_index, timestamp, symbol, cursor, limit))

    async def aget(
        self,
        account_index: AccountIndex,
        *,
        timestamp: Optional[Timestamp] = None,
        symbol: Optional[str] = None,
        cursor: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> CursorResponse[WalletPositions]:
        """Async version of :meth:`get`."""
        return await self._afetch(self._get_ep(account_index, timestamp, symbol, cursor, limit))

    # ---- account: hourly history -----------------------------------------

    def history(
        self,
        account_index: AccountIndex,
        *,
        start: Timestamp,
        end: Timestamp,
        symbol: Optional[str] = None,
        cursor: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> CursorResponse[list[Position]]:
        """Hourly position rows of a Lighter account in ``[start, end)``.

        Args:
            account_index: Integer Lighter account index.
            start: Inclusive start.
            end: Exclusive end.
            symbol: Only this market.
            cursor: ``next_cursor`` of the previous page.
            limit: Rows per page (default 500, max 5,000).
        """
        return self._fetch(
            self._range_ep(
                account_index, "positions/history", start, end, symbol, cursor, limit, _positions
            )
        )

    async def ahistory(
        self,
        account_index: AccountIndex,
        *,
        start: Timestamp,
        end: Timestamp,
        symbol: Optional[str] = None,
        cursor: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> CursorResponse[list[Position]]:
        """Async version of :meth:`history`."""
        return await self._afetch(
            self._range_ep(
                account_index, "positions/history", start, end, symbol, cursor, limit, _positions
            )
        )

    def iterate_history(
        self,
        account_index: AccountIndex,
        *,
        start: Timestamp,
        end: Timestamp,
        symbol: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> Iterator[Position]:
        """Yield every hourly position row of :meth:`history`, following cursors."""
        return self._iterate(
            self._range_ep(
                account_index, "positions/history", start, end, symbol, None, limit, _positions
            ),
            _positions_rows,
        )

    def aiterate_history(
        self,
        account_index: AccountIndex,
        *,
        start: Timestamp,
        end: Timestamp,
        symbol: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> AsyncIterator[Position]:
        """Async version of :meth:`iterate_history`."""
        return self._aiterate(
            self._range_ep(
                account_index, "positions/history", start, end, symbol, None, limit, _positions
            ),
            _positions_rows,
        )

    # ---- account: change log ---------------------------------------------

    def changes(
        self,
        account_index: AccountIndex,
        *,
        start: Timestamp,
        end: Timestamp,
        symbol: Optional[str] = None,
        cursor: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> CursorResponse[list[PositionChange]]:
        """Position change-log legs of a Lighter account in ``[start, end)``.

        ``end`` is clamped to ``meta.built_through``. Legs before
        ``meta.finalized_through`` are built from the canonical trade record
        and are final, the same boundary as ``trades.list()``.

        Args:
            account_index: Integer Lighter account index.
            start: Inclusive start.
            end: Exclusive end.
            symbol: Only this market.
            cursor: ``next_cursor`` of the previous page.
            limit: Rows per page (default 500, max 5,000).
        """
        return self._fetch(
            self._range_ep(
                account_index, "positions/changes", start, end, symbol, cursor, limit, _changes
            )
        )

    async def achanges(
        self,
        account_index: AccountIndex,
        *,
        start: Timestamp,
        end: Timestamp,
        symbol: Optional[str] = None,
        cursor: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> CursorResponse[list[PositionChange]]:
        """Async version of :meth:`changes`."""
        return await self._afetch(
            self._range_ep(
                account_index, "positions/changes", start, end, symbol, cursor, limit, _changes
            )
        )

    def iterate_changes(
        self,
        account_index: AccountIndex,
        *,
        start: Timestamp,
        end: Timestamp,
        symbol: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> Iterator[PositionChange]:
        """Yield every change-log leg of :meth:`changes`, following cursors."""
        return self._iterate(
            self._range_ep(
                account_index, "positions/changes", start, end, symbol, None, limit, _changes
            ),
            _change_rows,
        )

    def aiterate_changes(
        self,
        account_index: AccountIndex,
        *,
        start: Timestamp,
        end: Timestamp,
        symbol: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> AsyncIterator[PositionChange]:
        """Async version of :meth:`iterate_changes`."""
        return self._aiterate(
            self._range_ep(
                account_index, "positions/changes", start, end, symbol, None, limit, _changes
            ),
            _change_rows,
        )

    # ---- market routes ---------------------------------------------------

    def market(
        self,
        symbol: str,
        *,
        hour: Optional[Timestamp] = None,
        side: Optional[PositionSide] = None,
        min_value: Optional[float] = None,
        include_system: Optional[bool] = None,
        cursor: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> CursorResponse[list[MarketPosition]]:
        """Every open position in one Lighter perp market, largest value first.

        Reads the latest live snapshot, or the hourly snapshot at ``hour``.
        The first page carries ``meta.totals``.

        Args:
            symbol: Perp market symbol (e.g. ``BTC``).
            hour: An exact UTC hour with a committed snapshot; omit for live.
            side: ``"long"`` or ``"short"``.
            min_value: Minimum position value.
            include_system: Include settlement, insurance and other system accounts.
            cursor: ``next_cursor`` of the previous page.
            limit: Rows per page (default 100, max 2,000).
        """
        return self._fetch(
            self._market_ep(symbol, hour, side, min_value, include_system, cursor, limit)
        )

    async def amarket(
        self,
        symbol: str,
        *,
        hour: Optional[Timestamp] = None,
        side: Optional[PositionSide] = None,
        min_value: Optional[float] = None,
        include_system: Optional[bool] = None,
        cursor: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> CursorResponse[list[MarketPosition]]:
        """Async version of :meth:`market`."""
        return await self._afetch(
            self._market_ep(symbol, hour, side, min_value, include_system, cursor, limit)
        )

    def iterate_market(
        self,
        symbol: str,
        *,
        hour: Optional[Timestamp] = None,
        side: Optional[PositionSide] = None,
        min_value: Optional[float] = None,
        include_system: Optional[bool] = None,
        limit: Optional[int] = None,
    ) -> Iterator[MarketPosition]:
        """Yield every position of :meth:`market`, following cursors (one snapshot)."""
        return self._iterate(
            self._market_ep(symbol, hour, side, min_value, include_system, None, limit),
            _market_position_rows,
        )

    def aiterate_market(
        self,
        symbol: str,
        *,
        hour: Optional[Timestamp] = None,
        side: Optional[PositionSide] = None,
        min_value: Optional[float] = None,
        include_system: Optional[bool] = None,
        limit: Optional[int] = None,
    ) -> AsyncIterator[MarketPosition]:
        """Async version of :meth:`iterate_market`."""
        return self._aiterate(
            self._market_ep(symbol, hour, side, min_value, include_system, None, limit),
            _market_position_rows,
        )

    def market_summary(
        self,
        symbol: str,
        *,
        start: Optional[Timestamp] = None,
        end: Optional[Timestamp] = None,
        include_system: Optional[bool] = None,
        cursor: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> CursorResponse[list[MarketPositionsSummary]]:
        """Long/short aggregates of one Lighter perp market.

        Without ``start`` and ``end``: one summary at the latest live snapshot.
        With them: one summary per hourly snapshot in ``[start, end)``, at most
        168 hours per page.
        """
        return self._fetch(self._summary_ep(symbol, start, end, include_system, cursor, limit))

    async def amarket_summary(
        self,
        symbol: str,
        *,
        start: Optional[Timestamp] = None,
        end: Optional[Timestamp] = None,
        include_system: Optional[bool] = None,
        cursor: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> CursorResponse[list[MarketPositionsSummary]]:
        """Async version of :meth:`market_summary`."""
        return await self._afetch(
            self._summary_ep(symbol, start, end, include_system, cursor, limit)
        )

    def iterate_market_summary(
        self,
        symbol: str,
        *,
        start: Timestamp,
        end: Timestamp,
        include_system: Optional[bool] = None,
        limit: Optional[int] = None,
    ) -> Iterator[MarketPositionsSummary]:
        """Yield every hourly summary of :meth:`market_summary` in ``[start, end)``."""
        return self._iterate(
            self._summary_ep(symbol, start, end, include_system, None, limit), _summary_rows
        )

    def aiterate_market_summary(
        self,
        symbol: str,
        *,
        start: Timestamp,
        end: Timestamp,
        include_system: Optional[bool] = None,
        limit: Optional[int] = None,
    ) -> AsyncIterator[MarketPositionsSummary]:
        """Async version of :meth:`iterate_market_summary`."""
        return self._aiterate(
            self._summary_ep(symbol, start, end, include_system, None, limit), _summary_rows
        )

    def all(
        self,
        hour: Timestamp,
        *,
        include_system: Optional[bool] = None,
        cursor: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> CursorResponse[list[MarketPosition]]:
        """Every open position across every perp market at one hourly snapshot (bulk).

        Args:
            hour: An exact UTC hour with a committed snapshot.
            include_system: Include settlement, insurance and other system accounts.
            cursor: ``next_cursor`` of the previous page.
            limit: Rows per page (default 1,000, max 2,000).
        """
        return self._fetch(self._bulk_ep(hour, include_system, cursor, limit))

    async def aall(
        self,
        hour: Timestamp,
        *,
        include_system: Optional[bool] = None,
        cursor: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> CursorResponse[list[MarketPosition]]:
        """Async version of :meth:`all`."""
        return await self._afetch(self._bulk_ep(hour, include_system, cursor, limit))

    def iterate_all(
        self,
        hour: Timestamp,
        *,
        include_system: Optional[bool] = None,
        limit: Optional[int] = None,
    ) -> Iterator[MarketPosition]:
        """Yield every position of :meth:`all` at ``hour``, following cursors."""
        return self._iterate(
            self._bulk_ep(hour, include_system, None, limit), _market_position_rows
        )

    def aiterate_all(
        self,
        hour: Timestamp,
        *,
        include_system: Optional[bool] = None,
        limit: Optional[int] = None,
    ) -> AsyncIterator[MarketPosition]:
        """Async version of :meth:`iterate_all`."""
        return self._aiterate(
            self._bulk_ep(hour, include_system, None, limit), _market_position_rows
        )


class LighterAccountsResource(_PositionsBase):
    """Lighter L1 address resolver (``client.lighter.accounts``, mainnet only).

    Example:
        >>> owned = client.lighter.accounts.by_l1("0xabc...")
        >>> print(owned.data.total_accounts)
        >>> for account in owned.data.accounts:
        ...     print(account.account_index, account.account_type)
    """

    def __init__(self, http: HttpClient, base_path: str = "/v1/lighter"):
        super().__init__(http, base_path, _upper)

    def _by_l1_ep(self, l1_address: str, cursor: Optional[str], limit: Optional[int]) -> _Endpoint:
        return _Endpoint(
            f"{self._base_path}/accounts",
            {"l1_address": l1_address, "cursor": cursor, "limit": limit},
            _l1_accounts,
        )

    def by_l1(
        self,
        l1_address: str,
        *,
        cursor: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> CursorResponse[LighterL1Accounts]:
        """Account indices owned by an L1 (0x) address.

        Billed at the per-request minimum.

        Args:
            l1_address: 0x L1 address.
            cursor: ``next_cursor`` of the previous page.
            limit: Accounts per page (default 500, max 5,000).

        Returns:
            ``CursorResponse`` whose ``data`` is :class:`LighterL1Accounts`
            (``l1_address``, ``total_accounts``, ``accounts``).
        """
        return self._fetch(self._by_l1_ep(l1_address, cursor, limit))

    async def aby_l1(
        self,
        l1_address: str,
        *,
        cursor: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> CursorResponse[LighterL1Accounts]:
        """Async version of :meth:`by_l1`."""
        return await self._afetch(self._by_l1_ep(l1_address, cursor, limit))

    def iterate_by_l1(
        self, l1_address: str, *, limit: Optional[int] = None
    ) -> Iterator[LighterL1Account]:
        """Yield every account owned by ``l1_address``, following cursors."""
        return self._iterate(self._by_l1_ep(l1_address, None, limit), _l1_account_rows)

    def aiterate_by_l1(
        self, l1_address: str, *, limit: Optional[int] = None
    ) -> AsyncIterator[LighterL1Account]:
        """Async version of :meth:`iterate_by_l1`."""
        return self._aiterate(self._by_l1_ep(l1_address, None, limit), _l1_account_rows)


# ---- row extractors for the iterators --------------------------------------


def _positions_rows(data: list[Position]) -> list[Position]:
    return data


def _change_rows(data: list[PositionChange]) -> list[PositionChange]:
    return data


def _account_rows(data: list[AccountSummary]) -> list[AccountSummary]:
    return data


def _market_position_rows(data: list[MarketPosition]) -> list[MarketPosition]:
    return data


def _summary_rows(data: list[MarketPositionsSummary]) -> list[MarketPositionsSummary]:
    return data


def _l1_account_rows(data: LighterL1Accounts) -> list[LighterL1Account]:
    return data.accounts


__all__ = [
    "AccountIndex",
    "HyperliquidPositionsResource",
    "LighterAccountsResource",
    "LighterPositionsResource",
    "PositionSide",
]
