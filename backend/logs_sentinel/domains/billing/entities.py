from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import NewType

from logs_sentinel.domains.identity.entities import TenantId

TenantPlanId = NewType("TenantPlanId", int)
UsageCounterId = NewType("UsageCounterId", int)


class PlanType(StrEnum):
    """Supported billing plan types."""

    MONTHLY = "monthly"
    YEARLY = "yearly"
    UNLIMITED = "unlimited"


class PlanStatus(StrEnum):
    """State of a tenant plan."""

    ACTIVE = "active"
    INACTIVE = "inactive"


class UsagePeriod(StrEnum):
    """Granularity for usage counters."""

    MONTH = "month"


@dataclass(slots=True)
class TenantPlan:
    """Plan configuration for a given tenant."""

    id: TenantPlanId
    tenant_id: TenantId
    plan_type: PlanType
    starts_at: datetime
    ends_at: datetime | None
    status: PlanStatus
    enable_llm_enrichment: bool


@dataclass(slots=True)
class UsageCounter:
    """Aggregated usage for a tenant and period (credits = billing unit)."""

    id: UsageCounterId
    tenant_id: TenantId
    period_start: datetime
    period: UsagePeriod
    events_ingested: int
    llm_enrichments: int
    credits_used: int
