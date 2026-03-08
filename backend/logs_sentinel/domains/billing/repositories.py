from __future__ import annotations

from datetime import datetime
from typing import Protocol

from logs_sentinel.domains.identity.entities import TenantId

from .entities import (
    CreditPolicy,
    LlmModel,
    LlmModelId,
    LlmUsage,
    TenantPlan,
    UsageCounter,
    UsagePeriod,
)


class TenantPlanRepository(Protocol):
    """Repository for tenant billing plans."""

    async def get_active_plan(self, tenant_id: TenantId) -> TenantPlan | None: ...

    async def create_plan(
        self,
        tenant_id: TenantId,
        plan_type: str,
        starts_at: datetime,
        enable_llm_enrichment: bool = False,
        monthly_credits_limit: float = 1000.0,
    ) -> TenantPlan: ...

    async def set_plan_llm_enrichment(self, tenant_id: TenantId, enable: bool) -> None: ...

    async def set_monthly_credits_limit(self, tenant_id: TenantId, limit: float) -> None: ...


class UsageCounterRepository(Protocol):
    """Repository for tenant operational usage counters (no credits)."""

    async def get_counter(
        self,
        tenant_id: TenantId,
        period_start: datetime,
        period: UsagePeriod,
    ) -> UsageCounter | None: ...

    async def increment_counter(
        self,
        tenant_id: TenantId,
        period_start: datetime,
        period: UsagePeriod,
        events_delta: int,
        llm_delta: int,
    ) -> UsageCounter: ...


class LlmModelRepository(Protocol):
    """Repository for the LLM model catalogue."""

    async def get_by_id(self, model_id: LlmModelId) -> LlmModel | None: ...

    async def get_by_name(self, provider: str, model_name: str) -> LlmModel | None: ...

    async def list_models(self, *, active_only: bool = True) -> list[LlmModel]: ...

    async def create(self, model: LlmModel) -> LlmModel: ...

    async def update(self, model: LlmModel) -> LlmModel: ...


class LlmUsageRepository(Protocol):
    """Repository for raw LLM usage records."""

    async def record(self, usage: LlmUsage) -> LlmUsage: ...

    async def list_by_tenant(
        self,
        tenant_id: TenantId,
        *,
        period_start: datetime,
        period_end: datetime,
        project_id: int | None = None,
    ) -> list[LlmUsage]: ...


class CreditPolicyRepository(Protocol):
    """Repository for credit conversion policies."""

    async def get_active(self) -> CreditPolicy | None: ...

    async def list_policies(self) -> list[CreditPolicy]: ...

    async def create(self, policy: CreditPolicy) -> CreditPolicy: ...

    async def update(self, policy: CreditPolicy) -> CreditPolicy: ...
