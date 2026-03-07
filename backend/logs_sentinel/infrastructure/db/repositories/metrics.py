"""SQLAlchemy implementation of metrics repository."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Integer, case, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from logs_sentinel.domains.metrics.entities import TimeSeriesBucket
from logs_sentinel.infrastructure.db.models import LogEventModel
from logs_sentinel.utils.dateutils import normalize_ts


class MetricsRepositorySQLAlchemy:
    """MetricsRepository implementation for dashboard metrics.
    Supports PostgreSQL and SQLite (for tests) via dialect-aware expressions.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _bucket_exprs(self, bucket_seconds: int) -> tuple[Any, Any]:
        """Return (bucket_epoch, ts_expr) for the current dialect."""
        bind = self._session.get_bind()
        if bind is not None and bind.dialect.name == "sqlite":
            # SQLite: strftime('%s', ...) -> epoch; datetime(epoch, 'unixepoch') -> ts
            epoch = cast(func.strftime("%s", LogEventModel.received_at), Integer)
            bucket_epoch = (epoch / bucket_seconds) * bucket_seconds
            ts_expr = func.datetime(bucket_epoch, "unixepoch")
            return bucket_epoch, ts_expr
        # PostgreSQL
        pg_epoch = func.extract("epoch", LogEventModel.received_at)
        pg_bucket_epoch = cast(pg_epoch / bucket_seconds, Integer) * bucket_seconds
        pg_ts_expr = func.to_timestamp(pg_bucket_epoch)
        return pg_bucket_epoch, pg_ts_expr

    async def get_log_volume_series(
        self,
        *,
        tenant_id: int,
        since: datetime,
        bucket_minutes: int,
    ) -> list[TimeSeriesBucket]:
        bucket_seconds = bucket_minutes * 60
        bucket_epoch, ts_expr = self._bucket_exprs(bucket_seconds)

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
                ts=normalize_ts(row.ts),
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
        bucket_epoch, ts_expr = self._bucket_exprs(bucket_seconds)

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
            buckets.append(TimeSeriesBucket(ts=normalize_ts(row.ts), value=round(pct, 2)))
        return buckets
