from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Protocol

from logs_sentinel.domains.identity.entities import TenantId
from logs_sentinel.domains.ingestion.entities import ProjectId

from .entities import Issue, IssueId, IssueOccurrenceBucket


class IssueRepository(Protocol):
    """Repository for issue aggregates."""

    async def get_by_fingerprint(
        self,
        tenant_id: TenantId,
        project_id: ProjectId,
        fingerprint: str,
    ) -> Issue | None: ...

    async def create_issue(
        self,
        tenant_id: TenantId,
        project_id: ProjectId,
        fingerprint: str,
        title: str,
        severity: str,
        occurred_at: datetime,
    ) -> Issue: ...

    async def save(self, issue: Issue) -> Issue: ...

    async def list_issues(
        self,
        tenant_id: TenantId,
        project_id: ProjectId | None,
        severities: Sequence[str] | None,
        statuses: Sequence[str] | None,
        since: datetime | None,
        until: datetime | None,
        limit: int = 50,
        offset: int = 0,
        sort_by: str = "priority",
    ) -> Sequence[Issue]: ...

    async def count_issues(
        self,
        tenant_id: TenantId,
        project_id: ProjectId | None,
        severities: Sequence[str] | None,
        statuses: Sequence[str] | None,
        since: datetime | None,
        until: datetime | None,
    ) -> int: ...

    async def get_by_id(self, tenant_id: TenantId, issue_id: IssueId) -> Issue | None: ...

    async def delete(self, tenant_id: TenantId, issue_id: IssueId) -> bool:
        """Delete issue if it belongs to tenant. Returns True if deleted."""
        ...


class IssueOccurrencesRepository(Protocol):
    """Repository for issue occurrence buckets."""

    async def upsert_bucket(
        self,
        tenant_id: TenantId,
        issue_id: IssueId,
        bucket_start: datetime,
        bucket_minutes: int,
        increment: int,
    ) -> None: ...

    async def list_buckets(
        self,
        tenant_id: TenantId,
        issue_id: IssueId,
        bucket_minutes: int,
        since: datetime,
        until: datetime,
    ) -> Sequence[IssueOccurrenceBucket]: ...
