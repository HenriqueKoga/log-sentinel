"""Repository protocols for logs API."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Protocol

from logs_sentinel.domains.ai_insights.entities import ErrorLogEvent
from logs_sentinel.domains.identity.entities import TenantId
from logs_sentinel.domains.ingestion.entities import ProjectId
from logs_sentinel.domains.logs.entities import (
    LogDetailRow,
    LogEventForTenant,
    LogListRow,
)

if TYPE_CHECKING:
    from logs_sentinel.domains.ingestion.entities import LogEvent, LogEventId


class LogSearchRepository(Protocol):
    """Repository for querying recent error-like log events used by AI insights."""

    async def recent_errors(
        self,
        *,
        tenant_id: TenantId,
        project_id: ProjectId | None,
        from_dt: datetime | None,
        to_dt: datetime | None,
        limit: int,
    ) -> list[ErrorLogEvent]:
        """Return recent error events with the fields needed for AI insights."""

    async def get_event_by_id(
        self,
        *,
        tenant_id: TenantId,
        event_id: int,
        project_id: ProjectId | None = None,
    ) -> ErrorLogEvent | None:
        """Return a single log event by id if it belongs to the tenant (and optional project), else None."""


class LogsRepository(Protocol):
    """Repository for logs: list, detail, create, and lookup by fingerprint."""

    async def create_many(self, events: list[LogEvent]) -> list[LogEventId]:
        """Append log events (used by ingestion)."""

    async def get_log_event_for_tenant(
        self, tenant_id: int, log_id: int
    ) -> LogEventForTenant | None:
        """Return a single log event by id if it belongs to the tenant, else None."""

    async def get_log_events_by_fingerprint(
        self,
        tenant_id: int,
        project_id: int,
        fingerprint: str,
        limit: int = 20,
        log_id_hint: int | None = None,
    ) -> list[LogEventForTenant]:
        """Return log events matching the fingerprint. Raises ValueError(LOG_NOT_FOUND), LOG_NOT_IN_ISSUE when log_id_hint is provided and invalid."""

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
        """List logs with filters. Returns (rows, total_count)."""

    async def get_log_detail(self, log_id: int, tenant_id: int) -> LogDetailRow | None:
        """Get single log by id if it belongs to tenant."""
