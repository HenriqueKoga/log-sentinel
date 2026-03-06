"""SQLAlchemy implementation of log repositories (events, search, list/detail)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from logs_sentinel.domains.ai_insights.entities import ErrorLogEvent
from logs_sentinel.domains.identity.entities import TenantId
from logs_sentinel.domains.ingestion.entities import LogEvent, LogEventId, ProjectId
from logs_sentinel.domains.ingestion.normalization import compute_fingerprint, normalize_message
from logs_sentinel.domains.logs.entities import LogDetailRow, LogEventForTenant, LogListRow
from logs_sentinel.domains.logs.repositories import LogSearchRepository
from logs_sentinel.infrastructure.db.models import LogEventModel, ProjectModel


class LogSearchRepositorySQLAlchemy(LogSearchRepository):
    """LogSearchRepository implementation using SQLAlchemy and LogEventModel."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def recent_errors(
        self,
        *,
        tenant_id: TenantId,
        project_id: ProjectId | None,
        from_dt: datetime | None,
        to_dt: datetime | None,
        limit: int,
    ) -> list[ErrorLogEvent]:
        stmt = select(LogEventModel).where(LogEventModel.tenant_id == int(tenant_id))

        if project_id is not None:
            stmt = stmt.where(LogEventModel.project_id == int(project_id))

        # only error / critical levels
        stmt = stmt.where(LogEventModel.level.in_(["error", "critical"]))

        if from_dt is not None:
            stmt = stmt.where(LogEventModel.received_at >= from_dt)
        if to_dt is not None:
            stmt = stmt.where(LogEventModel.received_at <= to_dt)

        stmt = stmt.order_by(LogEventModel.received_at.desc()).limit(limit)

        result = await self._session.execute(stmt)
        rows = result.scalars().all()

        events: list[ErrorLogEvent] = []
        for row in rows:
            events.append(
                ErrorLogEvent(
                    id=LogEventId(row.id),
                    project_id=ProjectId(row.project_id),
                    message=row.message or "",
                    exception_type=row.exception_type,
                    stacktrace=row.stacktrace,
                    received_at=row.received_at,
                    level=row.level,
                )
            )
        return events

    async def get_event_by_id(
        self,
        *,
        tenant_id: TenantId,
        event_id: int,
        project_id: ProjectId | None = None,
    ) -> ErrorLogEvent | None:
        stmt = select(LogEventModel).where(
            LogEventModel.id == event_id,
            LogEventModel.tenant_id == int(tenant_id),
        )
        if project_id is not None:
            stmt = stmt.where(LogEventModel.project_id == int(project_id))
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return ErrorLogEvent(
            id=LogEventId(row.id),
            project_id=ProjectId(row.project_id),
            message=row.message or "",
            exception_type=row.exception_type,
            stacktrace=row.stacktrace,
            received_at=row.received_at,
            level=row.level,
        )


