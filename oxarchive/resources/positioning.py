"""Positioning cross-section (Hyperliquid core and HIP-3). Build and above."""

from __future__ import annotations

from ..http import HttpClient
from ..types import CursorResponse, PositioningReading, PositioningWindow
from ._paging import page_of

POSITIONING_WINDOWS = ("1h", "4h", "24h")
"""The trailing windows the API accepts on positioning."""


def _window(window: str) -> str:
    if window not in POSITIONING_WINDOWS:
        raise ValueError("window is required for positioning: 1h, 4h or 24h")
    return window


class PositioningResource:
    """Every listed perp's open interest change, taker buy and sell volume and
    liquidations over a trailing window, with each market's typical move over
    windows of that length: a ranking or a grouping by positioning in one call.

    Served for Hyperliquid core (``client.hyperliquid.positioning``) and HIP-3
    (``client.hyperliquid.hip3.positioning``). Included with the Build, Pro,
    Scale and Enterprise plans; a Free key raises
    :class:`~oxarchive.PlanRequiredError`.

    The current window only: there is no history, no paging and no symbol
    filter (filter the records yourself). One record per listed perp, sorted
    by symbol; delisted markets are not listed. The window is
    ``[close - window, close)``, the close being the newest 5-minute boundary
    about 4 minutes behind now (``meta.as_of``). ``oi_*`` and ``mark_*`` are
    ``None`` when that 5-minute bucket has no reading, never 0. ``typical_*``
    are the median absolute move over windows of the same length sliding by 5
    minutes over about the last 6.9 days, ``None`` under 288 counted windows.
    A 503 ``upstream_unavailable`` ("still being prepared") is retryable.

    Example:
        >>> cross = client.hyperliquid.positioning.current("4h")
        >>> print(cross.meta.as_of)
        >>> btc = next(r for r in cross.data if r.symbol == "BTC")
    """

    def __init__(self, http: HttpClient, base_path: str = "/v1/hyperliquid") -> None:
        self._http = http
        self._path = f"{base_path}/positioning"

    def current(self, window: PositioningWindow) -> CursorResponse[list[PositioningReading]]:
        """Get the cross-section for the trailing ``window``.

        Args:
            window: ``1h``, ``4h`` or ``24h``.

        Returns:
            Every listed perp's reading, with ``meta.as_of`` (the close). The
            response is never paged: ``next_cursor`` is ``None``.

        Raises:
            PlanRequiredError: The key's plan does not include positioning.
        """
        payload = self._http.get(self._path, params={"window": _window(window)})
        return page_of(payload, PositioningReading)

    async def acurrent(self, window: PositioningWindow) -> CursorResponse[list[PositioningReading]]:
        """Async version of :meth:`current`."""
        payload = await self._http.aget(self._path, params={"window": _window(window)})
        return page_of(payload, PositioningReading)
