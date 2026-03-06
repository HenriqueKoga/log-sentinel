"""Chat tools: search_logs, top_errors, error_details for Log Chat."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any

from logs_sentinel.domains.ai_insights.entities import ErrorLogEvent
from logs_sentinel.domains.ai_insights.fingerprinting import compute_fingerprint
from logs_sentinel.domains.identity.entities import TenantId
from logs_sentinel.domains.ingestion.entities import ProjectId
from logs_sentinel.domains.logs.repositories import LogSearchRepository


class ChatToolsService:
    """Executes chat tools (search_logs, top_errors, error_details) for Log Chat."""

    def __init__(self, log_search: LogSearchRepository) -> None:
        self._log_search = log_search

    async def search_logs(
        self,
        *,
        tenant_id: int,
        project_id: int | None,
        from_dt: datetime | None,
        to_dt: datetime | None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Return recent error log events as JSON-serializable dicts."""
        events = await self._log_search.recent_errors(
            tenant_id=TenantId(tenant_id),
            project_id=ProjectId(project_id) if project_id is not None else None,
            from_dt=from_dt,
            to_dt=to_dt,
            limit=limit,
        )
        return [
            {
                "id": int(e.id),
                "project_id": int(e.project_id),
                "message": e.message,
                "exception_type": e.exception_type,
                "stacktrace": e.stacktrace,
                "received_at": e.received_at.isoformat() if e.received_at else None,
                "level": e.level,
            }
            for e in events
        ]

    async def top_errors(
        self,
        *,
        tenant_id: int,
        project_id: int | None,
        from_dt: datetime | None,
        to_dt: datetime | None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Return top error clusters by fingerprint (count, sample_message, last_seen)."""
        events = await self._log_search.recent_errors(
            tenant_id=TenantId(tenant_id),
            project_id=ProjectId(project_id) if project_id is not None else None,
            from_dt=from_dt,
            to_dt=to_dt,
            limit=1000,
        )
        clusters: dict[str, list[ErrorLogEvent]] = defaultdict(list)
        for e in events:
            fp = compute_fingerprint(e.exception_type, e.stacktrace, e.message)
            clusters[fp].append(e)
        result: list[dict[str, Any]] = []
        for fp, group in sorted(clusters.items(), key=lambda x: -len(x[1]))[:limit]:
            sorted_group = sorted(group, key=lambda ev: ev.received_at)
            last = sorted_group[-1]
            result.append(
                {
                    "fingerprint": fp,
                    "count": len(group),
                    "sample_message": last.message,
                    "last_seen": last.received_at.isoformat() if last.received_at else None,
                }
            )
        return result

    async def error_details(
        self,
        *,
        tenant_id: int,
        event_id: int,
        project_id: int | None = None,
    ) -> dict[str, Any] | None:
        """Return a single log event by id (tenant-scoped)."""
        event = await self._log_search.get_event_by_id(
            tenant_id=TenantId(tenant_id),
            event_id=event_id,
            project_id=ProjectId(project_id) if project_id is not None else None,
        )
        if event is None:
            return None
        return {
            "id": int(event.id),
            "project_id": int(event.project_id),
            "message": event.message or "",
            "exception_type": event.exception_type,
            "stacktrace": event.stacktrace,
            "received_at": event.received_at.isoformat() if event.received_at else None,
            "level": event.level,
        }
