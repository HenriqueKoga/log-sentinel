from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class AlertKindEnum(StrEnum):
    COUNT_5M = "count_5m"
    SPIKE = "spike"


class NotificationChannelKindEnum(StrEnum):
    SLACK_WEBHOOK = "slack_webhook"


class AlertRuleCreateRequest(BaseModel):
    project_id: int
    name: str = Field(min_length=1, max_length=255)
    kind: AlertKindEnum
    threshold: float = Field(gt=0)


class AlertRuleUpdateRequest(BaseModel):
    name: str | None = None
    threshold: float | None = Field(default=None, gt=0)
    enabled: bool | None = None


class AlertRuleResponse(BaseModel):
    id: int
    project_id: int
    name: str
    kind: AlertKindEnum
    threshold: float
    enabled: bool


class NotificationChannelCreateRequest(BaseModel):
    kind: NotificationChannelKindEnum
    slack_webhook_url: str | None = None


class NotificationChannelUpdateRequest(BaseModel):
    enabled: bool | None = None


class NotificationChannelResponse(BaseModel):
    id: int
    kind: NotificationChannelKindEnum
    enabled: bool
    # For security, we do not echo back full secrets.
    display_name: str


class AlertEventResponse(BaseModel):
    id: int
    issue_id: int
    rule_id: int
    triggered_at: datetime
    payload: dict[str, object]
