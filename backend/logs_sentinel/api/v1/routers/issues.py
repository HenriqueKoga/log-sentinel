from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Annotated

import httpx
from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from logs_sentinel.api.v1.dependencies.auth import TenantContext, get_tenant_context
from logs_sentinel.api.v1.dependencies.services import (
    get_ai_service,
    get_billing_service,
    get_issue_service,
)
from logs_sentinel.api.v1.schemas.issues import (
    CreateIssueFromLogRequest,
    CreateIssueRequest,
    EnrichIssueRequest,
    EnrichIssueResponse,
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
    SuggestIssueRequest,
    SuggestIssueResponse,
)
from logs_sentinel.application.services.ai_service import AIEnrichmentService
from logs_sentinel.application.services.billing_service import BillingService
from logs_sentinel.application.services.issue_service import IssueService
from logs_sentinel.domains.identity.entities import TenantId
from logs_sentinel.domains.ingestion.entities import ProjectId
from logs_sentinel.domains.ingestion.normalization import compute_fingerprint, normalize_message
from logs_sentinel.domains.issues.entities import IssueId, IssueSeverity, IssueStatus
from logs_sentinel.domains.issues.repositories import IssueOccurrencesRepository
from logs_sentinel.infrastructure.db.base import get_session
from logs_sentinel.infrastructure.db.models import IssueEnrichmentModel, LogEventModel
from logs_sentinel.infrastructure.db.repositories.issues import (
    IssueOccurrencesRepositorySQLAlchemy,
)
from logs_sentinel.utils.severity import log_level_to_issue_severity

router = APIRouter(prefix="/issues", tags=["issues"])

_DEFAULT_ENRICH_REQUEST = EnrichIssueRequest()
_ENRICH_ISSUE_BODY = Body(default=_DEFAULT_ENRICH_REQUEST)


@router.get("", response_model=IssuesListResponse)
async def list_issues(
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    service: Annotated[IssueService, Depends(get_issue_service)],
    project_id: Annotated[int | None, Query()] = None,
    status: Annotated[list[IssueStatusEnum] | None, Query()] = None,
    severity: Annotated[list[IssueSeverityEnum] | None, Query()] = None,
    sort_by: Annotated[str, Query()] = "priority",
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
    if sort_by not in ("priority", "severity", "last_seen"):
        sort_by = "priority"

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
        sort_by=sort_by,
    )

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


@router.post("/suggest", response_model=SuggestIssueResponse)
async def suggest_issue(
    body: SuggestIssueRequest,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    billing: Annotated[BillingService, Depends(get_billing_service)],
) -> SuggestIssueResponse:
    """Suggest issue title and severity from context. Uses LLM when enabled and records usage."""
    tenant_id: TenantId = ctx.tenant_id
    use_llm = await billing.is_llm_enabled(tenant_id)

    if use_llm:
        try:
            from logs_sentinel.infrastructure.agents.suggest_issue import (
                create_suggest_issue_agent,
            )

            agent = create_suggest_issue_agent()
            run_result = await agent.run(body.context[:8000] if body.context else "")
            out = run_result.output
            title = (out.title or "").strip() or (body.context[:200].strip() if body.context else "Manual issue")
            severity = (out.severity or "medium").lower()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail={"code": "LLM_RATE_LIMIT", "message": "AI rate limit exceeded. Please try again in a moment."},
                ) from e
            raise
        try:
            await billing.record_llm_usage(tenant_id)
        except ValueError as e:
            if str(e) == "USAGE_LIMIT_EXCEEDED":
                raise HTTPException(
                    status_code=status.HTTP_402_PAYMENT_REQUIRED,
                    detail={"code": "USAGE_LIMIT_EXCEEDED"},
                ) from e
            raise
    else:
        title = (body.context[:200].strip() if body.context else "").strip() or "Manual issue"
        severity = "medium"

    if severity in ("low", "medium", "high", "critical"):
        severity_enum = IssueSeverityEnum(severity)
    else:
        severity_enum = IssueSeverityEnum.MEDIUM
    return SuggestIssueResponse(title=title[:255], severity=severity_enum)


