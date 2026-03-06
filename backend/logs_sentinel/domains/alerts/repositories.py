from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Protocol

from logs_sentinel.domains.identity.entities import TenantId
from logs_sentinel.domains.ingestion.entities import ProjectId
from logs_sentinel.domains.issues.entities import IssueId

from .entities import AlertEvent, AlertRule, AlertRuleId, NotificationChannel


class AlertRuleRepository(Protocol):
    """Repository for alert rules."""

    async def list_rules(
        self, tenant_id: TenantId, project_id: ProjectId | None
    ) -> Sequence[AlertRule]: ...

    async def create_rule(
        self,
        tenant_id: TenantId,
        project_id: ProjectId,
        name: str,
        kind: str,
        threshold: float,
    ) -> AlertRule: ...

    async def get_rule(self, tenant_id: TenantId, rule_id: AlertRuleId) -> AlertRule | None: ...


class NotificationChannelRepository(Protocol):
    """Repository for notification channels (e.g., Slack)."""

    async def list_channels(self, tenant_id: TenantId) -> Sequence[NotificationChannel]: ...


class AlertEventRepository(Protocol):
    """Repository for fired alert events."""

    async def create_event(
        self,
        tenant_id: TenantId,
        issue_id: IssueId,
        rule_id: AlertRuleId,
        triggered_at: datetime,
        payload_json: dict[str, object],
    ) -> AlertEvent: ...

    async def list_events(
        self,
        tenant_id: TenantId,
        since: datetime | None,
        limit: int = 50,
    ) -> Sequence[AlertEvent]: ...
