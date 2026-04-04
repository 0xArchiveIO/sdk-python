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
from .orders import OrdersResource
from .l4_orderbook import L4OrderBookResource
from .l2_orderbook import L2OrderBookResource
from .l3_orderbook import L3OrderBookResource

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
    "OrdersResource",
    "L4OrderBookResource",
    "L2OrderBookResource",
    "L3OrderBookResource",
]
