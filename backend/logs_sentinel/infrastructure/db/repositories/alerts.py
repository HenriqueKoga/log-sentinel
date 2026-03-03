from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from logs_sentinel.domains.alerts.entities import (
    AlertEvent,
    AlertEventId,
    AlertRule,
    AlertRuleId,
    NotificationChannel,
    NotificationChannelId,
    NotificationChannelKind,
)
from logs_sentinel.domains.alerts.repositories import (
    AlertEventRepository,
    AlertRuleRepository,
    NotificationChannelRepository,
)
from logs_sentinel.domains.identity.entities import TenantId
from logs_sentinel.domains.ingestion.entities import ProjectId
from logs_sentinel.domains.issues.entities import IssueId
from logs_sentinel.infrastructure.db.models import (
    AlertEventModel,
    AlertRuleModel,
    NotificationChannelModel,
)


class AlertRuleRepositorySQLAlchemy(AlertRuleRepository):
    """SQLAlchemy-based repository for alert rules."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_rules(self, tenant_id: TenantId, project_id: ProjectId | None) -> list[AlertRule]:
        stmt = AlertRuleModel.__table__.select().where(
            AlertRuleModel.tenant_id == int(tenant_id),
        )
        if project_id is not None:
            stmt = stmt.where(AlertRuleModel.project_id == int(project_id))
        result = await self._session.execute(stmt)
        rules: list[AlertRule] = []
        for row in result.fetchall():
            model = AlertRuleModel(**row._mapping)
            rules.append(
                AlertRule(
                    id=AlertRuleId(model.id),
                    tenant_id=TenantId(model.tenant_id),
                    project_id=ProjectId(model.project_id),
                    name=model.name,
                    kind=model.kind,  # type: ignore[arg-type]
                    threshold=model.threshold,
                    enabled=model.enabled,
                )
            )
        return rules

    async def create_rule(
        self,
        tenant_id: TenantId,
        project_id: ProjectId,
        name: str,
        kind: str,
        threshold: float,
    ) -> AlertRule:
        model = AlertRuleModel(
            tenant_id=int(tenant_id),
            project_id=int(project_id),
            name=name,
            kind=kind,
            threshold=threshold,
            enabled=True,
        )
        self._session.add(model)
        await self._session.flush()
        return AlertRule(
            id=AlertRuleId(model.id),
            tenant_id=TenantId(model.tenant_id),
            project_id=ProjectId(model.project_id),
            name=model.name,
            kind=model.kind,  # type: ignore[arg-type]
            threshold=model.threshold,
            enabled=model.enabled,
        )

    async def get_rule(self, tenant_id: TenantId, rule_id: AlertRuleId) -> AlertRule | None:
        model = await self._session.get(AlertRuleModel, int(rule_id))
        if model is None or model.tenant_id != int(tenant_id):
            return None
        return AlertRule(
            id=AlertRuleId(model.id),
            tenant_id=TenantId(model.tenant_id),
            project_id=ProjectId(model.project_id),
            name=model.name,
            kind=model.kind,  # type: ignore[arg-type]
            threshold=model.threshold,
            enabled=model.enabled,
        )

    async def update_rule(
        self,
        tenant_id: TenantId,
        rule_id: AlertRuleId,
        *,
        name: str | None = None,
        threshold: float | None = None,
        enabled: bool | None = None,
    ) -> AlertRule | None:
        model = await self._session.get(AlertRuleModel, int(rule_id))
        if model is None or model.tenant_id != int(tenant_id):
            return None
        if name is not None:
            model.name = name
        if threshold is not None:
            model.threshold = threshold
        if enabled is not None:
            model.enabled = enabled
        await self._session.flush()
        return AlertRule(
            id=AlertRuleId(model.id),
            tenant_id=TenantId(model.tenant_id),
            project_id=ProjectId(model.project_id),
            name=model.name,
            kind=model.kind,  # type: ignore[arg-type]
            threshold=model.threshold,
            enabled=model.enabled,
        )

    async def delete_rule(self, tenant_id: TenantId, rule_id: AlertRuleId) -> None:
        model = await self._session.get(AlertRuleModel, int(rule_id))
        if model is None or model.tenant_id != int(tenant_id):
            return
        await self._session.delete(model)
        await self._session.flush()


class NotificationChannelRepositorySQLAlchemy(NotificationChannelRepository):
    """SQLAlchemy-based repository for notification channels."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_channels(self, tenant_id: TenantId) -> list[NotificationChannel]:
        stmt = NotificationChannelModel.__table__.select().where(
            NotificationChannelModel.tenant_id == int(tenant_id),
        )
        result = await self._session.execute(stmt)
        channels: list[NotificationChannel] = []
        for row in result.fetchall():
            model = NotificationChannelModel(**row._mapping)
            channels.append(
                NotificationChannel(
                    id=NotificationChannelId(model.id),
                    tenant_id=TenantId(model.tenant_id),
                    kind=NotificationChannelKind(model.kind),
                    config_json=model.config_json,
                    enabled=model.enabled,
                )
            )
        return channels

    async def create_channel(
        self,
        tenant_id: TenantId,
        kind: str,
        config_json: dict[str, Any],
    ) -> NotificationChannel:
        model = NotificationChannelModel(
            tenant_id=int(tenant_id),
            kind=kind,
            config_json=config_json,
            enabled=True,
        )
        self._session.add(model)
        await self._session.flush()
        return NotificationChannel(
            id=NotificationChannelId(model.id),
            tenant_id=TenantId(model.tenant_id),
            kind=NotificationChannelKind(model.kind),
            config_json=model.config_json,
            enabled=model.enabled,
        )

    async def update_channel(
        self,
        tenant_id: TenantId,
        channel_id: NotificationChannelId,
        *,
        enabled: bool | None = None,
        config_json: dict[str, Any] | None = None,
    ) -> NotificationChannel | None:
        model = await self._session.get(NotificationChannelModel, int(channel_id))
        if model is None or model.tenant_id != int(tenant_id):
            return None
        if enabled is not None:
            model.enabled = enabled
        if config_json is not None:
            model.config_json = config_json
        await self._session.flush()
        return NotificationChannel(
            id=NotificationChannelId(model.id),
            tenant_id=TenantId(model.tenant_id),
            kind=NotificationChannelKind(model.kind),
            config_json=model.config_json,
            enabled=model.enabled,
        )


