"""Resource modules."""

from .candles import CandlesResource, Hip3CandlesResource, Hip4CandlesResource, SpotCandlesResource
from .data_quality import DataQualityResource
from .funding import FundingResource
from .instruments import (
    Hip3InstrumentsResource,
    Hip4InstrumentsResource,
    InstrumentsResource,
    LighterInstrumentsResource,
)
from .l2_orderbook import L2OrderBookResource
from .l3_orderbook import L3OrderBookResource
from .l4_orderbook import L4OrderBookResource
from .liquidations import LiquidationsResource
from .openinterest import Hip4OpenInterestResource, OpenInterestResource
from .orderbook import OrderBookResource
from .orders import OrdersResource
from .outcomes import Hip4OutcomesResource
from .spot import SpotPairsResource, SpotTwapResource
from .trades import TradesResource
from .web3 import Web3Resource

__all__ = [
    "OrderBookResource",
    "TradesResource",
    "InstrumentsResource",
    "LighterInstrumentsResource",
    "Hip3InstrumentsResource",
    "Hip4InstrumentsResource",
    "FundingResource",
    "OpenInterestResource",
    "Hip4OpenInterestResource",
    "CandlesResource",
    "Hip3CandlesResource",
    "Hip4CandlesResource",
    "SpotCandlesResource",
    "LiquidationsResource",
    "DataQualityResource",
    "Web3Resource",
    "OrdersResource",
    "Hip4OutcomesResource",
    "L4OrderBookResource",
    "L2OrderBookResource",
    "L3OrderBookResource",
    "SpotPairsResource",
    "SpotTwapResource",
]
