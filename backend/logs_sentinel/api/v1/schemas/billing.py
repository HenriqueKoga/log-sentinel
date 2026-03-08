from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


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
    enable_llm_enrichment: bool = False
    monthly_credits_limit: float = 1000.0


class BillingUsageResponse(BaseModel):
    plan_type: PlanTypeEnum
    period_start: datetime
    events_ingested: int = 0
    llm_enrichments: int = 0


class CreditBarResponse(BaseModel):
    credits_used: float
    credits_limit: float
    percentage: float
    period_start: datetime
    period_end: datetime


class SettingsUpdateRequest(BaseModel):
    enable_llm_enrichment: bool



class LlmModelIn(BaseModel):
    provider: str = Field(min_length=1, max_length=64)
    model_name: str = Field(min_length=1, max_length=128)
    display_name: str = Field(min_length=1, max_length=255)
    input_token_price: float = Field(ge=0)
    output_token_price: float = Field(ge=0)
    currency: str = Field(default="USD", max_length=8)
    is_active: bool = True
    supports_usage_tracking: bool = True


class LlmModelOut(BaseModel):
    id: int
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


class LlmModelsListResponse(BaseModel):
    items: list[LlmModelOut]


class LlmModelUpdateIn(BaseModel):
    display_name: str | None = None
    input_token_price: float | None = Field(default=None, ge=0)
    output_token_price: float | None = Field(default=None, ge=0)
    currency: str | None = None
    is_active: bool | None = None
    supports_usage_tracking: bool | None = None

class CreditPolicyOut(BaseModel):
    id: int
    name: str
    currency: str
    credits_per_currency_unit: float
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ModelBreakdownOut(BaseModel):
    model_id: int
    model_name: str
    display_name: str
    input_tokens: int
    output_tokens: int
    total_cost: float
    credits_used: float


class FeatureBreakdownOut(BaseModel):
    feature: str
    input_tokens: int
    output_tokens: int
    total_cost: float
    credits_used: float


class LlmUsageTotals(BaseModel):
    input_tokens: int
    output_tokens: int
    total_cost: float
    credits_used: float


class LlmUsageSummaryResponse(BaseModel):
    period_start: datetime
    period_end: datetime
    totals: LlmUsageTotals
    by_model: list[ModelBreakdownOut]
    by_feature: list[FeatureBreakdownOut]