@router.post("", response_model=IssueListItem, status_code=status.HTTP_201_CREATED)
async def create_issue(
    body: CreateIssueRequest,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    service: Annotated[IssueService, Depends(get_issue_service)],
) -> IssueListItem:
    """Create an issue manually (no log events)."""
    tenant_id: TenantId = ctx.tenant_id
    try:
        await service.ensure_project_accessible(tenant_id, ProjectId(body.project_id))
    except ValueError as e:
        if str(e) == "PROJECT_NOT_FOUND":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "PROJECT_NOT_FOUND"},
            ) from e
        raise
    issue = await service.create_issue_manual(
        tenant_id=tenant_id,
        project_id=ProjectId(body.project_id),
        title=body.title,
        severity=IssueSeverity(body.severity.value),
    )
    return IssueListItem(
        id=int(issue.id),
        project_id=int(issue.project_id),
        title=issue.title,
        severity=IssueSeverityEnum(issue.severity.value),
        status=IssueStatusEnum(issue.status.value),
        last_seen=issue.last_seen,
        total_count=issue.total_count,
        priority_score=issue.priority_score,
    )


@router.post("/from-log", response_model=IssueListItem, status_code=status.HTTP_201_CREATED)
async def create_issue_from_log(
    body: CreateIssueFromLogRequest,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    service: Annotated[IssueService, Depends(get_issue_service)],
    ai_service: Annotated[AIEnrichmentService, Depends(get_ai_service)],
    billing: Annotated[BillingService, Depends(get_billing_service)],
) -> IssueListItem:
    """Create an issue from an existing log. The issue is linked to that log (same fingerprint)."""
    tenant_id: TenantId = ctx.tenant_id
    log = await ai_service.get_log_event_for_tenant(tenant_id, body.log_id)
    if log is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "LOG_NOT_FOUND"},
        )
    normalized = normalize_message(log.message or "")
    frames = log.stacktrace.splitlines() if log.stacktrace else None
    fingerprint = compute_fingerprint(
        normalized_message=normalized,
        exception_type=log.exception_type,
        stack_frames=frames,
    )
    existing = await service.get_issue_by_fingerprint(
        tenant_id=tenant_id,
        project_id=ProjectId(log.project_id),
        fingerprint=fingerprint,
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "ISSUE_ALREADY_EXISTS", "issue_id": int(existing.id)},
        )
    use_llm = await billing.is_llm_enabled(tenant_id)
    if use_llm:
        context_parts = [log.message or ""]
        if log.exception_type:
            context_parts.append(f"Exception: {log.exception_type}")
        if log.stacktrace:
            context_parts.append(log.stacktrace)
        try:
            from logs_sentinel.infrastructure.agents.suggest_issue import (
                create_suggest_issue_agent,
            )

            agent = create_suggest_issue_agent()
            run_result = await agent.run("\n".join(context_parts))
            out = run_result.output
            title = (out.title or log.message or "Issue")[:200]
            severity_raw = (out.severity or "medium").lower()
            severity = (
                IssueSeverity(severity_raw)
                if severity_raw in ("low", "medium", "high", "critical")
                else log_level_to_issue_severity(log.level)
            )
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail={"code": "LLM_RATE_LIMIT", "message": "AI rate limit exceeded. Please try again in a moment."},
                ) from e
            raise
        try:
            await billing.record_llm_usage(tenant_id)
        except ValueError as e:
            if str(e) == "USAGE_LIMIT_EXCEEDED":
                raise HTTPException(
                    status_code=status.HTTP_402_PAYMENT_REQUIRED,
                    detail={"code": "USAGE_LIMIT_EXCEEDED"},
                ) from e
            raise
    else:
        title = (log.message or "Issue")[:200]
        severity = log_level_to_issue_severity(log.level)
    issue = await service.create_issue_from_log(
        tenant_id=tenant_id,
        project_id=ProjectId(log.project_id),
        fingerprint=fingerprint,
        title=title,
        severity=severity,
        occurred_at=log.received_at,
    )
    return IssueListItem(
        id=int(issue.id),
        project_id=int(issue.project_id),
        title=issue.title,
        severity=IssueSeverityEnum(issue.severity.value),
        status=IssueStatusEnum(issue.status.value),
        last_seen=issue.last_seen,
        total_count=issue.total_count,
        priority_score=issue.priority_score,
    )


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


