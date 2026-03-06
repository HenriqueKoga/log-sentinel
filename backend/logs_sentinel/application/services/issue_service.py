from __future__ import annotations

import hashlib
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from logs_sentinel.domains.identity.entities import TenantId
from logs_sentinel.domains.ingestion.entities import ProjectId
from logs_sentinel.domains.ingestion.normalization import compute_fingerprint, normalize_message
from logs_sentinel.domains.issues.entities import (
    Issue,
    IssueId,
    IssueSeverity,
    IssueStatus,
    compute_priority_score,
)
from logs_sentinel.domains.issues.repositories import IssueOccurrencesRepository, IssueRepository
from logs_sentinel.domains.projects.repositories import ProjectRepository


@dataclass(slots=True)
class NewOccurrenceInput:
    """Information extracted from a raw log for issue processing."""

    message: str
    exception_type: str | None
    stacktrace: str | None
    severity: IssueSeverity
    occurred_at: datetime


class IssueService:
    """Application service for upserting issues and computing prioritization."""

    def __init__(
        self,
        issue_repo: IssueRepository,
        buckets_repo: IssueOccurrencesRepository,
        project_repo: ProjectRepository | None = None,
    ) -> None:
        self._issue_repo = issue_repo
        self._buckets_repo = buckets_repo
        self._project_repo = project_repo

    async def ensure_project_accessible(
        self, tenant_id: TenantId, project_id: ProjectId
    ) -> None:
        """Raise ValueError('PROJECT_NOT_FOUND') if project does not exist or does not belong to tenant."""
        if self._project_repo is None:
            raise ValueError("PROJECT_NOT_FOUND")
        project = await self._project_repo.get_project(tenant_id, project_id)
        if project is None:
            raise ValueError("PROJECT_NOT_FOUND")

    async def record_occurrence(
        self,
        tenant_id: TenantId,
        project_id: ProjectId,
        input: NewOccurrenceInput,
    ) -> Issue:
        """Upsert issue aggregate and update time buckets."""

        normalized = normalize_message(input.message)
        frames = input.stacktrace.splitlines() if input.stacktrace else None
        fingerprint = compute_fingerprint(
            normalized_message=normalized,
            exception_type=input.exception_type,
            stack_frames=frames,
        )

        issue = await self._issue_repo.get_by_fingerprint(
            tenant_id=tenant_id,
            project_id=project_id,
            fingerprint=fingerprint,
        )
        if issue is None:
            title = input.message[:200]
            issue = await self._issue_repo.create_issue(
                tenant_id=tenant_id,
                project_id=project_id,
                fingerprint=fingerprint,
                title=title,
                severity=input.severity.value,
                occurred_at=input.occurred_at,
            )
        else:
            issue.update_on_occurrence(input.occurred_at, increment=1)

        await self._update_buckets(tenant_id, issue.id, input.occurred_at)

        count_last_hour = await self._estimate_last_hour_count(
            tenant_id, issue.id, now=input.occurred_at
        )
        spike_factor = 1.0  # simplified; can be enhanced with historical baseline
        issue.priority_score = compute_priority_score(
            severity=input.severity,
            count_last_hour=count_last_hour,
            spike_factor=spike_factor,
        )

        issue = await self._issue_repo.save(issue)
        return issue

    async def list_issues(
        self,
        tenant_id: TenantId,
        project_id: ProjectId | None,
        severities: Sequence[IssueSeverity] | None,
        statuses: Sequence[IssueStatus] | None,
        since: datetime | None,
        until: datetime | None,
        limit: int = 50,
        offset: int = 0,
        sort_by: str = "priority",
    ) -> Sequence[Issue]:
        severities_raw = [s.value for s in severities] if severities else None
        statuses_raw = [s.value for s in statuses] if statuses else None
        return await self._issue_repo.list_issues(
            tenant_id=tenant_id,
            project_id=project_id,
            severities=severities_raw,
            statuses=statuses_raw,
            since=since,
            until=until,
            limit=limit,
            offset=offset,
            sort_by=sort_by,
        )

    async def get_issue(self, tenant_id: TenantId, issue_id: IssueId) -> Issue | None:
        return await self._issue_repo.get_by_id(tenant_id=tenant_id, issue_id=issue_id)

    async def delete_issue(self, tenant_id: TenantId, issue_id: IssueId) -> bool:
        """Delete issue if it belongs to tenant. Returns True if deleted."""
        return await self._issue_repo.delete(tenant_id=tenant_id, issue_id=issue_id)

    async def get_issue_by_fingerprint(
        self,
        tenant_id: TenantId,
        project_id: ProjectId,
        fingerprint: str,
    ) -> Issue | None:
        return await self._issue_repo.get_by_fingerprint(
            tenant_id=tenant_id,
            project_id=project_id,
            fingerprint=fingerprint,
        )

    async def create_issue_manual(
        self,
        tenant_id: TenantId,
        project_id: ProjectId,
        title: str,
        severity: IssueSeverity,
    ) -> Issue:
        """Create an issue manually (no log events). Uses a unique fingerprint."""
        now = datetime.now(tz=UTC)
        raw = f"manual-{uuid.uuid4().hex}"
        fingerprint = hashlib.sha256(raw.encode()).hexdigest()[:64]
        issue = await self._issue_repo.create_issue(
            tenant_id=tenant_id,
            project_id=project_id,
            fingerprint=fingerprint,
            title=title[:200],
            severity=severity.value,
            occurred_at=now,
        )
        issue.priority_score = compute_priority_score(
            severity=severity,
            count_last_hour=1,
            spike_factor=1.0,
        )
        return await self._issue_repo.save(issue)

    async def create_issue_from_log(
        self,
        tenant_id: TenantId,
        project_id: ProjectId,
        fingerprint: str,
        title: str,
        severity: IssueSeverity,
        occurred_at: datetime,
    ) -> Issue:
        """Create an issue with the given fingerprint (from a log) and record one occurrence."""
        issue = await self._issue_repo.create_issue(
            tenant_id=tenant_id,
            project_id=project_id,
            fingerprint=fingerprint,
            title=title[:200],
            severity=severity.value,
            occurred_at=occurred_at,
        )
        await self._update_buckets(tenant_id, issue.id, occurred_at)
        count_last_hour = await self._estimate_last_hour_count(
            tenant_id, issue.id, now=occurred_at
        )
        issue.priority_score = compute_priority_score(
            severity=severity,
            count_last_hour=count_last_hour,
            spike_factor=1.0,
        )
        return await self._issue_repo.save(issue)

    async def save_issue(self, issue: Issue) -> Issue:
        """Persist the given issue aggregate."""

        return await self._issue_repo.save(issue)

    async def _update_buckets(
        self,
        tenant_id: TenantId,
        issue_id: IssueId,
        occurred_at: datetime,
    ) -> None:
        bucket_sizes = (5, 60, 24 * 60)
        for minutes in bucket_sizes:
            bucket_start = occurred_at.replace(second=0, microsecond=0)
            await self._buckets_repo.upsert_bucket(
                tenant_id=tenant_id,
                issue_id=issue_id,
                bucket_start=bucket_start,
                bucket_minutes=minutes,
                increment=1,
            )

    async def _estimate_last_hour_count(
        self,
        tenant_id: TenantId,
        issue_id: IssueId,
        now: datetime | None = None,
    ) -> int:
        if now is None:
            now = datetime.now(tz=UTC)
        since = now - timedelta(hours=1)
        buckets = await self._buckets_repo.list_buckets(
            tenant_id=tenant_id,
            issue_id=issue_id,
            bucket_minutes=60,
            since=since,
            until=now,
        )
        return sum(b.count for b in buckets)
