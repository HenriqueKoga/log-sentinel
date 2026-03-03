from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from logs_sentinel.api.v1.dependencies.auth import TenantContext, get_tenant_context
from logs_sentinel.api.v1.schemas.alerts import (
    AlertEventResponse,
    AlertRuleCreateRequest,
    AlertRuleResponse,
    AlertRuleUpdateRequest,
    NotificationChannelCreateRequest,
    NotificationChannelKindEnum,
    NotificationChannelResponse,
    NotificationChannelUpdateRequest,
)
from logs_sentinel.application.services.alerts_service import AlertsService
from logs_sentinel.domains.alerts.entities import AlertKind, AlertRuleId, NotificationChannelId
from logs_sentinel.domains.alerts.repositories import (
    AlertEventRepository,
    AlertRuleRepository,
    NotificationChannelRepository,
)
from logs_sentinel.domains.ingestion.entities import ProjectId
from logs_sentinel.infrastructure.db.base import get_session
from logs_sentinel.infrastructure.db.repositories.alerts import (
    AlertEventRepositorySQLAlchemy,
    AlertRuleRepositorySQLAlchemy,
    NotificationChannelRepositorySQLAlchemy,
)
from logs_sentinel.infrastructure.notifications.slack import SlackWebhookSender

router = APIRouter(prefix="/alerts", tags=["alerts"])


