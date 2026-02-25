"""Resource modules."""

from .orderbook import OrderBookResource
from .trades import TradesResource
from .instruments import InstrumentsResource, LighterInstrumentsResource, Hip3InstrumentsResource
from .funding import FundingResource
from .openinterest import OpenInterestResource
from .candles import CandlesResource
from .liquidations import LiquidationsResource
from .data_quality import DataQualityResource
from .web3 import Web3Resource

__all__ = [
    "OrderBookResource",
    "TradesResource",
    "InstrumentsResource",
    "LighterInstrumentsResource",
    "Hip3InstrumentsResource",
    "FundingResource",
    "OpenInterestResource",
    "CandlesResource",
    "LiquidationsResource",
    "DataQualityResource",
    "Web3Resource",
]
