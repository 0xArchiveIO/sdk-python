"""
L4 order book reconstructor with matching engine.

Reconstructs Hyperliquid and HIP-3 L4 order books from checkpoints and diffs.
The same class works for both exchanges — the diff format is identical.

The key insight: when a new order crosses the spread, the matching engine filled
opposite-side orders at crossing prices. Without removing them, the reconstructed
book will be "crossed" (best bid > best ask).

Ref: https://github.com/hyperliquid-dex/order_book_server
     server/src/order_book/mod.rs — add_order() + match_order()
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class L4Order:
    oid: int
    user_address: str
    side: str  # "B" or "A"
    price: float
    size: float


@dataclass
class L2Level:
    px: float
    sz: float
    n: int


class L4OrderBookReconstructor:
    """
    L4 orderbook reconstructor with matching engine.

    Works identically for Hyperliquid and HIP-3 — same diff format,
    same checkpoint format, same crossing logic.

    Usage:
        book = L4OrderBookReconstructor()
        book.load_checkpoint(checkpoint_data)

        # Group diffs by block, apply in order
        for block_number in sorted(blocks):
            non_resting = non_resting_by_block.get(block_number)
            for diff in blocks[block_number]:
                book.apply_diff(diff, non_resting)

        assert not book.is_crossed()
        l2_bids, l2_asks = book.derive_l2()
    """

    def __init__(self):
        self._orders: dict[int, L4Order] = {}
        # price -> set of OIDs (for efficient crossing lookups)
        self._bid_prices: dict[float, set[int]] = {}
        self._ask_prices: dict[float, set[int]] = {}

    def load_checkpoint(self, checkpoint) -> None:
        """
        Initialize from an L4 checkpoint.

        Args:
            checkpoint: Dict or object with 'bids' and 'asks' lists.
                        Each order needs: oid, side, price, size, user_address.
        """
        self._orders.clear()
        self._bid_prices.clear()
        self._ask_prices.clear()

        if isinstance(checkpoint, dict):
            bids = checkpoint.get("bids", [])
            asks = checkpoint.get("asks", [])
        else:
            bids = getattr(checkpoint, "bids", [])
            asks = getattr(checkpoint, "asks", [])

        for order in list(bids) + list(asks):
            if isinstance(order, dict):
                oid = int(order["oid"])
                side = order["side"]
                price = float(order["price"])
                size = float(order["size"])
                user_address = order.get("user_address", "")
            else:
                oid = int(order.oid)
                side = order.side
                price = float(order.price)
                size = float(order.size)
                user_address = getattr(order, "user_address", "")

            self._orders[oid] = L4Order(
                oid=oid,
                user_address=user_address,
                side=side,
                price=price,
                size=size,
            )
            if side == "B":
                self._bid_prices.setdefault(price, set()).add(oid)
            else:
                self._ask_prices.setdefault(price, set()).add(oid)

    def apply_diff(self, diff, non_resting_oids: Optional[set[int]] = None) -> None:
        """
        Apply a single L4 diff with matching engine.

        Args:
            diff: Dict or object with: diff_type, oid, side, price, new_size, user_address.
            non_resting_oids: Set of OIDs that were filled/canceled in the same block.
                              Pass to filter out non-resting orders for accuracy.
        """
        if isinstance(diff, dict):
            dt = diff.get("diff_type", "")
            oid = int(diff["oid"])
            side = diff.get("side", "")
            price = float(diff.get("price", 0))
            new_size = diff.get("new_size")
            user_address = diff.get("user_address", "")
        else:
            dt = getattr(diff, "diff_type", "")
            oid = int(diff.oid)
            side = getattr(diff, "side", "")
            price = float(getattr(diff, "price", 0))
            new_size = getattr(diff, "new_size", None)
            user_address = getattr(diff, "user_address", "")

        if dt == "new":
            # Skip non-resting orders (filled/canceled in same block)
            if non_resting_oids and oid in non_resting_oids:
                return

            if new_size is None or float(new_size) <= 0:
                return

            sz = float(new_size)

            # Matching engine: remove crossing opposite-side orders.
            if side == "B":
                to_remove = [px for px in self._ask_prices if px <= price]
                for px in to_remove:
                    for crossed_oid in self._ask_prices.pop(px, set()):
                        self._orders.pop(crossed_oid, None)
            else:
                to_remove = [px for px in self._bid_prices if px >= price]
                for px in to_remove:
                    for crossed_oid in self._bid_prices.pop(px, set()):
                        self._orders.pop(crossed_oid, None)

            # Insert the new order
            self._orders[oid] = L4Order(
                oid=oid,
                user_address=user_address,
                side=side,
                price=price,
                size=sz,
            )
            if side == "B":
                self._bid_prices.setdefault(price, set()).add(oid)
            else:
                self._ask_prices.setdefault(price, set()).add(oid)

        elif dt == "update":
            if oid in self._orders and new_size is not None:
                self._orders[oid].size = float(new_size)

        elif dt == "remove":
            order = self._orders.pop(oid, None)
            if order:
                px = order.price
                if order.side == "B":
                    if px in self._bid_prices:
                        self._bid_prices[px].discard(oid)
                        if not self._bid_prices[px]:
                            del self._bid_prices[px]
                else:
                    if px in self._ask_prices:
                        self._ask_prices[px].discard(oid)
                        if not self._ask_prices[px]:
                            del self._ask_prices[px]

    def bids(self) -> list[L4Order]:
        """Return bids sorted by price descending."""
        return sorted(
            [o for o in self._orders.values() if o.side == "B" and o.size > 0],
            key=lambda x: -x.price,
        )

    def asks(self) -> list[L4Order]:
        """Return asks sorted by price ascending."""
        return sorted(
            [o for o in self._orders.values() if o.side == "A" and o.size > 0],
            key=lambda x: x.price,
        )

    def best_bid(self) -> Optional[float]:
        bids = self.bids()
        return bids[0].price if bids else None

    def best_ask(self) -> Optional[float]:
        asks = self.asks()
        return asks[0].price if asks else None

    def is_crossed(self) -> bool:
        """Check if the book is crossed (best bid >= best ask). Should be False after correct reconstruction."""
        bb, ba = self.best_bid(), self.best_ask()
        return bb is not None and ba is not None and bb >= ba

    @property
    def bid_count(self) -> int:
        return sum(1 for o in self._orders.values() if o.side == "B" and o.size > 0)

    @property
    def ask_count(self) -> int:
        return sum(1 for o in self._orders.values() if o.side == "A" and o.size > 0)

    def derive_l2(self) -> tuple[list[L2Level], list[L2Level]]:
        """
        Aggregate L4 orders into L2 price levels.

        Returns:
            (bid_levels, ask_levels) — each sorted by price (bids descending, asks ascending).
            Each level has: px (price), sz (total size), n (number of orders).
        """
        bid_agg: dict[float, list[float, int]] = {}
        ask_agg: dict[float, list[float, int]] = {}

        for o in self._orders.values():
            if o.size <= 0:
                continue
            if o.side == "B":
                if o.price not in bid_agg:
                    bid_agg[o.price] = [0.0, 0]
                bid_agg[o.price][0] += o.size
                bid_agg[o.price][1] += 1
            else:
                if o.price not in ask_agg:
                    ask_agg[o.price] = [0.0, 0]
                ask_agg[o.price][0] += o.size
                ask_agg[o.price][1] += 1

        l2_bids = [L2Level(px=px, sz=v[0], n=v[1]) for px, v in sorted(bid_agg.items(), reverse=True)]
        l2_asks = [L2Level(px=px, sz=v[0], n=v[1]) for px, v in sorted(ask_agg.items())]
        return l2_bids, l2_asks