@router.delete("/{issue_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_issue(
    issue_id: int,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    service: Annotated[IssueService, Depends(get_issue_service)],
) -> None:
    tenant_id: TenantId = ctx.tenant_id
    deleted = await service.delete_issue(tenant_id=tenant_id, issue_id=IssueId(issue_id))
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "ISSUE_NOT_FOUND"},
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
    points = [IssueOccurrencesPoint(bucket_start=b.bucket_start, count=b.count) for b in buckets]
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


@router.post("/{issue_id}/enrich", response_model=EnrichIssueResponse)
async def enrich_issue(
    issue_id: int,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    service: Annotated[IssueService, Depends(get_issue_service)],
    ai_service: Annotated[AIEnrichmentService, Depends(get_ai_service)],
    billing: Annotated[BillingService, Depends(get_billing_service)],
    body: EnrichIssueRequest = _ENRICH_ISSUE_BODY,
) -> EnrichIssueResponse:
    tenant_id: TenantId = ctx.tenant_id
    issue = await service.get_issue(tenant_id=tenant_id, issue_id=IssueId(issue_id))
    if issue is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "ISSUE_NOT_FOUND"},
        )
    plan = await billing.get_active_plan(tenant_id)
    if plan is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "NO_ACTIVE_PLAN"},
        )

    try:
        events = await ai_service.get_events_for_issue(
            tenant_id=tenant_id,
            issue_id=IssueId(issue_id),
            log_id=body.log_id,
        )
    except ValueError as e:
        if str(e) == "LOG_NOT_FOUND":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "LOG_NOT_FOUND"},
            ) from e
        if str(e) == "LOG_NOT_IN_ISSUE":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "LOG_NOT_IN_ISSUE"},
            ) from e
        raise

    use_llm = await billing.is_llm_enabled(tenant_id)
    if use_llm:
        try:
            from logs_sentinel.infrastructure.agents.issue_enrichment import (
                create_issue_enrichment_agent,
                events_to_prompt,
            )

            agent = create_issue_enrichment_agent()
            run_result = await agent.run(events_to_prompt(events))
            out = run_result.output
            model_name = "gpt-4o-mini"
            summary = (out.summary or "").strip()
            suspected_cause = (out.suspected_cause or "").strip()
            checklist_json = list(out.checklist or [])
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail={"code": "LLM_RATE_LIMIT", "message": "AI rate limit exceeded. Please try again in a moment."},
                ) from e
            raise
    else:
        model_name = "null-llm"
        summary = "LLM enrichment is disabled."
        suspected_cause = "Enable LLM enrichment to see AI-generated analysis."
        checklist_json = [
            "Check recent deployments.",
            "Inspect related logs around the spike.",
            "Verify configuration and environment variables.",
        ]

    enrichment = await ai_service.persist_enrichment(
        tenant_id=tenant_id,
        issue_id=IssueId(issue_id),
        model_name=model_name,
        summary=summary,
        suspected_cause=suspected_cause,
        checklist_json=checklist_json,
    )

    if use_llm:
        try:
            await billing.record_llm_usage(tenant_id)
        except ValueError as e:
            if str(e) == "USAGE_LIMIT_EXCEEDED":
                raise HTTPException(
                    status_code=status.HTTP_402_PAYMENT_REQUIRED,
                    detail={"code": "USAGE_LIMIT_EXCEEDED"},
                ) from e
            raise

    return EnrichIssueResponse(
        enrichment=IssueEnrichmentResponse(
            model_name=enrichment.model_name,
            summary=enrichment.summary,
            suspected_cause=enrichment.suspected_cause,
            checklist=enrichment.checklist_json,
            created_at=enrichment.created_at,
        )
    )
