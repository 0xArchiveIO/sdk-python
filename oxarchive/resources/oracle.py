"""HIP-3 oracle API resource."""

from __future__ import annotations

from ..http import HttpClient
from ..types import Hip3OracleDiscoveryBounds, Hip3OracleExternalPrice


class Hip3OracleResource:
    """
    HIP-3 oracle reads: the deployer-pushed external price and the discovery bounds.

    Symbols keep their builder prefix and case (for example ``km:US500``).

    Example:
        >>> price = client.hyperliquid.hip3.oracle.external_price("km:US500")
        >>> print(price.external_price, price.mark_price)
        >>> bounds = client.hyperliquid.hip3.oracle.discovery_bounds("km:US500")
        >>> print(bounds.lower_bound, bounds.upper_bound)
    """

    def __init__(self, http: HttpClient, base_path: str = "/v1/hyperliquid/hip3") -> None:
        self._http = http
        self._base_path = base_path

    def discovery_bounds(self, symbol: str) -> Hip3OracleDiscoveryBounds:
        """
        Get the instantaneous discovery bounds for a HIP-3 market.

        The bounds are ``reference_price`` times one minus and one plus
        ``bound_fraction``, where the reference is the external price when
        available and the mark price otherwise, and the fraction follows from
        the market's max leverage. The full ratcheted range can be wider when
        a deployer's reset configuration applies.

        Args:
            symbol: HIP-3 symbol with its builder prefix (case-sensitive).
        """
        data = self._http.get(f"{self._base_path}/oracle/discovery-bounds/{symbol}")
        return Hip3OracleDiscoveryBounds.model_validate(data["data"])

    async def adiscovery_bounds(self, symbol: str) -> Hip3OracleDiscoveryBounds:
        """Async version of :meth:`discovery_bounds`."""
        data = await self._http.aget(f"{self._base_path}/oracle/discovery-bounds/{symbol}")
        return Hip3OracleDiscoveryBounds.model_validate(data["data"])

    def external_price(self, symbol: str) -> Hip3OracleExternalPrice:
        """
        Get the latest deployer-pushed external price and mark price for a HIP-3 market.

        Args:
            symbol: HIP-3 symbol with its builder prefix (case-sensitive).
        """
        data = self._http.get(f"{self._base_path}/oracle/external-price/{symbol}")
        return Hip3OracleExternalPrice.model_validate(data["data"])

    async def aexternal_price(self, symbol: str) -> Hip3OracleExternalPrice:
        """Async version of :meth:`external_price`."""
        data = await self._http.aget(f"{self._base_path}/oracle/external-price/{symbol}")
        return Hip3OracleExternalPrice.model_validate(data["data"])
