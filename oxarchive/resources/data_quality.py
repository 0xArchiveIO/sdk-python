"""Data quality API resource."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from ..http import HttpClient
from ..types import (
    CoverageResponse,
    ExchangeCoverage,
    Incident,
    IncidentsResponse,
    LatencyResponse,
    SlaResponse,
    StatusResponse,
    SymbolCoverageResponse,
    Timestamp,
)


class DataQualityResource:
    """
    Data quality API resource.

    Provides endpoints for monitoring data quality, coverage, incidents, and SLA metrics.

    Example:
        >>> # Get system status
        >>> status = client.data_quality.status()
        >>> print(f"System status: {status.status}")
        >>>
        >>> # Get coverage for all exchanges
        >>> coverage = client.data_quality.coverage()
        >>>
        >>> # Get symbol-specific coverage with gap detection
        >>> btc = client.data_quality.symbol_coverage("hyperliquid", "BTC")
        >>> print(f"BTC completeness: {btc.data_types['orderbook'].completeness}%")
        >>> for gap in btc.data_types['orderbook'].gaps[:5]:
        ...     print(f"Gap: {gap.start} - {gap.end} ({gap.duration_minutes} min)")
    """

    def __init__(self, http: HttpClient, base_path: str = "/v1/data-quality"):
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
            try:
                dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                return int(dt.timestamp() * 1000)
            except ValueError:
                return int(ts)
        return None

    # =========================================================================
    # Status Endpoints
    # =========================================================================

    def status(self) -> StatusResponse:
        """
        Get overall system health status.

        Returns:
            StatusResponse with overall status, per-exchange status,
            per-data-type status, and active incident count.

        Example:
            >>> status = client.data_quality.status()
            >>> print(f"Overall: {status.status}")
            >>> for exchange, info in status.exchanges.items():
            ...     print(f"{exchange}: {info.status}")
        """
        data = self._http.get(f"{self._base_path}/status")
        return StatusResponse.model_validate(data)

    async def astatus(self) -> StatusResponse:
        """Async version of status()."""
        data = await self._http.aget(f"{self._base_path}/status")
        return StatusResponse.model_validate(data)

    # =========================================================================
    # Coverage Endpoints
    # =========================================================================

    def coverage(self) -> CoverageResponse:
        """
        Get data coverage summary for all exchanges.

        Returns:
            CoverageResponse with coverage info for all exchanges and data types.

        Example:
            >>> coverage = client.data_quality.coverage()
            >>> for exchange in coverage.exchanges:
            ...     print(f"{exchange.exchange}:")
            ...     for dtype, info in exchange.data_types.items():
            ...         print(f"  {dtype}: {info.total_records} records")
        """
        data = self._http.get(f"{self._base_path}/coverage")
        return CoverageResponse.model_validate(data)

    async def acoverage(self) -> CoverageResponse:
        """Async version of coverage()."""
        data = await self._http.aget(f"{self._base_path}/coverage")
        return CoverageResponse.model_validate(data)

    def exchange_coverage(self, exchange: str) -> ExchangeCoverage:
        """
        Get data coverage for a specific exchange.

        Args:
            exchange: Exchange name ('hyperliquid' or 'lighter')

        Returns:
            ExchangeCoverage with coverage info for all data types on this exchange.

        Example:
            >>> hl = client.data_quality.exchange_coverage("hyperliquid")
            >>> print(f"Orderbook earliest: {hl.data_types['orderbook'].earliest}")
        """
        data = self._http.get(f"{self._base_path}/coverage/{exchange.lower()}")
        return ExchangeCoverage.model_validate(data)

    async def aexchange_coverage(self, exchange: str) -> ExchangeCoverage:
        """Async version of exchange_coverage()."""
        data = await self._http.aget(f"{self._base_path}/coverage/{exchange.lower()}")
        return ExchangeCoverage.model_validate(data)

    def symbol_coverage(
        self,
        exchange: str,
        symbol: str,
        *,
        from_time: Optional[Timestamp] = None,
        to_time: Optional[Timestamp] = None,
    ) -> SymbolCoverageResponse:
        """
        Get data coverage for a specific symbol on an exchange.

        Includes gap detection, empirical data cadence, and hour-level
        historical coverage.

        Args:
            exchange: Exchange name ('hyperliquid' or 'lighter')
            symbol: Symbol name (e.g., 'BTC', 'ETH')
            from_time: Start of gap detection window (default: now - 30 days).
                Accepts Unix ms, datetime, or ISO string.
            to_time: End of gap detection window (default: now).
                Accepts Unix ms, datetime, or ISO string.

        Returns:
            SymbolCoverageResponse with per-data-type coverage including gaps,
            cadence, and historical coverage.

        Example:
            >>> btc = client.data_quality.symbol_coverage("hyperliquid", "BTC")
            >>> oi = btc.data_types["open_interest"]
            >>> print(f"OI completeness: {oi.completeness}%")
            >>> print(f"Gaps found: {len(oi.gaps)}")
            >>> for gap in oi.gaps[:3]:
            ...     print(f"  {gap.duration_minutes} min gap at {gap.start}")
            >>>
            >>> # With time bounds (last 7 days)
            >>> from datetime import datetime, timedelta, timezone
            >>> week_ago = datetime.now(timezone.utc) - timedelta(days=7)
            >>> btc = client.data_quality.symbol_coverage(
            ...     "hyperliquid", "BTC", from_time=week_ago
            ... )
            >>> if btc.data_types["orderbook"].cadence:
            ...     print(f"Cadence: {btc.data_types['orderbook'].cadence.median_interval_seconds}s")
        """
        data = self._http.get(
            f"{self._base_path}/coverage/{exchange.lower()}/{symbol.upper()}",
            params={
                "from": self._convert_timestamp(from_time),
                "to": self._convert_timestamp(to_time),
            },
        )
        return SymbolCoverageResponse.model_validate(data)

    async def asymbol_coverage(
        self,
        exchange: str,
        symbol: str,
        *,
        from_time: Optional[Timestamp] = None,
        to_time: Optional[Timestamp] = None,
    ) -> SymbolCoverageResponse:
        """Async version of symbol_coverage()."""
        data = await self._http.aget(
            f"{self._base_path}/coverage/{exchange.lower()}/{symbol.upper()}",
            params={
                "from": self._convert_timestamp(from_time),
                "to": self._convert_timestamp(to_time),
            },
        )
        return SymbolCoverageResponse.model_validate(data)

    # =========================================================================
    # Incidents Endpoints
    # =========================================================================

    def list_incidents(
        self,
        *,
        status: Optional[Literal["open", "investigating", "identified", "monitoring", "resolved"]] = None,
        exchange: Optional[str] = None,
        since: Optional[Timestamp] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> IncidentsResponse:
        """
        List incidents with filtering and pagination.

        Args:
            status: Filter by incident status
            exchange: Filter by exchange
            since: Only show incidents starting after this timestamp
            limit: Maximum results per page (default: 20, max: 100)
            offset: Pagination offset

        Returns:
            IncidentsResponse with list of incidents and pagination info.

        Example:
            >>> # Get all open incidents
            >>> result = client.data_quality.list_incidents(status="open")
            >>> for incident in result.incidents:
            ...     print(f"{incident.severity}: {incident.title}")
        """
        data = self._http.get(
            f"{self._base_path}/incidents",
            params={
                "status": status,
                "exchange": exchange,
                "since": self._convert_timestamp(since),
                "limit": limit,
                "offset": offset,
            },
        )
        return IncidentsResponse.model_validate(data)

    async def alist_incidents(
        self,
        *,
        status: Optional[Literal["open", "investigating", "identified", "monitoring", "resolved"]] = None,
        exchange: Optional[str] = None,
        since: Optional[Timestamp] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> IncidentsResponse:
        """Async version of list_incidents()."""
        data = await self._http.aget(
            f"{self._base_path}/incidents",
            params={
                "status": status,
                "exchange": exchange,
                "since": self._convert_timestamp(since),
                "limit": limit,
                "offset": offset,
            },
        )
        return IncidentsResponse.model_validate(data)

    def get_incident(self, incident_id: str) -> Incident:
        """
        Get a specific incident by ID.

        Args:
            incident_id: The incident ID

        Returns:
            Incident details.

        Example:
            >>> incident = client.data_quality.get_incident("inc_123")
            >>> print(f"Status: {incident.status}")
            >>> print(f"Root cause: {incident.root_cause}")
        """
        data = self._http.get(f"{self._base_path}/incidents/{incident_id}")
        return Incident.model_validate(data)

    async def aget_incident(self, incident_id: str) -> Incident:
        """Async version of get_incident()."""
        data = await self._http.aget(f"{self._base_path}/incidents/{incident_id}")
        return Incident.model_validate(data)

    # =========================================================================
    # Latency Endpoints
    # =========================================================================

    def latency(self) -> LatencyResponse:
        """
        Get current latency metrics for all exchanges.

        Returns:
            LatencyResponse with WebSocket, REST API, and data freshness metrics.

        Example:
            >>> latency = client.data_quality.latency()
            >>> for exchange, metrics in latency.exchanges.items():
            ...     print(f"{exchange}:")
            ...     if metrics.websocket:
            ...         print(f"  WS current: {metrics.websocket.current_ms}ms")
            ...     print(f"  OB lag: {metrics.data_freshness.orderbook_lag_ms}ms")
        """
        data = self._http.get(f"{self._base_path}/latency")
        return LatencyResponse.model_validate(data)

    async def alatency(self) -> LatencyResponse:
        """Async version of latency()."""
        data = await self._http.aget(f"{self._base_path}/latency")
        return LatencyResponse.model_validate(data)

    # =========================================================================
    # SLA Endpoints
    # =========================================================================

    def sla(
        self,
        *,
        year: Optional[int] = None,
        month: Optional[int] = None,
    ) -> SlaResponse:
        """
        Get SLA compliance metrics for a specific month.

        Args:
            year: Year (defaults to current year)
            month: Month 1-12 (defaults to current month)

        Returns:
            SlaResponse with SLA targets, actual metrics, and compliance status.

        Example:
            >>> sla = client.data_quality.sla(year=2026, month=1)
            >>> print(f"Period: {sla.period}")
            >>> print(f"Uptime: {sla.actual.uptime}% ({sla.actual.uptime_status})")
            >>> print(f"Completeness: {sla.actual.data_completeness.overall}%")
            >>> print(f"API P99: {sla.actual.api_latency_p99_ms}ms")
        """
        data = self._http.get(
            f"{self._base_path}/sla",
            params={
                "year": year,
                "month": month,
            },
        )
        return SlaResponse.model_validate(data)

    async def asla(
        self,
        *,
        year: Optional[int] = None,
        month: Optional[int] = None,
    ) -> SlaResponse:
        """Async version of sla()."""
        data = await self._http.aget(
            f"{self._base_path}/sla",
            params={
                "year": year,
                "month": month,
            },
        )
        return SlaResponse.model_validate(data)
