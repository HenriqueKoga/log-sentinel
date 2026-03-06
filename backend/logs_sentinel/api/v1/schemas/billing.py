from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel


class PlanTypeEnum(StrEnum):
    MONTHLY = "monthly"
    YEARLY = "yearly"
    UNLIMITED = "unlimited"


class PlanStatusEnum(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class BillingPlanResponse(BaseModel):
    plan_type: PlanTypeEnum
    status: PlanStatusEnum
    starts_at: datetime
    ends_at: datetime | None
    limit: int | None
    enable_llm_enrichment: bool = False


class BillingUsageResponse(BaseModel):
    plan_type: PlanTypeEnum
    period_start: datetime
    used: int
    limit: int | None
    events_ingested: int = 0
    llm_enrichments: int = 0


class SettingsUpdateRequest(BaseModel):
    enable_llm_enrichment: bool
