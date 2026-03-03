from __future__ import annotations

from datetime import datetime
from typing import Protocol

from logs_sentinel.domains.identity.entities import TenantId

from .entities import TenantPlan, UsageCounter, UsagePeriod


class TenantPlanRepository(Protocol):
    """Repository for tenant billing plans."""

    async def get_active_plan(self, tenant_id: TenantId) -> TenantPlan | None:
        ...

    async def create_plan(
        self,
        tenant_id: TenantId,
        plan_type: str,
        starts_at: datetime,
    ) -> TenantPlan:
        ...


class UsageCounterRepository(Protocol):
    """Repository for tenant usage counters."""

    async def get_counter(
        self,
        tenant_id: TenantId,
        period_start: datetime,
        period: UsagePeriod,
    ) -> UsageCounter | None:
        ...

    async def increment_counter(
        self,
        tenant_id: TenantId,
        period_start: datetime,
        period: UsagePeriod,
        delta: int,
    ) -> UsageCounter:
        ...

