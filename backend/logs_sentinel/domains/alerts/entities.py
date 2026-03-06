from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any, NewType

from logs_sentinel.domains.identity.entities import TenantId
from logs_sentinel.domains.ingestion.entities import ProjectId
from logs_sentinel.domains.issues.entities import IssueId

AlertRuleId = NewType("AlertRuleId", int)
NotificationChannelId = NewType("NotificationChannelId", int)
AlertEventId = NewType("AlertEventId", int)


class AlertKind(StrEnum):
    """Kinds of alert rules supported."""

    COUNT_5M = "count_5m"
    SPIKE = "spike"


@dataclass(slots=True)
class AlertRule:
    """Alert rule bound to a project and tenant."""

    id: AlertRuleId
    tenant_id: TenantId
    project_id: ProjectId
    name: str
    kind: AlertKind
    threshold: float
    enabled: bool


class NotificationChannelKind(StrEnum):
    """Supported notification channel types."""

    SLACK_WEBHOOK = "slack_webhook"


@dataclass(slots=True)
class NotificationChannel:
    """Represents a delivery channel for alerts."""

    id: NotificationChannelId
    tenant_id: TenantId
    kind: NotificationChannelKind
    config_json: dict[str, Any]
    enabled: bool


@dataclass(slots=True)
class AlertEvent:
    """Represents a fired alert for a specific issue and rule."""

    id: AlertEventId
    tenant_id: TenantId
    issue_id: IssueId
    rule_id: AlertRuleId
    triggered_at: datetime
    payload_json: dict[str, Any]
