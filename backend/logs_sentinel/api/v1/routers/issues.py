from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from logs_sentinel.api.v1.dependencies.auth import TenantContext, get_tenant_context
from logs_sentinel.api.v1.schemas.issues import (
    IssueDetailResponse,
    IssueDetailSample,
    IssueEnrichmentResponse,
    IssueListItem,
    IssueOccurrencesPoint,
    IssueOccurrencesResponse,
    IssuesAggregates,
    IssueSeverityEnum,
    IssuesListResponse,
    IssueStatusEnum,
    SnoozeRequest,
)
from logs_sentinel.application.services.ai_service import AIEnrichmentService
from logs_sentinel.application.services.issue_service import IssueService
from logs_sentinel.domains.identity.entities import TenantId
from logs_sentinel.domains.ingestion.entities import ProjectId
from logs_sentinel.domains.ingestion.normalization import compute_fingerprint, normalize_message
from logs_sentinel.domains.issues.entities import IssueId, IssueSeverity, IssueStatus
from logs_sentinel.domains.issues.repositories import IssueOccurrencesRepository, IssueRepository
from logs_sentinel.infrastructure.db.base import get_session
from logs_sentinel.infrastructure.db.models import IssueEnrichmentModel, LogEventModel
from logs_sentinel.infrastructure.db.repositories.issues import (
    IssueOccurrencesRepositorySQLAlchemy,
    IssueRepositorySQLAlchemy,
)
from logs_sentinel.infrastructure.llm.null_client import NullLLMClient
from logs_sentinel.infrastructure.settings.config import settings

router = APIRouter(prefix="/issues", tags=["issues"])


