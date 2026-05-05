"""Resource modules."""

from .orderbook import OrderBookResource
from .trades import TradesResource
from .instruments import (
    Hip3InstrumentsResource,
    Hip4InstrumentsResource,
    InstrumentsResource,
    LighterInstrumentsResource,
)
from .funding import FundingResource
from .openinterest import OpenInterestResource
from .candles import CandlesResource
from .liquidations import LiquidationsResource
from .data_quality import DataQualityResource
from .web3 import Web3Resource
from .orders import OrdersResource
from .outcomes import Hip4OutcomesResource
from .l4_orderbook import L4OrderBookResource
from .l2_orderbook import L2OrderBookResource
from .l3_orderbook import L3OrderBookResource

__all__ = [
    "OrderBookResource",
    "TradesResource",
    "InstrumentsResource",
    "LighterInstrumentsResource",
    "Hip3InstrumentsResource",
    "Hip4InstrumentsResource",
    "FundingResource",
    "OpenInterestResource",
    "CandlesResource",
    "LiquidationsResource",
    "DataQualityResource",
    "Web3Resource",
    "OrdersResource",
    "Hip4OutcomesResource",
    "L4OrderBookResource",
    "L2OrderBookResource",
    "L3OrderBookResource",
]
