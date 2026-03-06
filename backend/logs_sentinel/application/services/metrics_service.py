"""Application service for dashboard metrics."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from logs_sentinel.api.v1.schemas.metrics import (
    DashboardMetricsResponse,
    TimeSeriesPoint,
)
from logs_sentinel.domains.metrics.repositories import MetricsRepository
from logs_sentinel.utils.dateutils import ts_to_str


class MetricsService:
    """Service for dashboard metrics."""

    def __init__(self, metrics_repo: MetricsRepository) -> None:
        self._repo = metrics_repo

    async def get_dashboard_metrics(
        self,
        *,
        tenant_id: int,
        minutes: int,
    ) -> DashboardMetricsResponse:
        since = datetime.now(UTC) - timedelta(minutes=minutes)
        bucket_minutes = 5 if minutes <= 60 else 15

        log_volume_raw = await self._repo.get_log_volume_series(
            tenant_id=tenant_id,
            since=since,
            bucket_minutes=bucket_minutes,
        )
        error_rate_raw = await self._repo.get_error_rate_series(
            tenant_id=tenant_id,
            since=since,
            bucket_minutes=bucket_minutes,
        )

        log_volume = [
            TimeSeriesPoint(ts=ts_to_str(b.ts), value=b.value)
            for b in log_volume_raw
        ]
        error_rate = [
            TimeSeriesPoint(ts=ts_to_str(b.ts), value=b.value)
            for b in error_rate_raw
        ]

        return DashboardMetricsResponse(
            log_volume=log_volume,
            error_rate=error_rate,
        )
