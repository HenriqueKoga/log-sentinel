"""Tests for IssueService (record_occurrence, upsert, priority)."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from logs_sentinel.application.services.issue_service import IssueService, NewOccurrenceInput
from logs_sentinel.domains.identity.entities import TenantId
from logs_sentinel.domains.ingestion.entities import ProjectId
from logs_sentinel.domains.issues.entities import Issue, IssueId, IssueSeverity, IssueStatus
from logs_sentinel.domains.issues.repositories import IssueOccurrencesRepository, IssueRepository
from logs_sentinel.domains.projects.repositories import ProjectRepository


class InMemoryIssueRepo(IssueRepository):
    def __init__(self) -> None:
        self._by_id: dict[int, Issue] = {}
        self._by_fp: dict[tuple[int, int, str], Issue] = {}
        self._next_id = 1

    async def get_by_fingerprint(
        self, tenant_id: Any, project_id: Any, fingerprint: str
    ) -> Issue | None:
        return self._by_fp.get((int(tenant_id), int(project_id), fingerprint))

    async def create_issue(
        self,
        tenant_id: Any,
        project_id: Any,
        fingerprint: str,
        title: str,
        severity: str,
        occurred_at: Any,
    ) -> Issue:
        issue = Issue(
            id=IssueId(self._next_id),
            tenant_id=TenantId(int(tenant_id)),
            project_id=ProjectId(int(project_id)),
            fingerprint=fingerprint,
            title=title,
            severity=IssueSeverity(severity),
            status=IssueStatus.OPEN,
            first_seen=occurred_at,
            last_seen=occurred_at,
            total_count=1,
            priority_score=0.0,
        )
        self._next_id += 1
        self._by_id[int(issue.id)] = issue
        self._by_fp[(int(tenant_id), int(project_id), fingerprint)] = issue
        return issue

    async def save(self, issue: Issue) -> Issue:
        self._by_id[int(issue.id)] = issue
        return issue

    async def list_issues(self, *args: Any, **kwargs: Any) -> list[Issue]:
        return list(self._by_id.values())

    async def get_by_id(self, tenant_id: Any, issue_id: Any) -> Issue | None:
        return self._by_id.get(int(issue_id))

    async def delete(self, tenant_id: Any, issue_id: Any) -> bool:
        issue = self._by_id.get(int(issue_id))
        if issue is None or int(issue.tenant_id) != int(tenant_id):
            return False
        del self._by_id[int(issue_id)]
        key = (int(tenant_id), int(issue.project_id), issue.fingerprint)
        if key in self._by_fp:
            del self._by_fp[key]
        return True

    async def count_issues(
        self,
        tenant_id: Any,
        project_id: Any,
        severities: Sequence[str] | None,
        statuses: Sequence[str] | None,
        since: Any,
        until: Any,
    ) -> int:
        n = 0
        for issue in self._by_id.values():
            if int(issue.tenant_id) != int(tenant_id):
                continue
            if project_id is not None and int(issue.project_id) != int(project_id):
                continue
            if severities and issue.severity.value not in severities:
                continue
            if statuses and issue.status.value not in statuses:
                continue
            if since is not None and issue.last_seen < since:
                continue
            if until is not None and issue.last_seen > until:
                continue
            n += 1
        return n


class InMemoryBucketsRepo(IssueOccurrencesRepository):
    def __init__(self) -> None:
        self._buckets: list[dict[str, Any]] = []

    async def upsert_bucket(
        self,
        tenant_id: Any,
        issue_id: Any,
        bucket_start: Any,
        bucket_minutes: int,
        increment: int,
    ) -> None:
        for b in self._buckets:
            if (
                b["tenant_id"] == int(tenant_id)
                and b["issue_id"] == int(issue_id)
                and b["bucket_start"] == bucket_start
                and b["bucket_minutes"] == bucket_minutes
            ):
                b["count"] += increment
                return
        self._buckets.append(
            {
                "tenant_id": int(tenant_id),
                "issue_id": int(issue_id),
                "bucket_start": bucket_start,
                "bucket_minutes": bucket_minutes,
                "count": increment,
            }
        )

    async def list_buckets(
        self,
        tenant_id: Any,
        issue_id: Any,
        bucket_minutes: int,
        since: Any,
        until: Any,
    ) -> Any:
        from logs_sentinel.domains.issues.entities import IssueOccurrenceBucket, IssueOccurrenceId

        out = []
        for idx, b in enumerate(self._buckets):
            if (
                b["tenant_id"] == int(tenant_id)
                and b["issue_id"] == int(issue_id)
                and b["bucket_minutes"] == bucket_minutes
                and since <= b["bucket_start"] <= until
            ):
                out.append(
                    IssueOccurrenceBucket(
                        id=IssueOccurrenceId(idx + 1),
                        tenant_id=TenantId(b["tenant_id"]),
                        issue_id=IssueId(b["issue_id"]),
                        bucket_start=b["bucket_start"],
                        bucket_minutes=b["bucket_minutes"],
                        count=b["count"],
                    )
                )
        return out


@pytest.mark.asyncio
async def test_issue_upsert_and_priority() -> None:
    repo = InMemoryIssueRepo()
    buckets = InMemoryBucketsRepo()
    service = IssueService(repo, buckets)

    tenant_id = TenantId(1)
    project_id = ProjectId(1)
    now = datetime.now(tz=UTC)

    inp = NewOccurrenceInput(
        message="Error processing request for user 1",
        exception_type="ValueError",
        stacktrace="trace",
        severity=IssueSeverity.HIGH,
        occurred_at=now,
    )

    issue1 = await service.record_occurrence(tenant_id, project_id, inp)
    assert issue1.total_count == 1
    assert issue1.priority_score > 0

    later = now + timedelta(minutes=1)
    inp2 = NewOccurrenceInput(
        message="Error processing request for user 2",
        exception_type="ValueError",
        stacktrace="trace",
        severity=IssueSeverity.HIGH,
        occurred_at=later,
    )
    issue2 = await service.record_occurrence(tenant_id, project_id, inp2)
    assert int(issue2.id) == int(issue1.id)
    assert issue2.total_count == 2
    assert issue2.priority_score >= issue1.priority_score


@pytest.mark.asyncio
async def test_list_issues() -> None:
    repo = InMemoryIssueRepo()
    buckets = InMemoryBucketsRepo()
    service = IssueService(repo, buckets)
    tenant_id = TenantId(1)
    project_id = ProjectId(1)
    now = datetime.now(tz=UTC)
    inp = NewOccurrenceInput(
        message="Err",
        exception_type="ValueError",
        stacktrace="x",
        severity=IssueSeverity.HIGH,
        occurred_at=now,
    )
    await service.record_occurrence(tenant_id, project_id, inp)
    issues = await service.list_issues(tenant_id, project_id, None, None, None, None, 50, 0)
    assert len(issues) == 1
    assert issues[0].fingerprint


@pytest.mark.asyncio
async def test_get_issue() -> None:
    repo = InMemoryIssueRepo()
    buckets = InMemoryBucketsRepo()
    service = IssueService(repo, buckets)
    tenant_id = TenantId(1)
    project_id = ProjectId(1)
    now = datetime.now(tz=UTC)
    inp = NewOccurrenceInput(
        message="Err",
        exception_type="ValueError",
        stacktrace="x",
        severity=IssueSeverity.HIGH,
        occurred_at=now,
    )
    created = await service.record_occurrence(tenant_id, project_id, inp)
    got = await service.get_issue(tenant_id, created.id)
    assert got is not None
    assert got.id == created.id
    assert await service.get_issue(tenant_id, IssueId(999)) is None


@pytest.mark.asyncio
async def test_delete_issue() -> None:
    repo = InMemoryIssueRepo()
    buckets = InMemoryBucketsRepo()
    service = IssueService(repo, buckets)
    tenant_id = TenantId(1)
    project_id = ProjectId(1)
    now = datetime.now(tz=UTC)
    created = await service.record_occurrence(
        tenant_id,
        project_id,
        NewOccurrenceInput("Err", "ValueError", "x", IssueSeverity.HIGH, now),
    )
    ok = await service.delete_issue(tenant_id, created.id)
    assert ok is True
    assert await service.get_issue(tenant_id, created.id) is None
    assert await service.delete_issue(tenant_id, IssueId(999)) is False


@pytest.mark.asyncio
async def test_create_issue_manual() -> None:
    repo = InMemoryIssueRepo()
    buckets = InMemoryBucketsRepo()
    service = IssueService(repo, buckets)
    tenant_id = TenantId(1)
    project_id = ProjectId(1)
    issue = await service.create_issue_manual(
        tenant_id=tenant_id,
        project_id=project_id,
        title="Manual issue",
        severity=IssueSeverity.MEDIUM,
    )
    assert issue.title == "Manual issue"
    assert issue.severity == IssueSeverity.MEDIUM
    assert issue.total_count == 1
    assert len(issue.fingerprint) == 64


@pytest.mark.asyncio
async def test_ensure_project_accessible_raises_when_no_project_repo() -> None:
    repo = InMemoryIssueRepo()
    buckets = InMemoryBucketsRepo()
    service = IssueService(repo, buckets, project_repo=None)
    with pytest.raises(ValueError) as exc:
        await service.ensure_project_accessible(TenantId(1), ProjectId(1))
    assert exc.value.args[0] == "PROJECT_NOT_FOUND"


@pytest.mark.asyncio
async def test_ensure_project_accessible_raises_when_project_not_found() -> None:
    from logs_sentinel.domains.projects.entities import Project

    class EmptyProjectRepo(ProjectRepository):
        async def get_project(
            self, tenant_id: TenantId, project_id: ProjectId
        ) -> Project | None:
            return None

        async def list_projects(self, tenant_id: TenantId) -> list[Project]:
            return []

        async def create_project(self, tenant_id: TenantId, name: str) -> Project:
            raise NotImplementedError

    repo = InMemoryIssueRepo()
    buckets = InMemoryBucketsRepo()
    service = IssueService(repo, buckets, project_repo=EmptyProjectRepo())
    with pytest.raises(ValueError) as exc:
        await service.ensure_project_accessible(TenantId(1), ProjectId(1))
    assert exc.value.args[0] == "PROJECT_NOT_FOUND"
