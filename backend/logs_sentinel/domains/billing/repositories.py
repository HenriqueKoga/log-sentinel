from __future__ import annotations

from datetime import datetime
from typing import Protocol

from logs_sentinel.domains.identity.entities import TenantId

from .entities import TenantPlan, UsageCounter, UsagePeriod


class TenantPlanRepository(Protocol):
    """Repository for tenant billing plans."""

    async def get_active_plan(self, tenant_id: TenantId) -> TenantPlan | None: ...

    async def create_plan(
        self,
        tenant_id: TenantId,
        plan_type: str,
        starts_at: datetime,
        enable_llm_enrichment: bool = False,
    ) -> TenantPlan: ...

    async def set_plan_llm_enrichment(self, tenant_id: TenantId, enable: bool) -> None: ...


class UsageCounterRepository(Protocol):
    """Repository for tenant usage counters."""

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
        credits_delta: int,
    ) -> UsageCounter: ...
