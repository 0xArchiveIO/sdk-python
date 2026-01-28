"""Instruments API resource."""

from __future__ import annotations

from ..http import HttpClient
from ..types import Instrument, LighterInstrument


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

    def __init__(self, http: HttpClient, base_path: str = "/v1"):
        self._http = http
        self._base_path = base_path

    def list(self) -> list[Instrument]:
        """
        List all available trading instruments.

        Returns:
            List of instruments
        """
        data = self._http.get(f"{self._base_path}/instruments")
        return [Instrument.model_validate(item) for item in data["data"]]

    async def alist(self) -> list[Instrument]:
        """Async version of list()."""
        data = await self._http.aget(f"{self._base_path}/instruments")
        return [Instrument.model_validate(item) for item in data["data"]]

    def get(self, coin: str) -> Instrument:
        """
        Get a specific instrument by coin symbol.

        Args:
            coin: The coin symbol (e.g., 'BTC', 'ETH')

        Returns:
            Instrument details
        """
        data = self._http.get(f"{self._base_path}/instruments/{coin.upper()}")
        return Instrument.model_validate(data["data"])

    async def aget(self, coin: str) -> Instrument:
        """Async version of get()."""
        data = await self._http.aget(f"{self._base_path}/instruments/{coin.upper()}")
        return Instrument.model_validate(data["data"])


class LighterInstrumentsResource:
    """
    Lighter.xyz Instruments API resource.

    Lighter instruments have a different schema than Hyperliquid with more
    detailed market configuration including fees and minimum amounts.

    Example:
        >>> # List all Lighter instruments
        >>> instruments = client.lighter.instruments.list()
        >>>
        >>> # Get specific instrument
        >>> btc = client.lighter.instruments.get("BTC")
        >>> print(f"Taker fee: {btc.taker_fee}")
    """

    def __init__(self, http: HttpClient, base_path: str = "/v1/lighter"):
        self._http = http
        self._base_path = base_path

    def list(self) -> list[LighterInstrument]:
        """
        List all available Lighter trading instruments.

        Returns:
            List of Lighter instruments with full market configuration
        """
        data = self._http.get(f"{self._base_path}/instruments")
        return [LighterInstrument.model_validate(item) for item in data["data"]]

    async def alist(self) -> list[LighterInstrument]:
        """Async version of list()."""
        data = await self._http.aget(f"{self._base_path}/instruments")
        return [LighterInstrument.model_validate(item) for item in data["data"]]

    def get(self, coin: str) -> LighterInstrument:
        """
        Get a specific Lighter instrument by coin symbol.

        Args:
            coin: The coin symbol (e.g., 'BTC', 'ETH')

        Returns:
            Lighter instrument details with full market configuration
        """
        data = self._http.get(f"{self._base_path}/instruments/{coin.upper()}")
        return LighterInstrument.model_validate(data["data"])

    async def aget(self, coin: str) -> LighterInstrument:
        """Async version of get()."""
        data = await self._http.aget(f"{self._base_path}/instruments/{coin.upper()}")
        return LighterInstrument.model_validate(data["data"])