class LogsRepositorySQLAlchemy:
    """LogsRepository implementation: create, list, and detail of log events."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_many(self, events: list[LogEvent]) -> list[LogEventId]:
        models = [
            LogEventModel(
                tenant_id=int(e.tenant_id),
                project_id=int(e.project_id),
                received_at=e.received_at,
                level=e.level.value,
                message=e.message,
                exception_type=e.exception_type,
                stacktrace=e.stacktrace,
                raw_json=e.raw_json,
            )
            for e in events
        ]
        self._session.add_all(models)
        await self._session.flush()
        return [LogEventId(m.id) for m in models]

    async def list_logs(
        self,
        *,
        tenant_id: int,
        project_id: int | None,
        level: list[str] | None,
        q: str | None,
        from_dt: datetime | None,
        to_dt: datetime | None,
        limit: int,
        offset: int,
    ) -> tuple[list[LogListRow], int]:
        filters = [LogEventModel.tenant_id == tenant_id]
        if project_id is not None:
            filters.append(LogEventModel.project_id == project_id)
        if level:
            filters.append(LogEventModel.level.in_(level))
        if from_dt is not None:
            filters.append(LogEventModel.received_at >= from_dt)
        if to_dt is not None:
            filters.append(LogEventModel.received_at <= to_dt)
        if q and q.strip():
            term = f"%{q.strip()}%"
            filters.append(
                or_(
                    LogEventModel.message.ilike(term),
                    LogEventModel.exception_type.isnot(None)
                    & LogEventModel.exception_type.ilike(term),
                )
            )

        count_stmt = select(func.count()).select_from(LogEventModel).where(*filters)
        total = (await self._session.execute(count_stmt)).scalar_one()

        base = (
            select(LogEventModel, ProjectModel.name)
            .join(ProjectModel, LogEventModel.project_id == ProjectModel.id)
            .where(
                LogEventModel.tenant_id == tenant_id,
                ProjectModel.tenant_id == tenant_id,
            )
        )
        if project_id is not None:
            base = base.where(LogEventModel.project_id == project_id)
        if level:
            base = base.where(LogEventModel.level.in_(level))
        if from_dt is not None:
            base = base.where(LogEventModel.received_at >= from_dt)
        if to_dt is not None:
            base = base.where(LogEventModel.received_at <= to_dt)
        if q and q.strip():
            term = f"%{q.strip()}%"
            base = base.where(
                or_(
                    LogEventModel.message.ilike(term),
                    LogEventModel.exception_type.isnot(None)
                    & LogEventModel.exception_type.ilike(term),
                )
            )

        base = base.order_by(LogEventModel.received_at.desc()).offset(offset).limit(limit)
        result = await self._session.execute(base)
        rows: list[LogListRow] = []
        for log, project_name in result.all():
            raw = log.raw_json if isinstance(log.raw_json, dict) else {}
            rows.append(
                LogListRow(
                    id=log.id,
                    received_at=log.received_at,
                    level=log.level,
                    message=log.message or "",
                    project_id=log.project_id,
                    project_name=project_name or "",
                    raw_json=raw,
                    stacktrace=log.stacktrace,
                    exception_type=log.exception_type,
                )
            )
        return rows, total

    async def get_log_detail(self, log_id: int, tenant_id: int) -> LogDetailRow | None:
        stmt = (
            select(LogEventModel, ProjectModel.name)
            .join(ProjectModel, LogEventModel.project_id == ProjectModel.id)
            .where(
                LogEventModel.id == log_id,
                LogEventModel.tenant_id == tenant_id,
                ProjectModel.tenant_id == tenant_id,
            )
        )
        result = await self._session.execute(stmt)
        row = result.one_or_none()
        if row is None:
            return None
        log, project_name = row
        raw = log.raw_json if isinstance(log.raw_json, dict) else {}
        return LogDetailRow(
            id=log.id,
            received_at=log.received_at,
            level=log.level,
            message=log.message or "",
            exception_type=log.exception_type,
            stacktrace=log.stacktrace,
            raw_json=raw,
            project_id=log.project_id,
            project_name=project_name or "",
        )

    async def get_log_event_for_tenant(self, tenant_id: int, log_id: int) -> LogEventForTenant | None:
        row = await self._session.get(LogEventModel, log_id)
        if row is None or row.tenant_id != tenant_id:
            return None
        return LogEventForTenant(
            id=row.id,
            project_id=row.project_id,
            message=row.message,
            exception_type=row.exception_type,
            stacktrace=row.stacktrace,
            level=row.level or "error",
            received_at=row.received_at,
        )

    async def get_log_events_by_fingerprint(
        self,
        tenant_id: int,
        project_id: int,
        fingerprint: str,
        limit: int = 20,
        log_id_hint: int | None = None,
    ) -> list[LogEventForTenant]:
        if log_id_hint is not None:
            row = await self._session.get(LogEventModel, log_id_hint)
            if row is None or row.tenant_id != tenant_id or row.project_id != project_id:
                raise ValueError("LOG_NOT_FOUND")
            normalized = normalize_message(row.message or "")
            frames = row.stacktrace.splitlines() if row.stacktrace else None
            fp = compute_fingerprint(
                normalized_message=normalized,
                exception_type=row.exception_type,
                stack_frames=frames,
            )
            if fp != fingerprint:
                raise ValueError("LOG_NOT_IN_ISSUE")
            return [
                LogEventForTenant(
                    id=row.id,
                    project_id=row.project_id,
                    message=row.message,
                    exception_type=row.exception_type,
                    stacktrace=row.stacktrace,
                    level=row.level or "error",
                    received_at=row.received_at,
                )
            ]
        stmt = (
            select(LogEventModel)
            .where(
                LogEventModel.tenant_id == tenant_id,
                LogEventModel.project_id == project_id,
            )
            .order_by(LogEventModel.received_at.desc())
            .limit(500)
        )
        result = await self._session.execute(stmt)
        events: list[LogEventForTenant] = []
        for ev in result.scalars().all():
            normalized = normalize_message(ev.message or "")
            frames = ev.stacktrace.splitlines() if ev.stacktrace else None
            fp = compute_fingerprint(
                normalized_message=normalized,
                exception_type=ev.exception_type,
                stack_frames=frames,
            )
            if fp != fingerprint:
                continue
            events.append(
                LogEventForTenant(
                    id=ev.id,
                    project_id=ev.project_id,
                    message=ev.message,
                    exception_type=ev.exception_type,
                    stacktrace=ev.stacktrace,
                    level=ev.level or "error",
                    received_at=ev.received_at,
                )
            )
            if len(events) >= limit:
                break
        return events

