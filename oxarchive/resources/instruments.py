"""Instruments API resource."""

from __future__ import annotations

from urllib.parse import quote

from ..http import HttpClient
from ..types import Hip3Instrument, Hip4Outcome, Instrument, LighterInstrument


def _hip4_path_segment(symbol: str) -> str:
    """Normalize a HIP-4 coin symbol for REST paths.

    Backend accepts both bare numeric (``0``) and ``#``-prefixed (``%230``)
    forms. We send the bare form to avoid percent-encoding pain.
    """
    s = symbol.lstrip("#")
    if s.isdigit():
        return s
    return quote(symbol, safe="")


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


class Hip3InstrumentsResource:
    """
    HIP-3 Builder Perps Instruments API resource.

    HIP-3 instruments are derived from live market data and include
    mark price, open interest, and mid price context.

    Example:
        >>> # List all HIP-3 instruments
        >>> instruments = client.hyperliquid.hip3.instruments.list()
        >>>
        >>> # Get specific instrument
        >>> us500 = client.hyperliquid.hip3.instruments.get("km:US500")
        >>> print(f"Mark price: {us500.mark_price}")
    """

    def __init__(self, http: HttpClient, base_path: str = "/v1/hyperliquid/hip3", coin_transform=None):
        self._http = http
        self._base_path = base_path
        self._coin_transform = coin_transform or (lambda c: c)

    def list(self) -> list[Hip3Instrument]:
        """
        List all available HIP-3 instruments with latest market data.

        Returns:
            List of HIP-3 instruments
        """
        data = self._http.get(f"{self._base_path}/instruments")
        return [Hip3Instrument.model_validate(item) for item in data["data"]]

    async def alist(self) -> list[Hip3Instrument]:
        """Async version of list()."""
        data = await self._http.aget(f"{self._base_path}/instruments")
        return [Hip3Instrument.model_validate(item) for item in data["data"]]

    def get(self, coin: str) -> Hip3Instrument:
        """
        Get a specific HIP-3 instrument by coin name.

        Args:
            coin: The coin name (e.g., 'km:US500', 'xyz:XYZ100'). Case-sensitive.

        Returns:
            HIP-3 instrument details with latest market data
        """
        coin = self._coin_transform(coin)
        data = self._http.get(f"{self._base_path}/instruments/{coin}")
        return Hip3Instrument.model_validate(data["data"])

    async def aget(self, coin: str) -> Hip3Instrument:
        """Async version of get()."""
        coin = self._coin_transform(coin)
        data = await self._http.aget(f"{self._base_path}/instruments/{coin}")
        return Hip3Instrument.model_validate(data["data"])


class Hip4InstrumentsResource:
    """
    HIP-4 Outcome Markets per-side instruments resource.

    Each row is one ``#N`` (per outcome side). For outcome-level metadata,
    use :class:`Hip4OutcomesResource`.

    Symbols can be passed as either the bare numeric form (``"0"``) or the
    ``#``-prefixed form (``"#0"``). The SDK normalizes to the bare form on
    the REST path; the backend routes both to the same record.

    Example:
        >>> instruments = client.hyperliquid.hip4.instruments.list()
        >>> outcome0_yes = client.hyperliquid.hip4.instruments.get("0")
    """

    def __init__(self, http: HttpClient, base_path: str = "/v1/hyperliquid/hip4"):
        self._http = http
        self._base_path = base_path

    def list(self) -> list[Hip4Outcome]:
        """List all HIP-4 per-side instruments."""
        data = self._http.get(f"{self._base_path}/instruments")
        return [Hip4Outcome.model_validate(item) for item in data["data"]]

    async def alist(self) -> list[Hip4Outcome]:
        """Async version of list()."""
        data = await self._http.aget(f"{self._base_path}/instruments")
        return [Hip4Outcome.model_validate(item) for item in data["data"]]

    def get(self, symbol: str) -> Hip4Outcome:
        """Get a single per-side instrument by symbol.

        Args:
            symbol: HIP-4 symbol. Either ``"0"`` or ``"#0"`` works; the SDK
                normalizes to the bare form on the path.
        """
        seg = _hip4_path_segment(symbol)
        data = self._http.get(f"{self._base_path}/instruments/{seg}")
        return Hip4Outcome.model_validate(data["data"])

    async def aget(self, symbol: str) -> Hip4Outcome:
        """Async version of get()."""
        seg = _hip4_path_segment(symbol)
        data = await self._http.aget(f"{self._base_path}/instruments/{seg}")
        return Hip4Outcome.model_validate(data["data"])
