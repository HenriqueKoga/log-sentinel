from __future__ import annotations

from celery import shared_task

from logs_sentinel.application.services.issue_service import IssueService, NewOccurrenceInput
from logs_sentinel.domains.identity.entities import TenantId
from logs_sentinel.domains.ingestion.entities import ProjectId
from logs_sentinel.domains.issues.entities import IssueSeverity
from logs_sentinel.domains.issues.repositories import IssueOccurrencesRepository, IssueRepository
from logs_sentinel.infrastructure.db.base import SessionFactory
from logs_sentinel.infrastructure.db.models import IssueModel, IssueOccurrenceModel, LogEventModel


class IssueRepositorySQLAlchemy(IssueRepository):
    def __init__(self, session):
        self._session = session

    async def get_by_fingerprint(self, tenant_id, project_id, fingerprint):
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
        from logs_sentinel.domains.issues.entities import Issue, IssueId

        return Issue(
            id=IssueId(model.id),
            tenant_id=TenantId(model.tenant_id),
            project_id=ProjectId(model.project_id),
            fingerprint=model.fingerprint,
            title=model.title,
            severity=IssueSeverity(model.severity),
            status=model.status,  # type: ignore[arg-type]
            first_seen=model.first_seen,
            last_seen=model.last_seen,
            total_count=model.total_count,
            priority_score=model.priority_score,
        )

    async def create_issue(self, tenant_id, project_id, fingerprint, title, severity, occurred_at):
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
        from logs_sentinel.domains.issues.entities import Issue, IssueId, IssueSeverity, IssueStatus

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

    async def save(self, issue):
        model = await self._session.get(IssueModel, int(issue.id))
        if model is None:
            raise RuntimeError("ISSUE_NOT_FOUND")
        model.last_seen = issue.last_seen
        model.total_count = issue.total_count
        model.priority_score = issue.priority_score
        await self._session.flush()
        return issue

    async def list_issues(self, *args, **kwargs):
        raise NotImplementedError

    async def get_by_id(self, tenant_id, issue_id):
        model = await self._session.get(IssueModel, int(issue_id))
        if model is None or model.tenant_id != int(tenant_id):
            return None
        from logs_sentinel.domains.issues.entities import Issue, IssueId, IssueSeverity, IssueStatus

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


class IssueOccurrencesRepositorySQLAlchemy(IssueOccurrencesRepository):
    def __init__(self, session):
        self._session = session

    async def upsert_bucket(self, tenant_id, issue_id, bucket_start, bucket_minutes, increment):
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

    async def list_buckets(self, tenant_id, issue_id, bucket_minutes, since, until):
        stmt = IssueOccurrenceModel.__table__.select().where(
            IssueOccurrenceModel.tenant_id == int(tenant_id),
            IssueOccurrenceModel.issue_id == int(issue_id),
            IssueOccurrenceModel.bucket_minutes == bucket_minutes,
            IssueOccurrenceModel.bucket_start >= since,
            IssueOccurrenceModel.bucket_start <= until,
        )
        result = await self._session.execute(stmt)
        rows = result.fetchall()
        from logs_sentinel.domains.issues.entities import IssueOccurrenceBucket, IssueOccurrenceId

        buckets: list[IssueOccurrenceBucket] = []
        for row in rows:
            model = IssueOccurrenceModel(**row._mapping)
            buckets.append(
                IssueOccurrenceBucket(
                    id=IssueOccurrenceId(model.id),
                    tenant_id=TenantId(model.tenant_id),
                    issue_id=model.issue_id,
                    bucket_start=model.bucket_start,
                    bucket_minutes=model.bucket_minutes,
                    count=model.count,
                )
            )
        return buckets


@shared_task(name="logs_sentinel.workers.tasks.process_ingest_batch")
def process_ingest_batch(payload: dict) -> None:
    """Celery task: process an ingestion batch into issues and buckets."""

    import asyncio
    from datetime import datetime

    async def _run() -> None:
        async with SessionFactory() as session:
            for event in payload["events"]:
                repo = IssueRepositorySQLAlchemy(session)
                buckets_repo = IssueOccurrencesRepositorySQLAlchemy(session)
                service = IssueService(repo, buckets_repo)
                occurred_at = datetime.fromisoformat(event["received_at"])
                input_data = NewOccurrenceInput(
                    message=event["message"],
                    exception_type=event.get("exception_type"),
                    stacktrace=event.get("stacktrace"),
                    severity=IssueSeverity.ERROR,
                    occurred_at=occurred_at,
                )
                await service.record_occurrence(
                    tenant_id=TenantId(event["tenant_id"]),
                    project_id=ProjectId(event["project_id"]),
                    input=input_data,
                )
            await session.commit()

    asyncio.run(_run())

