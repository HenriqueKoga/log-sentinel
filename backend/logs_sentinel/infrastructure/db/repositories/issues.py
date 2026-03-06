"""SQLAlchemy implementations of issue and issue-occurrence repositories."""

from __future__ import annotations

from typing import Any

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from logs_sentinel.domains.identity.entities import TenantId
from logs_sentinel.domains.ingestion.entities import ProjectId
from logs_sentinel.domains.issues.entities import (
    Issue,
    IssueId,
    IssueOccurrenceBucket,
    IssueOccurrenceId,
    IssueSeverity,
    IssueStatus,
)
from logs_sentinel.domains.issues.repositories import (
    IssueOccurrencesRepository,
    IssueRepository,
)
from logs_sentinel.infrastructure.db.models import IssueModel, IssueOccurrenceModel


class IssueRepositorySQLAlchemy(IssueRepository):
    """SQLAlchemy implementation of issue repository."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_fingerprint(
        self, tenant_id: Any, project_id: Any, fingerprint: str
    ) -> Issue | None:
        stmt = IssueModel.__table__.select().where(
            IssueModel.tenant_id == int(tenant_id),
            IssueModel.project_id == int(project_id),
            IssueModel.fingerprint == fingerprint,
        )
        result = await self._session.execute(stmt)
        row = result.first()
        if row is None:
            return None
        model = IssueModel(**row._mapping)
        return Issue(
            id=IssueId(model.id),
            tenant_id=TenantId(model.tenant_id),
            project_id=ProjectId(model.project_id),
            fingerprint=model.fingerprint,
            title=model.title,
            severity=IssueSeverity(model.severity),
            status=IssueStatus(model.status),
            first_seen=model.first_seen,
            last_seen=model.last_seen,
            total_count=model.total_count,
            priority_score=model.priority_score,
        )

    async def create_issue(
        self,
        tenant_id: Any,
        project_id: Any,
        fingerprint: str,
        title: str,
        severity: str,
        occurred_at: Any,
    ) -> Issue:
        model = IssueModel(
            tenant_id=int(tenant_id),
            project_id=int(project_id),
            fingerprint=fingerprint,
            title=title,
            severity=severity,
            status="open",
            first_seen=occurred_at,
            last_seen=occurred_at,
            total_count=1,
            priority_score=0.0,
        )
        self._session.add(model)
        await self._session.flush()
        return Issue(
            id=IssueId(model.id),
            tenant_id=TenantId(model.tenant_id),
            project_id=ProjectId(model.project_id),
            fingerprint=model.fingerprint,
            title=model.title,
            severity=IssueSeverity(model.severity),
            status=IssueStatus(model.status),
            first_seen=model.first_seen,
            last_seen=model.last_seen,
            total_count=model.total_count,
            priority_score=model.priority_score,
            snoozed_until=model.snoozed_until,
        )

    async def save(self, issue: Issue) -> Issue:
        model = await self._session.get(IssueModel, int(issue.id))
        if model is None:
            raise RuntimeError("ISSUE_NOT_FOUND")
        model.last_seen = issue.last_seen
        model.total_count = issue.total_count
        model.priority_score = issue.priority_score
        model.status = issue.status.value
        model.snoozed_until = issue.snoozed_until
        await self._session.flush()
        return issue

    async def list_issues(self, *args: Any, **kwargs: Any) -> Any:
        tenant_raw = kwargs.get("tenant_id")
        tenant_id = int(tenant_raw) if tenant_raw is not None else 0
        project_id_raw = kwargs.get("project_id")
        severities = kwargs.get("severities")
        statuses = kwargs.get("statuses")
        since = kwargs.get("since")
        until = kwargs.get("until")
        limit = int(kwargs.get("limit", 50))
        offset = int(kwargs.get("offset", 0))

        stmt = IssueModel.__table__.select().where(IssueModel.tenant_id == tenant_id)
        if project_id_raw is not None:
            stmt = stmt.where(IssueModel.project_id == int(project_id_raw))
        if severities:
            db_values = list(severities)
            stmt = stmt.where(IssueModel.severity.in_(db_values))
        if statuses:
            stmt = stmt.where(IssueModel.status.in_(list(statuses)))
        if since is not None:
            stmt = stmt.where(IssueModel.last_seen >= since)
        if until is not None:
            stmt = stmt.where(IssueModel.last_seen <= until)

        sort_by = kwargs.get("sort_by", "priority")
        if sort_by == "severity":
            severity_order = case(
                (IssueModel.severity == "critical", 4),
                (IssueModel.severity == "high", 3),
                (IssueModel.severity == "medium", 2),
                else_=1,
            )
            stmt = stmt.order_by(severity_order.desc()).limit(limit).offset(offset)
        elif sort_by == "last_seen":
            stmt = stmt.order_by(IssueModel.last_seen.desc()).limit(limit).offset(offset)
        else:
            stmt = stmt.order_by(IssueModel.priority_score.desc()).limit(limit).offset(offset)

        result = await self._session.execute(stmt)
        rows = result.fetchall()
        issues: list[Issue] = []
        for row in rows:
            model = IssueModel(**row._mapping)
            issues.append(
                Issue(
                    id=IssueId(model.id),
                    tenant_id=TenantId(model.tenant_id),
                    project_id=ProjectId(model.project_id),
                    fingerprint=model.fingerprint,
                    title=model.title,
                    severity=IssueSeverity(model.severity),
                    status=IssueStatus(model.status),
                    first_seen=model.first_seen,
                    last_seen=model.last_seen,
                    total_count=model.total_count,
                    priority_score=model.priority_score,
                    snoozed_until=model.snoozed_until,
                )
            )
        return issues

    async def count_issues(self, *args: Any, **kwargs: Any) -> int:
        tenant_raw = kwargs.get("tenant_id")
        tenant_id = int(tenant_raw) if tenant_raw is not None else 0
        project_id_raw = kwargs.get("project_id")
        severities = kwargs.get("severities")
        statuses = kwargs.get("statuses")
        since = kwargs.get("since")
        until = kwargs.get("until")

        stmt = IssueModel.__table__.select().where(IssueModel.tenant_id == tenant_id)
        if project_id_raw is not None:
            stmt = stmt.where(IssueModel.project_id == int(project_id_raw))
        if severities:
            stmt = stmt.where(IssueModel.severity.in_(list(severities)))
        if statuses:
            stmt = stmt.where(IssueModel.status.in_(list(statuses)))
        if since is not None:
            stmt = stmt.where(IssueModel.last_seen >= since)
        if until is not None:
            stmt = stmt.where(IssueModel.last_seen <= until)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        result = await self._session.execute(count_stmt)
        return int(result.scalar_one() or 0)

    async def get_by_id(self, tenant_id: Any, issue_id: Any) -> Issue | None:
        model = await self._session.get(IssueModel, int(issue_id))
        if model is None or model.tenant_id != int(tenant_id):
            return None
        return Issue(
            id=IssueId(model.id),
            tenant_id=TenantId(model.tenant_id),
            project_id=ProjectId(model.project_id),
            fingerprint=model.fingerprint,
            title=model.title,
            severity=IssueSeverity(model.severity),
            status=IssueStatus(model.status),
            first_seen=model.first_seen,
            last_seen=model.last_seen,
            total_count=model.total_count,
            priority_score=model.priority_score,
            snoozed_until=model.snoozed_until,
        )

    async def delete(self, tenant_id: Any, issue_id: Any) -> bool:
        model = await self._session.get(IssueModel, int(issue_id))
        if model is None or model.tenant_id != int(tenant_id):
            return False
        await self._session.delete(model)
        await self._session.flush()
        return True


class IssueOccurrencesRepositorySQLAlchemy(IssueOccurrencesRepository):
    """SQLAlchemy implementation of issue occurrence buckets repository."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert_bucket(
        self,
        tenant_id: Any,
        issue_id: Any,
        bucket_start: Any,
        bucket_minutes: int,
        increment: int,
    ) -> None:
        stmt = IssueOccurrenceModel.__table__.select().where(
            IssueOccurrenceModel.tenant_id == int(tenant_id),
            IssueOccurrenceModel.issue_id == int(issue_id),
            IssueOccurrenceModel.bucket_start == bucket_start,
            IssueOccurrenceModel.bucket_minutes == bucket_minutes,
        )
        result = await self._session.execute(stmt)
        row = result.first()
        if row is None:
            model = IssueOccurrenceModel(
                tenant_id=int(tenant_id),
                issue_id=int(issue_id),
                bucket_start=bucket_start,
                bucket_minutes=bucket_minutes,
                count=increment,
            )
            self._session.add(model)
        else:
            model = IssueOccurrenceModel(**row._mapping)
            model.count += increment
        await self._session.flush()

    async def list_buckets(
        self,
        tenant_id: Any,
        issue_id: Any,
        bucket_minutes: int,
        since: Any,
        until: Any,
    ) -> list[IssueOccurrenceBucket]:
        stmt = IssueOccurrenceModel.__table__.select().where(
            IssueOccurrenceModel.tenant_id == int(tenant_id),
            IssueOccurrenceModel.issue_id == int(issue_id),
            IssueOccurrenceModel.bucket_minutes == bucket_minutes,
            IssueOccurrenceModel.bucket_start >= since,
            IssueOccurrenceModel.bucket_start <= until,
        )
        result = await self._session.execute(stmt)
        rows = result.fetchall()
        buckets: list[IssueOccurrenceBucket] = []
        for row in rows:
            model = IssueOccurrenceModel(**row._mapping)
            buckets.append(
                IssueOccurrenceBucket(
                    id=IssueOccurrenceId(model.id),
                    tenant_id=TenantId(model.tenant_id),
                    issue_id=IssueId(model.issue_id),
                    bucket_start=model.bucket_start,
                    bucket_minutes=model.bucket_minutes,
                    count=model.count,
                )
            )
        return buckets
