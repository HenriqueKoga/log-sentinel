from __future__ import annotations

from datetime import UTC, datetime

from logs_sentinel.domains.ai.entities import IssueEnrichment
from logs_sentinel.domains.ai.repositories import IssueEnrichmentRepository
from logs_sentinel.domains.identity.entities import TenantId
from logs_sentinel.domains.issues.entities import IssueId
from logs_sentinel.domains.issues.repositories import IssueRepository
from logs_sentinel.domains.logs.entities import LogEventForTenant
from logs_sentinel.domains.logs.repositories import LogsRepository


class AIEnrichmentService:
    """Application service for issue enrichment: load events and persist enrichment data."""

    def __init__(
        self,
        enrichment_repo: IssueEnrichmentRepository,
        logs_repo: LogsRepository,
        issue_repo: IssueRepository,
    ) -> None:
        self._enrichment_repo = enrichment_repo
        self._logs_repo = logs_repo
        self._issue_repo = issue_repo

    async def get_log_event_for_tenant(
        self, tenant_id: TenantId, log_id: int
    ) -> LogEventForTenant | None:
        """Return a single log event by id if it belongs to the tenant, else None."""
        return await self._logs_repo.get_log_event_for_tenant(int(tenant_id), log_id)

    async def get_latest_enrichment(
        self,
        tenant_id: TenantId,
        issue_id: IssueId,
    ) -> IssueEnrichment | None:
        return await self._enrichment_repo.get_latest_enrichment(tenant_id, issue_id)

    async def get_events_for_issue(
        self,
        tenant_id: TenantId,
        issue_id: IssueId,
        log_id: int | None = None,
    ) -> list[LogEventForTenant]:
        """Load event data for an issue (for LLM enrichment). Raises ValueError(ISSUE_NOT_FOUND), LOG_NOT_FOUND, LOG_NOT_IN_ISSUE."""
        issue = await self._issue_repo.get_by_id(tenant_id, issue_id)
        if issue is None:
            raise ValueError("ISSUE_NOT_FOUND")
        events = await self._logs_repo.get_log_events_by_fingerprint(
            tenant_id=int(tenant_id),
            project_id=int(issue.project_id),
            fingerprint=issue.fingerprint,
            limit=20,
            log_id_hint=log_id,
        )
        if not events:
            now = datetime.now(tz=UTC)
            events = [
                LogEventForTenant(
                    id=0,
                    project_id=int(issue.project_id),
                    message=issue.title,
                    exception_type=None,
                    stacktrace=None,
                    level="error",
                    received_at=now,
                )
            ]
        return events

    async def persist_enrichment(
        self,
        tenant_id: TenantId,
        issue_id: IssueId,
        *,
        model_name: str,
        summary: str,
        suspected_cause: str,
        checklist_json: list[str],
    ) -> IssueEnrichment:
        """Persist enrichment data for an issue and return the created IssueEnrichment."""
        return await self._enrichment_repo.persist_enrichment(
            tenant_id=tenant_id,
            issue_id=issue_id,
            model_name=model_name,
            summary=summary,
            suspected_cause=suspected_cause,
            checklist_json=checklist_json,
        )
