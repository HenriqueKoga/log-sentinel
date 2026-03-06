"""Repository protocol for metrics API."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from logs_sentinel.domains.metrics.entities import TimeSeriesBucket


class MetricsRepository(Protocol):
    """Repository for dashboard metrics (log volume, error rate)."""

    async def get_log_volume_series(
        self,
        *,
        tenant_id: int,
        since: datetime,
        bucket_minutes: int,
    ) -> list[TimeSeriesBucket]:
        """Return time series of log count per bucket."""

    async def get_error_rate_series(
        self,
        *,
        tenant_id: int,
        since: datetime,
        bucket_minutes: int,
    ) -> list[TimeSeriesBucket]:
        """Return time series of error percentage per bucket (value 0-100)."""