async def get_issue_service(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> IssueService:
    issue_repo: IssueRepository = IssueRepositorySQLAlchemy(session)
    buckets_repo: IssueOccurrencesRepository = IssueOccurrencesRepositorySQLAlchemy(session)
    return IssueService(issue_repo=issue_repo, buckets_repo=buckets_repo)


async def get_ai_service(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AIEnrichmentService:
    from logs_sentinel.domains.ai.entities import LLMClientProtocol

    llm: LLMClientProtocol
    if settings.enable_llm_enrichment and settings.openai_api_key:
        try:
            from logs_sentinel.infrastructure.llm.openai_client import OpenAILLMClient
        except Exception:  # pragma: no cover
            llm = NullLLMClient()
        else:
            llm = OpenAILLMClient(api_key=settings.openai_api_key)
    else:
        llm = NullLLMClient()

    return AIEnrichmentService(session=session, llm_client=llm)


@router.get("", response_model=IssuesListResponse)
async def list_issues(
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    service: Annotated[IssueService, Depends(get_issue_service)],
    project_id: Annotated[int | None, Query()] = None,
    status: Annotated[list[IssueStatusEnum] | None, Query()] = None,
    severity: Annotated[list[IssueSeverityEnum] | None, Query()] = None,
    q: Annotated[str | None, Query()] = None,
    from_: Annotated[datetime | None, Query(alias="from")] = None,
    to: Annotated[datetime | None, Query()] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 50,
) -> IssuesListResponse:
    tenant_id = ctx.tenant_id
    project = ProjectId(project_id) if project_id is not None else None
    statuses = [IssueStatus(s.value) for s in status] if status else None
    severities = [IssueSeverity(s.value) for s in severity] if severity else None

    limit = page_size
    offset = (page - 1) * page_size

    issues = await service.list_issues(
        tenant_id=tenant_id,
        project_id=project,
        severities=severities,
        statuses=statuses,
        since=from_,
        until=to,
        limit=limit,
        offset=offset,
    )

    # Basic in-memory aggregates over the returned window.
    total = len(issues)
    by_severity_counter: Counter[str] = Counter()
    by_status_counter: Counter[str] = Counter()
    for issue in issues:
        by_severity_counter[issue.severity.value] += 1
        by_status_counter[issue.status.value] += 1

    items: list[IssueListItem] = [
        IssueListItem(
            id=int(issue.id),
            project_id=int(issue.project_id),
            title=issue.title,
            severity=IssueSeverityEnum(issue.severity.value),
            status=IssueStatusEnum(issue.status.value),
            last_seen=issue.last_seen,
            total_count=issue.total_count,
            priority_score=issue.priority_score,
        )
        for issue in issues
        if not q or q.lower() in issue.title.lower()
    ]

    aggregates = IssuesAggregates(
        total=total,
        by_severity=dict(by_severity_counter),
        by_status=dict(by_status_counter),
    )
    return IssuesListResponse(items=items, aggregates=aggregates)


@router.get("/{issue_id}", response_model=IssueDetailResponse)
async def get_issue_detail(
    issue_id: int,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    service: Annotated[IssueService, Depends(get_issue_service)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> IssueDetailResponse:
    tenant_id: TenantId = ctx.tenant_id
    issue = await service.get_issue(tenant_id=tenant_id, issue_id=IssueId(issue_id))
    if issue is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "ISSUE_NOT_FOUND"},
        )

    # Fetch recent samples by recomputing fingerprints for latest log events.
    stmt = (
        select(LogEventModel)
        .where(
            LogEventModel.tenant_id == int(tenant_id),
            LogEventModel.project_id == int(issue.project_id),
        )
        .order_by(LogEventModel.received_at.desc())
        .limit(200)
    )
    result = await session.execute(stmt)
    rows: Sequence[LogEventModel] = [row[0] for row in result.fetchall()]

    samples: list[IssueDetailSample] = []
    for row in rows:
        normalized = normalize_message(row.message)
        frames = row.stacktrace.splitlines() if row.stacktrace else None
        fp = compute_fingerprint(
            normalized_message=normalized,
            exception_type=row.exception_type,
            stack_frames=frames,
        )
        if fp != issue.fingerprint:
            continue
        samples.append(
            IssueDetailSample(
                received_at=row.received_at,
                level=row.level,
                message=row.message,
                exception_type=row.exception_type,
                stacktrace=row.stacktrace,
            )
        )
        if len(samples) >= 20:
            break

    # Latest enrichment, if any.
    enrichment_stmt = (
        select(IssueEnrichmentModel)
        .where(
            IssueEnrichmentModel.tenant_id == int(tenant_id),
            IssueEnrichmentModel.issue_id == issue_id,
        )
        .order_by(IssueEnrichmentModel.created_at.desc())
        .limit(1)
    )
    enrichment_result = await session.execute(enrichment_stmt)
    enrichment_row = enrichment_result.scalar_one_or_none()
    enrichment: IssueEnrichmentResponse | None = None
    if enrichment_row is not None:
        model: IssueEnrichmentModel = enrichment_row
        enrichment = IssueEnrichmentResponse(
            model_name=model.model_name,
            summary=model.summary,
            suspected_cause=model.suspected_cause,
            checklist=model.checklist_json,
            created_at=model.created_at,
        )

    return IssueDetailResponse(
        id=int(issue.id),
        project_id=int(issue.project_id),
        title=issue.title,
        severity=IssueSeverityEnum(issue.severity.value),
        status=IssueStatusEnum(issue.status.value),
        first_seen=issue.first_seen,
        last_seen=issue.last_seen,
        total_count=issue.total_count,
        priority_score=issue.priority_score,
        snoozed_until=issue.snoozed_until,
        samples=samples,
        enrichment=enrichment,
    )


@router.get("/{issue_id}/occurrences", response_model=IssueOccurrencesResponse)
async def get_issue_occurrences(
    issue_id: int,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
    range_: Annotated[str, Query(alias="range")] = "24h",
) -> IssueOccurrencesResponse:
    tenant_id: TenantId = ctx.tenant_id
    buckets_repo: IssueOccurrencesRepository = IssueOccurrencesRepositorySQLAlchemy(session)

    now = datetime.now(tz=UTC)
    if range_ == "24h":
        since = now - timedelta(hours=24)
        bucket_minutes = 60
    elif range_ == "7d":
        since = now - timedelta(days=7)
        bucket_minutes = 60 * 24
    elif range_ == "30d":
        since = now - timedelta(days=30)
        bucket_minutes = 60 * 24
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_RANGE"},
        )

    buckets = await buckets_repo.list_buckets(
        tenant_id=tenant_id,
        issue_id=IssueId(issue_id),
        bucket_minutes=bucket_minutes,
        since=since,
        until=now,
    )
    points = [
        IssueOccurrencesPoint(bucket_start=b.bucket_start, count=b.count) for b in buckets
    ]
    return IssueOccurrencesResponse(points=points)


@router.post("/{issue_id}/actions/snooze", status_code=status.HTTP_204_NO_CONTENT)
async def snooze_issue(
    issue_id: int,
    body: SnoozeRequest,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    service: Annotated[IssueService, Depends(get_issue_service)],
) -> None:
    tenant_id: TenantId = ctx.tenant_id
    issue = await service.get_issue(tenant_id=tenant_id, issue_id=IssueId(issue_id))
    if issue is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "ISSUE_NOT_FOUND"},
        )
    issue.status = IssueStatus.SNOOZED
    issue.snoozed_until = datetime.now(tz=UTC) + timedelta(minutes=body.duration_minutes)
    await service.save_issue(issue)


@router.post("/{issue_id}/actions/resolve", status_code=status.HTTP_204_NO_CONTENT)
async def resolve_issue(
    issue_id: int,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    service: Annotated[IssueService, Depends(get_issue_service)],
) -> None:
    tenant_id: TenantId = ctx.tenant_id
    issue = await service.get_issue(tenant_id=tenant_id, issue_id=IssueId(issue_id))
    if issue is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "ISSUE_NOT_FOUND"},
        )
    issue.status = IssueStatus.RESOLVED
    issue.snoozed_until = None
    await service.save_issue(issue)


@router.post("/{issue_id}/actions/reopen", status_code=status.HTTP_204_NO_CONTENT)
async def reopen_issue(
    issue_id: int,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    service: Annotated[IssueService, Depends(get_issue_service)],
) -> None:
    tenant_id: TenantId = ctx.tenant_id
    issue = await service.get_issue(tenant_id=tenant_id, issue_id=IssueId(issue_id))
    if issue is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "ISSUE_NOT_FOUND"},
        )
    issue.status = IssueStatus.OPEN
    issue.snoozed_until = None
    await service.save_issue(issue)

