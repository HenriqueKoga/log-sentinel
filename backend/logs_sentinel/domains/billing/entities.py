from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import NewType

from logs_sentinel.domains.identity.entities import TenantId

TenantPlanId = NewType("TenantPlanId", int)
UsageCounterId = NewType("UsageCounterId", int)
LlmModelId = NewType("LlmModelId", int)
LlmUsageId = NewType("LlmUsageId", int)
CreditPolicyId = NewType("CreditPolicyId", int)


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


class LlmFeature(StrEnum):
    """Known LLM features for usage tracking."""

    ISSUE_SUGGEST = "issue_suggest"
    ISSUE_ENRICH = "issue_enrich"
    FIX_SUGGESTION = "fix_suggestion"
    LOG_CHAT = "log_chat"
    CHAT_TITLE = "chat_title"


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
    monthly_credits_limit: float = 1000.0


@dataclass(slots=True)
class UsageCounter:
    """Aggregated operational counter for a tenant and period."""

    id: UsageCounterId
    tenant_id: TenantId
    period_start: datetime
    period: UsagePeriod
    events_ingested: int
    llm_enrichments: int


@dataclass(slots=True)
class LlmModel:
    """Catalogue entry for an LLM model with pricing."""

    id: LlmModelId
    provider: str
    model_name: str
    display_name: str
    input_token_price: float
    output_token_price: float
    currency: str
    is_active: bool
    supports_usage_tracking: bool
    created_at: datetime
    updated_at: datetime


@dataclass(slots=True)
class LlmUsage:
    """Raw usage record of a single LLM call."""

    id: LlmUsageId
    tenant_id: TenantId
    project_id: int | None
    user_id: int | None
    llm_model_id: LlmModelId
    feature_name: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    correlation_id: str | None
    metadata_json: dict[str, object] | None
    created_at: datetime


@dataclass(slots=True)
class CreditPolicy:
    """Conversion policy from real cost to billing credits."""

    id: CreditPolicyId
    name: str
    currency: str
    credits_per_currency_unit: float
    is_active: bool
    created_at: datetime
    updated_at: datetime