async def get_alerts_service(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AlertsService:
    rules_repo: AlertRuleRepository = AlertRuleRepositorySQLAlchemy(session)
    events_repo: AlertEventRepository = AlertEventRepositorySQLAlchemy(session)
    channels_repo: NotificationChannelRepository = NotificationChannelRepositorySQLAlchemy(session)
    sender = SlackWebhookSender()
    # Issue occurrences repo is only needed for evaluation, wired in worker.
    from logs_sentinel.infrastructure.db.repositories.issues import (
        IssueOccurrencesRepositorySQLAlchemy,
    )

    occurrences_repo = IssueOccurrencesRepositorySQLAlchemy(session)
    return AlertsService(
        rules_repo=rules_repo,
        events_repo=events_repo,
        channels_repo=channels_repo,
        occurrences_repo=occurrences_repo,
        sender=sender,
    )


@router.post("/rules", response_model=AlertRuleResponse, status_code=status.HTTP_201_CREATED)
async def create_rule(
    payload: AlertRuleCreateRequest,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AlertRuleResponse:
    repo = AlertRuleRepositorySQLAlchemy(session)
    rule = await repo.create_rule(
        tenant_id=ctx.tenant_id,
        project_id=ProjectId(payload.project_id),
        name=payload.name,
        kind=payload.kind.value,
        threshold=payload.threshold,
    )
    return AlertRuleResponse(
        id=int(rule.id),
        project_id=int(rule.project_id),
        name=rule.name,
        kind=payload.kind,
        threshold=rule.threshold,
        enabled=rule.enabled,
    )


@router.get("/rules", response_model=list[AlertRuleResponse])
async def list_rules(
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
    project_id: Annotated[int | None, Query()] = None,
) -> list[AlertRuleResponse]:
    repo = AlertRuleRepositorySQLAlchemy(session)
    rules = await repo.list_rules(
        tenant_id=ctx.tenant_id,
        project_id=ProjectId(project_id) if project_id is not None else None,
    )
    return [
        AlertRuleResponse(
            id=int(rule.id),
            project_id=int(rule.project_id),
            name=rule.name,
            kind=AlertKind(rule.kind).value,  # type: ignore[arg-type]
            threshold=rule.threshold,
            enabled=rule.enabled,
        )
        for rule in rules
    ]


@router.patch("/rules/{rule_id}", response_model=AlertRuleResponse)
async def update_rule(
    rule_id: int,
    payload: AlertRuleUpdateRequest,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AlertRuleResponse:
    repo = AlertRuleRepositorySQLAlchemy(session)
    updated = await repo.update_rule(
        tenant_id=ctx.tenant_id,
        rule_id=AlertRuleId(rule_id),
        name=payload.name,
        threshold=payload.threshold,
        enabled=payload.enabled,
    )
    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "ALERT_RULE_NOT_FOUND"},
        )
    return AlertRuleResponse(
        id=int(updated.id),
        project_id=int(updated.project_id),
        name=updated.name,
        kind=AlertKind(updated.kind).value,  # type: ignore[arg-type]
        threshold=updated.threshold,
        enabled=updated.enabled,
    )


@router.delete("/rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_rule(
    rule_id: int,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    repo = AlertRuleRepositorySQLAlchemy(session)
    await repo.delete_rule(tenant_id=ctx.tenant_id, rule_id=AlertRuleId(rule_id))


@router.post(
    "/channels",
    response_model=NotificationChannelResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_channel(
    payload: NotificationChannelCreateRequest,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> NotificationChannelResponse:
    repo = NotificationChannelRepositorySQLAlchemy(session)
    config: dict[str, object] = {}
    if payload.kind == NotificationChannelKindEnum.SLACK_WEBHOOK:
        if not payload.slack_webhook_url:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "MISSING_SLACK_WEBHOOK_URL"},
            )
        config["webhook_url"] = payload.slack_webhook_url
    channel = await repo.create_channel(
        tenant_id=ctx.tenant_id,
        kind=payload.kind.value,
        config_json=config,
    )
    display_name = "Slack webhook"
    return NotificationChannelResponse(
        id=int(channel.id),
        kind=NotificationChannelKindEnum(channel.kind.value),
        enabled=channel.enabled,
        display_name=display_name,
    )


@router.get("/channels", response_model=list[NotificationChannelResponse])
async def list_channels(
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[NotificationChannelResponse]:
    repo = NotificationChannelRepositorySQLAlchemy(session)
    channels = await repo.list_channels(tenant_id=ctx.tenant_id)
    responses: list[NotificationChannelResponse] = []
    for ch in channels:
        display_name = "Slack webhook" if ch.kind.value == "slack_webhook" else ch.kind.value
        responses.append(
            NotificationChannelResponse(
                id=int(ch.id),
                kind=NotificationChannelKindEnum(ch.kind.value),
                enabled=ch.enabled,
                display_name=display_name,
            )
        )
    return responses


@router.patch("/channels/{channel_id}", response_model=NotificationChannelResponse)
async def update_channel(
    channel_id: int,
    payload: NotificationChannelUpdateRequest,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> NotificationChannelResponse:
    repo = NotificationChannelRepositorySQLAlchemy(session)
    updated = await repo.update_channel(
        tenant_id=ctx.tenant_id,
        channel_id=NotificationChannelId(channel_id),
        enabled=payload.enabled,
    )
    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "ALERT_CHANNEL_NOT_FOUND"},
        )
    display_name = "Slack webhook" if updated.kind.value == "slack_webhook" else updated.kind.value
    return NotificationChannelResponse(
        id=int(updated.id),
        kind=NotificationChannelKindEnum(updated.kind.value),
        enabled=updated.enabled,
        display_name=display_name,
    )


@router.get("/events", response_model=list[AlertEventResponse])
async def list_events(
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
    since_hours: Annotated[int | None, Query(ge=1, le=168)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[AlertEventResponse]:
    repo = AlertEventRepositorySQLAlchemy(session)
    since_dt: datetime | None = None
    if since_hours is not None:
        since_dt = datetime.now(tz=UTC) - timedelta(hours=since_hours)
    events = await repo.list_events(
        tenant_id=ctx.tenant_id,
        since=since_dt,
        limit=limit,
    )
    return [
        AlertEventResponse(
            id=int(ev.id),
            issue_id=int(ev.issue_id),
            rule_id=int(ev.rule_id),
            triggered_at=ev.triggered_at,
            payload=ev.payload_json,
        )
        for ev in events
    ]

