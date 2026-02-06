"""
Orderbook Reconstructor for tick-level delta data.

Efficiently reconstructs full orderbook state from checkpoint + deltas.
All reconstruction happens client-side for optimal server performance.

Example:
    >>> from oxarchive import Client
    >>> from oxarchive.orderbook_reconstructor import OrderBookReconstructor
    >>>
    >>> client = Client(api_key="your_api_key")
    >>>
    >>> # Get raw tick data
    >>> tick_data = client.lighter.orderbook.history_tick("BTC", start=start, end=end)
    >>>
    >>> # Reconstruct to get snapshots at each delta
    >>> reconstructor = OrderBookReconstructor()
    >>> snapshots = reconstructor.reconstruct_all(tick_data.checkpoint, tick_data.deltas)
    >>>
    >>> # Or iterate efficiently (memory-friendly for large datasets)
    >>> for snapshot in reconstructor.iterate(tick_data.checkpoint, tick_data.deltas):
    ...     print(snapshot.timestamp, snapshot.bids[0], snapshot.asks[0])
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Iterator, Optional

from .types import OrderBook, PriceLevel


@dataclass
class OrderbookDelta:
    """A single orderbook delta/change."""

    timestamp: int
    """Timestamp in milliseconds"""

    side: str
    """Side: 'bid' or 'ask'"""

    price: float
    """Price level"""

    size: float
    """New size (0 = level removed)"""

    sequence: int
    """Sequence number for ordering"""


@dataclass
class TickData:
    """Raw tick data from the API (checkpoint + deltas)."""

    checkpoint: OrderBook
    """Initial orderbook state"""

    deltas: list[OrderbookDelta]
    """Incremental changes to apply"""


@dataclass
class ReconstructedOrderBook:
    """Reconstructed orderbook snapshot with sequence info."""

    coin: str
    timestamp: str
    bids: list[PriceLevel]
    asks: list[PriceLevel]
    mid_price: Optional[str] = None
    spread: Optional[str] = None
    spread_bps: Optional[str] = None
    sequence: Optional[int] = None


@dataclass
class ReconstructOptions:
    """Options for reconstruction."""

    depth: Optional[int] = None
    """Maximum depth (price levels) to include in output. Default: all levels"""

    emit_all: bool = True
    """If True, yield a snapshot after every delta. If False, only return final state."""


@dataclass
class InternalLevel:
    """Price level stored internally with numeric values."""

    price: float
    size: float
    orders: int = 1


class OrderBookReconstructor:
    """
    Orderbook Reconstructor.

    Maintains orderbook state and efficiently applies delta updates.
    Uses dictionaries with sorted output for O(1) updates.

    Example:
        >>> reconstructor = OrderBookReconstructor()
        >>> snapshots = reconstructor.reconstruct_all(checkpoint, deltas)
        >>>
        >>> # Or iterate for memory efficiency
        >>> for snapshot in reconstructor.iterate(checkpoint, deltas):
        ...     process(snapshot)
    """

    def __init__(self) -> None:
        self._bids: dict[float, InternalLevel] = {}
        self._asks: dict[float, InternalLevel] = {}
        self._coin: str = ""
        self._last_timestamp: str = ""
        self._last_sequence: int = 0

    def initialize(self, checkpoint: OrderBook) -> None:
        """Initialize or reset the reconstructor with a checkpoint."""
        self._bids.clear()
        self._asks.clear()
        self._coin = checkpoint.coin
        self._last_timestamp = checkpoint.timestamp
        self._last_sequence = 0

        # Parse checkpoint bids
        for level in checkpoint.bids:
            price = float(level.px)
            self._bids[price] = InternalLevel(
                price=price,
                size=float(level.sz),
                orders=level.n,
            )

        # Parse checkpoint asks
        for level in checkpoint.asks:
            price = float(level.px)
            self._asks[price] = InternalLevel(
                price=price,
                size=float(level.sz),
                orders=level.n,
            )

    def apply_delta(self, delta: OrderbookDelta) -> None:
        """Apply a single delta to the current state."""
        book = self._bids if delta.side == "bid" else self._asks

        if delta.size == 0:
            # Remove level
            book.pop(delta.price, None)
        else:
            # Insert or update level
            book[delta.price] = InternalLevel(
                price=delta.price,
                size=delta.size,
                orders=1,  # Deltas don't include order count
            )

        # Convert timestamp to ISO format (timezone-aware)
        self._last_timestamp = datetime.fromtimestamp(delta.timestamp / 1000, tz=timezone.utc).isoformat().replace("+00:00", "Z")
        self._last_sequence = delta.sequence

    def get_snapshot(self, depth: Optional[int] = None) -> ReconstructedOrderBook:
        """Get the current orderbook state as a snapshot."""
        # Sort bids descending (best bid first)
        sorted_bids = sorted(self._bids.values(), key=lambda x: x.price, reverse=True)

        # Sort asks ascending (best ask first)
        sorted_asks = sorted(self._asks.values(), key=lambda x: x.price)

        # Apply depth limit
        if depth:
            sorted_bids = sorted_bids[:depth]
            sorted_asks = sorted_asks[:depth]

        bids_output = [self._to_level(level) for level in sorted_bids]
        asks_output = [self._to_level(level) for level in sorted_asks]

        # Calculate mid price and spread
        best_bid = sorted_bids[0].price if sorted_bids else None
        best_ask = sorted_asks[0].price if sorted_asks else None

        mid_price = None
        spread = None
        spread_bps = None

        if best_bid is not None and best_ask is not None:
            mid_price = (best_bid + best_ask) / 2
            spread = best_ask - best_bid
            spread_bps = (spread / mid_price) * 10000 if mid_price else None

        return ReconstructedOrderBook(
            coin=self._coin,
            timestamp=self._last_timestamp,
            bids=bids_output,
            asks=asks_output,
            mid_price=str(mid_price) if mid_price is not None else None,
            spread=str(spread) if spread is not None else None,
            spread_bps=f"{spread_bps:.2f}" if spread_bps is not None else None,
            sequence=self._last_sequence,
        )

    def _to_level(self, level: InternalLevel) -> PriceLevel:
        """Convert internal level to API format."""
        return PriceLevel(
            px=str(level.price),
            sz=str(level.size),
            n=level.orders,
        )

    def reconstruct_all(
        self,
        checkpoint: OrderBook,
        deltas: list[OrderbookDelta],
        options: Optional[ReconstructOptions] = None,
    ) -> list[ReconstructedOrderBook]:
        """
        Reconstruct all orderbook states from checkpoint + deltas.

        Returns an array of snapshots, one after each delta.
        For large datasets, prefer `iterate()` to avoid memory issues.

        Args:
            checkpoint: Initial orderbook state
            deltas: Array of delta updates
            options: Reconstruction options

        Returns:
            Array of reconstructed orderbook snapshots
        """
        options = options or ReconstructOptions()
        snapshots: list[ReconstructedOrderBook] = []

        self.initialize(checkpoint)

        # Sort deltas by sequence to ensure correct order
        sorted_deltas = sorted(deltas, key=lambda d: d.sequence)

        if options.emit_all:
            # Emit initial state
            snapshots.append(self.get_snapshot(options.depth))

        for delta in sorted_deltas:
            self.apply_delta(delta)
            if options.emit_all:
                snapshots.append(self.get_snapshot(options.depth))

        if not options.emit_all:
            # Only return final state
            snapshots.append(self.get_snapshot(options.depth))

        return snapshots

    def iterate(
        self,
        checkpoint: OrderBook,
        deltas: list[OrderbookDelta],
        depth: Optional[int] = None,
    ) -> Iterator[ReconstructedOrderBook]:
        """
        Iterate over reconstructed orderbook states (memory-efficient).

        Yields a snapshot after each delta is applied.

        Args:
            checkpoint: Initial orderbook state
            deltas: Array of delta updates
            depth: Maximum price levels to include

        Yields:
            Reconstructed orderbook snapshots
        """
        self.initialize(checkpoint)

        # Yield initial state
        yield self.get_snapshot(depth)

        # Sort deltas by sequence
        sorted_deltas = sorted(deltas, key=lambda d: d.sequence)

        for delta in sorted_deltas:
            self.apply_delta(delta)
            yield self.get_snapshot(depth)

    def reconstruct_final(
        self,
        checkpoint: OrderBook,
        deltas: list[OrderbookDelta],
        depth: Optional[int] = None,
    ) -> ReconstructedOrderBook:
        """
        Get the final reconstructed state without intermediate snapshots.

        Most efficient when you only need the end result.

        Args:
            checkpoint: Initial orderbook state
            deltas: Array of delta updates
            depth: Maximum price levels to include

        Returns:
            Final orderbook state after all deltas applied
        """
        self.initialize(checkpoint)

        # Sort and apply all deltas
        sorted_deltas = sorted(deltas, key=lambda d: d.sequence)
        for delta in sorted_deltas:
            self.apply_delta(delta)

        return self.get_snapshot(depth)

    @staticmethod
    def detect_gaps(deltas: list[OrderbookDelta]) -> list[tuple[int, int]]:
        """
        Check for sequence gaps in deltas.

        Args:
            deltas: Array of delta updates

        Returns:
            List of (expected_seq, actual_seq) tuples where gaps exist
        """
        if len(deltas) < 2:
            return []

        sorted_deltas = sorted(deltas, key=lambda d: d.sequence)
        gaps: list[tuple[int, int]] = []

        for i in range(1, len(sorted_deltas)):
            expected = sorted_deltas[i - 1].sequence + 1
            actual = sorted_deltas[i].sequence
            if actual != expected:
                gaps.append((expected, actual))

        return gaps


def reconstruct_orderbook(
    tick_data: TickData,
    options: Optional[ReconstructOptions] = None,
) -> list[ReconstructedOrderBook]:
    """
    Convenience function for one-shot reconstruction.

    Creates a new reconstructor, processes data, and returns snapshots.

    Args:
        tick_data: Checkpoint and deltas from API
        options: Reconstruction options

    Returns:
        Array of reconstructed orderbook snapshots
    """
    reconstructor = OrderBookReconstructor()
    return reconstructor.reconstruct_all(tick_data.checkpoint, tick_data.deltas, options)


def reconstruct_final(
    tick_data: TickData,
    depth: Optional[int] = None,
) -> ReconstructedOrderBook:
    """
    Convenience function to get final orderbook state.

    Args:
        tick_data: Checkpoint and deltas from API
        depth: Maximum price levels

    Returns:
        Final orderbook state
    """
    reconstructor = OrderBookReconstructor()
    return reconstructor.reconstruct_final(tick_data.checkpoint, tick_data.deltas, depth)
