"""SQLAlchemy implementation of metrics repository."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Integer, case, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from logs_sentinel.domains.metrics.entities import TimeSeriesBucket
from logs_sentinel.infrastructure.db.models import LogEventModel


class MetricsRepositorySQLAlchemy:
    """MetricsRepository implementation for dashboard metrics."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_log_volume_series(
        self,
        *,
        tenant_id: int,
        since: datetime,
        bucket_minutes: int,
    ) -> list[TimeSeriesBucket]:
        bucket_seconds = bucket_minutes * 60
        epoch = func.extract("epoch", LogEventModel.received_at)
        bucket_epoch = cast(epoch / bucket_seconds, Integer) * bucket_seconds
        ts_expr = func.to_timestamp(bucket_epoch)

        stmt = (
            select(ts_expr.label("ts"), func.count().label("value"))
            .where(
                LogEventModel.tenant_id == tenant_id,
                LogEventModel.received_at >= since,
            )
            .group_by(bucket_epoch)
            .order_by(bucket_epoch)
        )
        result = await self._session.execute(stmt)
        return [
            TimeSeriesBucket(
                ts=row.ts,
                value=float(row.value),
            )
            for row in result.all()
        ]

    async def get_error_rate_series(
        self,
        *,
        tenant_id: int,
        since: datetime,
        bucket_minutes: int,
    ) -> list[TimeSeriesBucket]:
        bucket_seconds = bucket_minutes * 60
        epoch = func.extract("epoch", LogEventModel.received_at)
        bucket_epoch = cast(epoch / bucket_seconds, Integer) * bucket_seconds
        ts_expr = func.to_timestamp(bucket_epoch)

        stmt = (
            select(
                ts_expr.label("ts"),
                func.count().label("total"),
                func.sum(case((LogEventModel.level == "error", 1), else_=0)).label("errors"),
            )
            .where(
                LogEventModel.tenant_id == tenant_id,
                LogEventModel.received_at >= since,
            )
            .group_by(bucket_epoch)
            .order_by(bucket_epoch)
        )
        result = await self._session.execute(stmt)
        buckets: list[TimeSeriesBucket] = []
        for row in result.all():
            total = float(row.total or 0)
            errors = float(row.errors or 0)
            pct = (100.0 * errors / total) if total else 0.0
            buckets.append(TimeSeriesBucket(ts=row.ts, value=round(pct, 2)))
        return buckets
