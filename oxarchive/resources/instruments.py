"""Instruments API resource."""

from __future__ import annotations

from ..http import HttpClient
from ..types import Instrument


class InstrumentsResource:
    """
    Instruments API resource.

    Example:
        >>> # List all instruments
        >>> instruments = client.instruments.list()
        >>>
        >>> # Get specific instrument
        >>> btc = client.instruments.get("BTC")
    """

    def __init__(self, http: HttpClient):
        self._http = http

    def list(self) -> list[Instrument]:
        """
        List all available trading instruments.

        Returns:
            List of instruments
        """
        data = self._http.get("/v1/instruments")
        return [Instrument.model_validate(item) for item in data["data"]]

    async def alist(self) -> list[Instrument]:
        """Async version of list()."""
        data = await self._http.aget("/v1/instruments")
        return [Instrument.model_validate(item) for item in data["data"]]

    def get(self, coin: str) -> Instrument:
        """
        Get a specific instrument by coin symbol.

        Args:
            coin: The coin symbol (e.g., 'BTC', 'ETH')

        Returns:
            Instrument details
        """
        data = self._http.get(f"/v1/instruments/{coin.upper()}")
        return Instrument.model_validate(data["data"])

    async def aget(self, coin: str) -> Instrument:
        """Async version of get()."""
        data = await self._http.aget(f"/v1/instruments/{coin.upper()}")
        return Instrument.model_validate(data["data"])
