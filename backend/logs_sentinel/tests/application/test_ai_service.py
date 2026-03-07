"""Tests for AIEnrichmentService with in-memory repos."""

from __future__ import annotations

from typing import Any

import pytest

from logs_sentinel.application.services.ai_service import AIEnrichmentService
from logs_sentinel.domains.ai.entities import IssueEnrichment, IssueEnrichmentId
from logs_sentinel.domains.ai.repositories import IssueEnrichmentRepository
from logs_sentinel.domains.identity.entities import TenantId
from logs_sentinel.domains.ingestion.entities import LogEvent, LogEventId
from logs_sentinel.domains.issues.entities import Issue, IssueId, IssueSeverity, IssueStatus
from logs_sentinel.domains.issues.repositories import IssueRepository
from logs_sentinel.domains.logs.entities import (
    LogDetailRow,
    LogEventForTenant,
    LogListRow,
)
from logs_sentinel.domains.logs.repositories import LogsRepository


class InMemoryEnrichmentRepo(IssueEnrichmentRepository):
    def __init__(self) -> None:
        self._enrichments: list[IssueEnrichment] = []
        self._next_id = 1

    async def get_latest_enrichment(
        self, tenant_id: TenantId, issue_id: IssueId
    ) -> IssueEnrichment | None:
        for e in reversed(self._enrichments):
            if e.tenant_id == tenant_id and e.issue_id == issue_id:
                return e
        return None

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
        from datetime import UTC, datetime
        e = IssueEnrichment(
            id=IssueEnrichmentId(self._next_id),
            tenant_id=tenant_id,
            issue_id=issue_id,
            model_name=model_name,
            summary=summary,
            suspected_cause=suspected_cause,
            checklist_json=checklist_json,
            created_at=datetime.now(UTC),
        )
        self._next_id += 1
        self._enrichments.append(e)
        return e


class InMemoryLogsRepoForAI(LogsRepository):
    async def get_log_event_for_tenant(self, tenant_id: int, log_id: int) -> LogEventForTenant | None:
        return None

    async def get_log_events_by_fingerprint(
        self,
        tenant_id: int,
        project_id: int,
        fingerprint: str,
        limit: int = 20,
        log_id_hint: int | None = None,
    ) -> list[LogEventForTenant]:
        return []

    async def create_many(self, events: list[LogEvent]) -> list[LogEventId]:
        return []

    async def list_logs(
        self,
        *,
        tenant_id: int,
        project_id: int | None,
        level: list[str] | None,
        q: str | None,
        from_dt: Any,
        to_dt: Any,
        limit: int,
        offset: int,
    ) -> tuple[list[LogListRow], int]:
        return [], 0

    async def get_log_detail(self, log_id: int, tenant_id: int) -> LogDetailRow | None:
        return None


class InMemoryIssueRepoForAI(IssueRepository):
    def __init__(self, issue: Issue | None = None) -> None:
        self._issue = issue

    async def get_by_id(self, tenant_id: Any, issue_id: Any) -> Issue | None:
        if self._issue and int(self._issue.id) == int(issue_id):
            return self._issue
        return None

    async def get_by_fingerprint(self, *args: Any, **kwargs: Any) -> Issue | None:
        return None

    async def create_issue(self, *args: Any, **kwargs: Any) -> Issue:
        raise NotImplementedError

    async def save(self, issue: Issue) -> Issue:
        return issue

    async def list_issues(self, *args: Any, **kwargs: Any) -> list[Issue]:
        return []

    async def count_issues(self, *args: Any, **kwargs: Any) -> int:
        return 0

    async def delete(self, *args: Any, **kwargs: Any) -> bool:
        return False


@pytest.mark.asyncio
async def test_get_events_for_issue_raises_when_issue_not_found() -> None:


    issue_repo = InMemoryIssueRepoForAI(issue=None)
    logs_repo = InMemoryLogsRepoForAI()
    enrichment_repo = InMemoryEnrichmentRepo()
    service = AIEnrichmentService(
        enrichment_repo=enrichment_repo,
        logs_repo=logs_repo,
        issue_repo=issue_repo,
    )
    with pytest.raises(ValueError) as exc:
        await service.get_events_for_issue(
            tenant_id=TenantId(1),
            issue_id=IssueId(999),
        )
    assert exc.value.args[0] == "ISSUE_NOT_FOUND"


@pytest.mark.asyncio
async def test_get_events_for_issue_returns_fallback_when_no_logs() -> None:
    from datetime import UTC, datetime

    from logs_sentinel.domains.ingestion.entities import ProjectId

    issue = Issue(
        id=IssueId(1),
        tenant_id=TenantId(1),
        project_id=ProjectId(1),
        fingerprint="fp",
        title="Error",
        severity=IssueSeverity.HIGH,
        status=IssueStatus.OPEN,
        first_seen=datetime.now(UTC),
        last_seen=datetime.now(UTC),
        total_count=1,
        priority_score=1.0,
    )
    issue_repo = InMemoryIssueRepoForAI(issue=issue)
    logs_repo = InMemoryLogsRepoForAI()
    enrichment_repo = InMemoryEnrichmentRepo()
    service = AIEnrichmentService(
        enrichment_repo=enrichment_repo,
        logs_repo=logs_repo,
        issue_repo=issue_repo,
    )
    events = await service.get_events_for_issue(
        tenant_id=TenantId(1),
        issue_id=IssueId(1),
    )
    assert len(events) == 1
    assert events[0].message == "Error"


@pytest.mark.asyncio
async def test_persist_enrichment() -> None:
    enrichment_repo = InMemoryEnrichmentRepo()
    service = AIEnrichmentService(
        enrichment_repo=enrichment_repo,
        logs_repo=InMemoryLogsRepoForAI(),
        issue_repo=InMemoryIssueRepoForAI(),
    )
    out = await service.persist_enrichment(
        tenant_id=TenantId(1),
        issue_id=IssueId(1),
        model_name="test",
        summary="Summary",
        suspected_cause="Cause",
        checklist_json=["Step 1"],
    )
    assert out.summary == "Summary"
    assert out.model_name == "test"
    got = await service.get_latest_enrichment(TenantId(1), IssueId(1))
    assert got is not None
    assert got.summary == "Summary"
