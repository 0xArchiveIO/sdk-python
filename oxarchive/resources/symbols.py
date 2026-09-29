"""Public symbol universe API resource."""

from __future__ import annotations

from typing import Any, List

from ..http import HttpClient
from ..types import SymbolEntry, _body


def _entries(payload: dict[str, Any]) -> list[SymbolEntry]:
    body = _body(payload)
    rows = body if isinstance(body, list) else body.get("symbols") or []
    return [SymbolEntry.model_validate(item) for item in rows]


class SymbolsResource:
    """
    The public symbol universe across every venue family.

    One entry per market with its venue family (``exchange``), the data types
    served for it, coverage dates overall and per data type, and, for HIP-4,
    the slug, outcome pair and display title. Use it to discover symbols
    before choosing a venue-specific route. The route needs no API key and
    returns the whole universe in one response.

    Example:
        >>> symbols = client.symbols.list()
        >>> hip3 = [s.symbol for s in symbols if s.exchange == "hip3"]
    """

    def __init__(self, http: HttpClient, base_path: str = "/v1") -> None:
        self._http = http
        self._base_path = base_path

    def list(self) -> list[SymbolEntry]:
        """List every public symbol, across all venue families."""
        return _entries(self._http.get(f"{self._base_path}/symbols"))

    async def alist(self) -> List[SymbolEntry]:
        """Async version of :meth:`list`."""
        return _entries(await self._http.aget(f"{self._base_path}/symbols"))