class AlertEventRepositorySQLAlchemy(AlertEventRepository):
    """SQLAlchemy-based repository for alert events."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_event(
        self,
        tenant_id: TenantId,
        issue_id: IssueId,
        rule_id: AlertRuleId,
        triggered_at: datetime,
        payload_json: dict[str, object],
    ) -> AlertEvent:
        model = AlertEventModel(
            tenant_id=int(tenant_id),
            issue_id=int(issue_id),
            rule_id=int(rule_id),
            triggered_at=triggered_at,
            payload_json=payload_json,
        )
        self._session.add(model)
        await self._session.flush()
        return AlertEvent(
            id=AlertEventId(model.id),
            tenant_id=TenantId(model.tenant_id),
            issue_id=IssueId(model.issue_id),
            rule_id=AlertRuleId(model.rule_id),
            triggered_at=model.triggered_at,
            payload_json=model.payload_json,
        )

    async def list_events(
        self,
        tenant_id: TenantId,
        since: datetime | None,
        limit: int = 50,
    ) -> list[AlertEvent]:
        stmt = select(AlertEventModel).where(AlertEventModel.tenant_id == int(tenant_id))
        if since is not None:
            stmt = stmt.where(AlertEventModel.triggered_at >= since)
        stmt = stmt.order_by(AlertEventModel.triggered_at.desc()).limit(limit)
        result = await self._session.execute(stmt)
        events: list[AlertEvent] = []
        for row in result.scalars().all():
            model: AlertEventModel = row
            events.append(
                AlertEvent(
                    id=AlertEventId(model.id),
                    tenant_id=TenantId(model.tenant_id),
                    issue_id=IssueId(model.issue_id),
                    rule_id=AlertRuleId(model.rule_id),
                    triggered_at=model.triggered_at,
                    payload_json=model.payload_json,
                )
            )
        return events

