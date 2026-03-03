from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from logs_sentinel.application.services.issue_service import IssueService, NewOccurrenceInput
from logs_sentinel.domains.identity.entities import TenantId
from logs_sentinel.domains.ingestion.entities import ProjectId
from logs_sentinel.domains.issues.entities import Issue, IssueId, IssueSeverity, IssueStatus
from logs_sentinel.domains.issues.repositories import IssueOccurrencesRepository, IssueRepository


class InMemoryIssueRepo(IssueRepository):
    def __init__(self) -> None:
        self._by_id: dict[int, Issue] = {}
        self._by_fp: dict[tuple[int, int, str], Issue] = {}
        self._next_id = 1

    async def get_by_fingerprint(self, tenant_id, project_id, fingerprint):
        return self._by_fp.get((int(tenant_id), int(project_id), fingerprint))

    async def create_issue(self, tenant_id, project_id, fingerprint, title, severity, occurred_at):
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

    async def save(self, issue):
        self._by_id[int(issue.id)] = issue
        return issue

    async def list_issues(self, *args, **kwargs):
        return list(self._by_id.values())

    async def get_by_id(self, tenant_id, issue_id):
        return self._by_id.get(int(issue_id))


class InMemoryBucketsRepo(IssueOccurrencesRepository):
    def __init__(self) -> None:
        self._buckets: list[dict] = []

    async def upsert_bucket(self, tenant_id, issue_id, bucket_start, bucket_minutes, increment):
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

    async def list_buckets(self, tenant_id, issue_id, bucket_minutes, since, until):
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
    now = datetime.now(tz=timezone.utc)

    inp = NewOccurrenceInput(
        message="Error processing request",
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

