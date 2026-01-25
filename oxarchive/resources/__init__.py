"""Resource modules."""

from .orderbook import OrderBookResource
from .trades import TradesResource
from .instruments import InstrumentsResource
from .funding import FundingResource
from .openinterest import OpenInterestResource

__all__ = [
    "OrderBookResource",
    "TradesResource",
    "InstrumentsResource",
    "FundingResource",
    "OpenInterestResource",
]
