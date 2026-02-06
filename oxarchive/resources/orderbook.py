"""Order book API resource."""

from __future__ import annotations

from datetime import datetime
from typing import AsyncIterator, Iterator, Optional, Union

from ..http import HttpClient
from typing import Literal

from ..types import CursorResponse, OrderBook, Timestamp
from ..orderbook_reconstructor import (
    OrderBookReconstructor,
    OrderbookDelta,
    TickData,
    ReconstructedOrderBook,
    ReconstructOptions,
)

# Lighter orderbook granularity levels (Lighter.xyz only)
LighterGranularity = Literal["checkpoint", "30s", "10s", "1s", "tick"]


class OrderBookResource:
    """
    Order book API resource.

    Example:
        >>> # Get current order book (Hyperliquid)
        >>> orderbook = client.hyperliquid.orderbook.get("BTC")
        >>>
        >>> # Get order book at specific timestamp
        >>> historical = client.hyperliquid.orderbook.get("ETH", timestamp=1704067200000)
        >>>
        >>> # Get order book history
        >>> history = client.hyperliquid.orderbook.history("BTC", start="2024-01-01", end="2024-01-02")
        >>>
        >>> # Lighter.xyz order book
        >>> lighter_ob = client.lighter.orderbook.get("BTC")
    """

    def __init__(self, http: HttpClient, base_path: str = "/v1"):
        self._http = http
        self._base_path = base_path

    def _convert_timestamp(self, ts: Optional[Timestamp]) -> Optional[int]:
        """Convert timestamp to Unix milliseconds."""
        if ts is None:
            return None
        if isinstance(ts, int):
            return ts
        if isinstance(ts, datetime):
            return int(ts.timestamp() * 1000)
        if isinstance(ts, str):
            # Try parsing ISO format
            try:
                dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                return int(dt.timestamp() * 1000)
            except ValueError:
                return int(ts)
        return None

    def get(
        self,
        coin: str,
        *,
        timestamp: Optional[Timestamp] = None,
        depth: Optional[int] = None,
    ) -> OrderBook:
        """
        Get order book snapshot for a coin.

        Args:
            coin: The coin symbol (e.g., 'BTC', 'ETH')
            timestamp: Optional timestamp to get historical snapshot
            depth: Number of price levels to return per side

        Returns:
            Order book snapshot
        """
        data = self._http.get(
            f"{self._base_path}/orderbook/{coin.upper()}",
            params={
                "timestamp": self._convert_timestamp(timestamp),
                "depth": depth,
            },
        )
        return OrderBook.model_validate(data["data"])

    async def aget(
        self,
        coin: str,
        *,
        timestamp: Optional[Timestamp] = None,
        depth: Optional[int] = None,
    ) -> OrderBook:
        """Async version of get()."""
        data = await self._http.aget(
            f"{self._base_path}/orderbook/{coin.upper()}",
            params={
                "timestamp": self._convert_timestamp(timestamp),
                "depth": depth,
            },
        )
        return OrderBook.model_validate(data["data"])

    def history(
        self,
        coin: str,
        *,
        start: Timestamp,
        end: Timestamp,
        cursor: Optional[Timestamp] = None,
        limit: Optional[int] = None,
        depth: Optional[int] = None,
        granularity: Optional[LighterGranularity] = None,
    ) -> CursorResponse[list[OrderBook]]:
        """
        Get historical order book snapshots with cursor-based pagination.

        Args:
            coin: The coin symbol (e.g., 'BTC', 'ETH')
            start: Start timestamp (required)
            end: End timestamp (required)
            cursor: Cursor from previous response's next_cursor (timestamp)
            limit: Maximum number of results (default: 100, max: 1000)
            depth: Number of price levels per side
            granularity: Data resolution for Lighter orderbook (Lighter.xyz only, ignored for Hyperliquid).
                Options: 'checkpoint' (1min, default), '30s', '10s', '1s', 'tick'.
                Tier restrictions apply. Credit multipliers: checkpoint=1x, 30s=2x, 10s=3x, 1s=10x, tick=20x.

        Returns:
            CursorResponse with order book snapshots and next_cursor for pagination

        Example:
            >>> result = client.orderbook.history("BTC", start=start, end=end, limit=1000)
            >>> snapshots = result.data
            >>> while result.next_cursor:
            ...     result = client.orderbook.history(
            ...         "BTC", start=start, end=end, cursor=result.next_cursor, limit=1000
            ...     )
            ...     snapshots.extend(result.data)
            >>>
            >>> # Lighter.xyz with 10s granularity (Build+ tier)
            >>> result = client.lighter.orderbook.history(
            ...     "BTC", start=start, end=end, granularity="10s"
            ... )
        """
        data = self._http.get(
            f"{self._base_path}/orderbook/{coin.upper()}/history",
            params={
                "start": self._convert_timestamp(start),
                "end": self._convert_timestamp(end),
                "cursor": self._convert_timestamp(cursor),
                "limit": limit,
                "depth": depth,
                "granularity": granularity,
            },
        )
        return CursorResponse(
            data=[OrderBook.model_validate(item) for item in data["data"]],
            next_cursor=data.get("meta", {}).get("next_cursor"),
        )

    async def ahistory(
        self,
        coin: str,
        *,
        start: Timestamp,
        end: Timestamp,
        cursor: Optional[Timestamp] = None,
        limit: Optional[int] = None,
        depth: Optional[int] = None,
        granularity: Optional[LighterGranularity] = None,
    ) -> CursorResponse[list[OrderBook]]:
        """Async version of history(). start and end are required. See history() for granularity details."""
        data = await self._http.aget(
            f"{self._base_path}/orderbook/{coin.upper()}/history",
            params={
                "start": self._convert_timestamp(start),
                "end": self._convert_timestamp(end),
                "cursor": self._convert_timestamp(cursor),
                "limit": limit,
                "depth": depth,
                "granularity": granularity,
            },
        )
        return CursorResponse(
            data=[OrderBook.model_validate(item) for item in data["data"]],
            next_cursor=data.get("meta", {}).get("next_cursor"),
        )

    def history_tick(
        self,
        coin: str,
        *,
        start: Timestamp,
        end: Timestamp,
        depth: Optional[int] = None,
    ) -> TickData:
        """
        Get raw tick-level orderbook data (Enterprise tier only).

        Returns a checkpoint (full orderbook state) and array of deltas.
        Use this when you want to implement custom reconstruction logic
        (e.g., in Rust for maximum performance).

        For automatic reconstruction, use `history_reconstructed()` instead.

        Args:
            coin: The coin symbol (e.g., 'BTC', 'ETH')
            start: Start timestamp (required)
            end: End timestamp (required)
            depth: Number of price levels in checkpoint (default: all)

        Returns:
            TickData with checkpoint and deltas

        Example:
            >>> tick_data = client.lighter.orderbook.history_tick(
            ...     "BTC",
            ...     start=datetime.now() - timedelta(hours=1),
            ...     end=datetime.now()
            ... )
            >>> print(f"Checkpoint: {tick_data.checkpoint}")
            >>> print(f"Deltas: {len(tick_data.deltas)}")
            >>>
            >>> # Implement your own reconstruction...
            >>> for delta in tick_data.deltas:
            ...     # delta: OrderbookDelta with timestamp, side, price, size, sequence
            ...     pass
        """
        response = self._http.get(
            f"{self._base_path}/orderbook/{coin.upper()}/history",
            params={
                "start": self._convert_timestamp(start),
                "end": self._convert_timestamp(end),
                "depth": depth,
                "granularity": "tick",
            },
        )

        # Check if tick-level data was returned (nested inside "data" wrapper)
        tick_data = response.get("data", {})
        if not isinstance(tick_data, dict) or "checkpoint" not in tick_data or tick_data.get("checkpoint") is None:
            error_msg = response.get("error") or response.get("message") or (
                "Tick-level orderbook data requires Enterprise tier. "
                "Upgrade your subscription or use a different granularity."
            )
            raise ValueError(error_msg)

        checkpoint = OrderBook.model_validate(tick_data["checkpoint"])
        deltas = [
            OrderbookDelta(
                timestamp=d["timestamp"],
                side=d["side"],
                price=float(d["price"]),
                size=float(d["size"]),
                sequence=d["sequence"],
            )
            for d in tick_data.get("deltas", [])
        ]

        return TickData(checkpoint=checkpoint, deltas=deltas)

    async def ahistory_tick(
        self,
        coin: str,
        *,
        start: Timestamp,
        end: Timestamp,
        depth: Optional[int] = None,
    ) -> TickData:
        """Async version of history_tick(). See history_tick() for details."""
        response = await self._http.aget(
            f"{self._base_path}/orderbook/{coin.upper()}/history",
            params={
                "start": self._convert_timestamp(start),
                "end": self._convert_timestamp(end),
                "depth": depth,
                "granularity": "tick",
            },
        )

        # Check if tick-level data was returned (nested inside "data" wrapper)
        tick_data = response.get("data", {})
        if not isinstance(tick_data, dict) or "checkpoint" not in tick_data or tick_data.get("checkpoint") is None:
            error_msg = response.get("error") or response.get("message") or (
                "Tick-level orderbook data requires Enterprise tier. "
                "Upgrade your subscription or use a different granularity."
            )
            raise ValueError(error_msg)

        checkpoint = OrderBook.model_validate(tick_data["checkpoint"])
        deltas = [
            OrderbookDelta(
                timestamp=d["timestamp"],
                side=d["side"],
                price=float(d["price"]),
                size=float(d["size"]),
                sequence=d["sequence"],
            )
            for d in tick_data.get("deltas", [])
        ]

        return TickData(checkpoint=checkpoint, deltas=deltas)

    def history_reconstructed(
        self,
        coin: str,
        *,
        start: Timestamp,
        end: Timestamp,
        depth: Optional[int] = None,
        emit_all: bool = True,
    ) -> list[ReconstructedOrderBook]:
        """
        Get reconstructed tick-level orderbook history (Enterprise tier only).

        Fetches raw tick data and reconstructs full orderbook state at each delta.
        All reconstruction happens client-side for optimal server performance.

        For large time ranges, consider using `history_tick()` with the
        `OrderBookReconstructor.iterate()` method for memory efficiency.

        Args:
            coin: The coin symbol (e.g., 'BTC', 'ETH')
            start: Start timestamp (required)
            end: End timestamp (required)
            depth: Maximum price levels to include in output
            emit_all: If True, return snapshot after every delta.
                     If False, only return final state.

        Returns:
            List of reconstructed orderbook snapshots

        Example:
            >>> # Get all snapshots
            >>> snapshots = client.lighter.orderbook.history_reconstructed(
            ...     "BTC",
            ...     start=datetime.now() - timedelta(hours=1),
            ...     end=datetime.now()
            ... )
            >>> for ob in snapshots:
            ...     print(ob.timestamp, "Best bid:", ob.bids[0].px, "Best ask:", ob.asks[0].px)
            >>>
            >>> # Get only final state
            >>> [final] = client.lighter.orderbook.history_reconstructed(
            ...     "BTC", start=start, end=end, emit_all=False
            ... )
        """
        tick_data = self.history_tick(coin, start=start, end=end, depth=depth)
        reconstructor = OrderBookReconstructor()
        options = ReconstructOptions(depth=depth, emit_all=emit_all)
        return reconstructor.reconstruct_all(tick_data.checkpoint, tick_data.deltas, options)

    async def ahistory_reconstructed(
        self,
        coin: str,
        *,
        start: Timestamp,
        end: Timestamp,
        depth: Optional[int] = None,
        emit_all: bool = True,
    ) -> list[ReconstructedOrderBook]:
        """Async version of history_reconstructed(). See history_reconstructed() for details."""
        tick_data = await self.ahistory_tick(coin, start=start, end=end, depth=depth)
        reconstructor = OrderBookReconstructor()
        options = ReconstructOptions(depth=depth, emit_all=emit_all)
        return reconstructor.reconstruct_all(tick_data.checkpoint, tick_data.deltas, options)

    def iterate_reconstructed(
        self,
        coin: str,
        *,
        start: Timestamp,
        end: Timestamp,
        depth: Optional[int] = None,
    ) -> Iterator[ReconstructedOrderBook]:
        """
        Iterate over reconstructed orderbook states (memory-efficient).

        Fetches tick data and yields snapshots one at a time.
        Use this for large time ranges to avoid loading all snapshots into memory.

        Args:
            coin: The coin symbol (e.g., 'BTC', 'ETH')
            start: Start timestamp (required)
            end: End timestamp (required)
            depth: Maximum price levels to include

        Yields:
            Reconstructed orderbook snapshots

        Example:
            >>> for snapshot in client.lighter.orderbook.iterate_reconstructed(
            ...     "BTC", start=start, end=end
            ... ):
            ...     process(snapshot)
            ...     if some_condition:
            ...         break  # Early exit if needed
        """
        tick_data = self.history_tick(coin, start=start, end=end, depth=depth)
        reconstructor = OrderBookReconstructor()
        yield from reconstructor.iterate(tick_data.checkpoint, tick_data.deltas, depth)

    def create_reconstructor(self) -> OrderBookReconstructor:
        """
        Create a reconstructor for streaming tick-level data.

        Returns an OrderBookReconstructor instance that you can use
        to process tick data incrementally or with custom logic.

        Returns:
            A new OrderBookReconstructor instance

        Example:
            >>> reconstructor = client.lighter.orderbook.create_reconstructor()
            >>> tick_data = client.lighter.orderbook.history_tick("BTC", start=start, end=end)
            >>>
            >>> # Memory-efficient iteration
            >>> for snapshot in reconstructor.iterate(tick_data.checkpoint, tick_data.deltas):
            ...     # Process each snapshot
            ...     if some_condition(snapshot):
            ...         break  # Early exit if needed
            >>>
            >>> # Check for gaps
            >>> gaps = OrderBookReconstructor.detect_gaps(tick_data.deltas)
            >>> if gaps:
            ...     print("Sequence gaps detected:", gaps)
        """
        return OrderBookReconstructor()

    def iterate_tick_history(
        self,
        coin: str,
        *,
        start: Timestamp,
        end: Timestamp,
        depth: Optional[int] = None,
    ) -> Iterator[ReconstructedOrderBook]:
        """
        Iterate over tick-level orderbook history with automatic pagination (Enterprise tier only).

        This generator automatically handles pagination, fetching up to 1,000 deltas
        per API request and yielding reconstructed orderbook snapshots one at a time.
        Memory-efficient for processing large time ranges.

        Args:
            coin: The coin symbol (e.g., 'BTC', 'ETH')
            start: Start timestamp (required)
            end: End timestamp (required)
            depth: Maximum price levels to include in output snapshots

        Yields:
            Reconstructed orderbook snapshots

        Example:
            >>> # Process 24 hours of tick data with automatic pagination
            >>> for snapshot in client.lighter.orderbook.iterate_tick_history(
            ...     "BTC",
            ...     start=datetime.now() - timedelta(days=1),
            ...     end=datetime.now()
            ... ):
            ...     print(snapshot.timestamp, "Mid:", snapshot.mid_price)
            ...     if some_condition:
            ...         break  # Early exit supported
            >>>
            >>> # Collect all snapshots (caution: memory usage for large ranges)
            >>> snapshots = list(client.lighter.orderbook.iterate_tick_history(
            ...     "BTC", start=start, end=end
            ... ))
        """
        start_ts = self._convert_timestamp(start)
        end_ts = self._convert_timestamp(end)
        if start_ts is None or end_ts is None:
            raise ValueError("start and end timestamps are required")

        cursor = start_ts
        reconstructor = OrderBookReconstructor()
        max_deltas_per_page = 1000
        is_first_page = True

        while cursor < end_ts:
            tick_data = self.history_tick(coin, start=cursor, end=end_ts, depth=depth)

            if len(tick_data.deltas) == 0:
                # No deltas - yield checkpoint only on first page if no data
                if is_first_page:
                    reconstructor.initialize(tick_data.checkpoint)
                    yield reconstructor.get_snapshot(depth)
                break

            # Yield each reconstructed snapshot
            # Skip initial checkpoint on subsequent pages to avoid duplicates
            skip_first = not is_first_page
            for snapshot in reconstructor.iterate(tick_data.checkpoint, tick_data.deltas, depth):
                if skip_first:
                    skip_first = False
                    continue
                yield snapshot

            is_first_page = False

            # Move cursor past the last delta
            last_delta = tick_data.deltas[-1]
            cursor = last_delta.timestamp + 1

            # If we got fewer than max deltas, we've reached the end
            if len(tick_data.deltas) < max_deltas_per_page:
                break

    async def aiterate_tick_history(
        self,
        coin: str,
        *,
        start: Timestamp,
        end: Timestamp,
        depth: Optional[int] = None,
    ) -> AsyncIterator[ReconstructedOrderBook]:
        """
        Async iterate over tick-level orderbook history with automatic pagination (Enterprise tier only).

        This async generator automatically handles pagination, fetching up to 1,000 deltas
        per API request and yielding reconstructed orderbook snapshots one at a time.
        Memory-efficient for processing large time ranges.

        Args:
            coin: The coin symbol (e.g., 'BTC', 'ETH')
            start: Start timestamp (required)
            end: End timestamp (required)
            depth: Maximum price levels to include in output snapshots

        Yields:
            Reconstructed orderbook snapshots

        Example:
            >>> # Process 24 hours of tick data with automatic pagination
            >>> async for snapshot in client.lighter.orderbook.aiterate_tick_history(
            ...     "BTC",
            ...     start=datetime.now() - timedelta(days=1),
            ...     end=datetime.now()
            ... ):
            ...     print(snapshot.timestamp, "Mid:", snapshot.mid_price)
            ...     if some_condition:
            ...         break  # Early exit supported
        """
        start_ts = self._convert_timestamp(start)
        end_ts = self._convert_timestamp(end)
        if start_ts is None or end_ts is None:
            raise ValueError("start and end timestamps are required")

        cursor = start_ts
        reconstructor = OrderBookReconstructor()
        max_deltas_per_page = 1000
        is_first_page = True

        while cursor < end_ts:
            tick_data = await self.ahistory_tick(coin, start=cursor, end=end_ts, depth=depth)

            if len(tick_data.deltas) == 0:
                # No deltas - yield checkpoint only on first page if no data
                if is_first_page:
                    reconstructor.initialize(tick_data.checkpoint)
                    yield reconstructor.get_snapshot(depth)
                break

            # Yield each reconstructed snapshot
            # Skip initial checkpoint on subsequent pages to avoid duplicates
            skip_first = not is_first_page
            for snapshot in reconstructor.iterate(tick_data.checkpoint, tick_data.deltas, depth):
                if skip_first:
                    skip_first = False
                    continue
                yield snapshot

            is_first_page = False

            # Move cursor past the last delta
            last_delta = tick_data.deltas[-1]
            cursor = last_delta.timestamp + 1

            # If we got fewer than max deltas, we've reached the end
            if len(tick_data.deltas) < max_deltas_per_page:
                break
