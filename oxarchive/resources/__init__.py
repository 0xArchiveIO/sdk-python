"""Resource modules."""

from .breadth import BreadthResource
from .candles import CandlesResource, Hip3CandlesResource, Hip4CandlesResource, SpotCandlesResource
from .cvd import CvdResource
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
from .lighter_liquidations import LighterLiquidationsResource
from .liquidations import Hip3LiquidationsResource, LiquidationsResource
from .openinterest import Hip4OpenInterestResource, OpenInterestResource
from .oracle import Hip3OracleResource
from .orderbook import OrderBookResource
from .orders import Hip4OrdersResource, OrdersResource, SpotOrdersResource
from .outcomes import Hip4OutcomesResource, Hip4QuestionsResource
from .positions import (
    HyperliquidPositionsResource,
    LighterAccountsResource,
    LighterPositionsResource,
)
from .spot import SpotPairsResource, SpotTwapResource
from .symbols import SymbolsResource
from .trades import TradesResource
from .wallets import WalletsResource
from .web3 import Web3Resource
from .webhooks import WebhooksResource

__all__ = [
    "OrderBookResource",
    "TradesResource",
    "InstrumentsResource",
    "LighterInstrumentsResource",
    "Hip3InstrumentsResource",
    "Hip4InstrumentsResource",
    "FundingResource",
    "BreadthResource",
    "OpenInterestResource",
    "Hip4OpenInterestResource",
    "CandlesResource",
    "Hip3CandlesResource",
    "Hip4CandlesResource",
    "SpotCandlesResource",
    "LiquidationsResource",
    "Hip3LiquidationsResource",
    "LighterLiquidationsResource",
    "DataQualityResource",
    "Web3Resource",
    "OrdersResource",
    "Hip4OrdersResource",
    "SpotOrdersResource",
    "Hip4OutcomesResource",
    "L4OrderBookResource",
    "L2OrderBookResource",
    "L3OrderBookResource",
    "SpotPairsResource",
    "SpotTwapResource",
    "HyperliquidPositionsResource",
    "LighterPositionsResource",
    "LighterAccountsResource",
    "CvdResource",
    "Hip3OracleResource",
    "Hip4QuestionsResource",
    "WalletsResource",
    "SymbolsResource",
    "WebhooksResource",
]
