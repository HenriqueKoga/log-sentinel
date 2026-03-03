from __future__ import annotations

from datetime import datetime

import pytest

from logs_sentinel.application.services.billing_service import BillingService
from logs_sentinel.domains.billing.entities import (
    PlanType,
    TenantPlan,
    TenantPlanId,
    UsageCounter,
    UsageCounterId,
    UsagePeriod,
)
from logs_sentinel.domains.billing.repositories import TenantPlanRepository, UsageCounterRepository
from logs_sentinel.domains.identity.entities import TenantId


class InMemoryTenantPlanRepo(TenantPlanRepository):
    def __init__(self) -> None:
        self._plans: dict[int, TenantPlan] = {}
        self._next_id = 1

    async def get_active_plan(self, tenant_id: TenantId) -> TenantPlan | None:
        return self._plans.get(int(tenant_id))

    async def create_plan(
        self,
        tenant_id: TenantId,
        plan_type: str,
        starts_at: datetime,
    ) -> TenantPlan:
        plan = TenantPlan(
            id=TenantPlanId(self._next_id),
            tenant_id=tenant_id,
            plan_type=PlanType(plan_type),
            starts_at=starts_at,
            ends_at=None,
            status="active",  # type: ignore[arg-type]
        )
        self._next_id += 1
        self._plans[int(tenant_id)] = plan
        return plan


class InMemoryUsageCounterRepo(UsageCounterRepository):
    def __init__(self) -> None:
        self._counters: dict[tuple[int, datetime, str], UsageCounter] = {}
        self._next_id = 1

    async def get_counter(
        self,
        tenant_id: TenantId,
        period_start: datetime,
        period: UsagePeriod,
    ) -> UsageCounter | None:
        return self._counters.get((int(tenant_id), period_start, period.value))

    async def increment_counter(
        self,
        tenant_id: TenantId,
        period_start: datetime,
        period: UsagePeriod,
        delta: int,
    ) -> UsageCounter:
        key = (int(tenant_id), period_start, period.value)
        existing = self._counters.get(key)
        if existing is None:
            counter = UsageCounter(
                id=UsageCounterId(self._next_id),
                tenant_id=tenant_id,
                period_start=period_start,
                period=period,
                events_ingested=delta,
            )
            self._next_id += 1
            self._counters[key] = counter
            return counter
        existing.events_ingested += delta
        return existing


@pytest.mark.asyncio
async def test_billing_allows_within_monthly_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    plans = InMemoryTenantPlanRepo()
    usage = InMemoryUsageCounterRepo()
    service = BillingService(plans_repo=plans, usage_repo=usage)

    # Force plan type to MONTHLY and a high limit for the test.
    from logs_sentinel.infrastructure.settings import config as config_module

    monkeypatch.setattr(config_module.settings, "default_plan", "monthly", raising=False)
    monkeypatch.setattr(config_module.settings, "monthly_events_limit", 10, raising=False)

    tenant_id = TenantId(1)
    result = await service.check_and_increment(tenant_id=tenant_id, events=5)
    assert result.used == 5
    assert result.plan_type == PlanType.MONTHLY


@pytest.mark.asyncio
async def test_billing_raises_when_limit_exceeded(monkeypatch: pytest.MonkeyPatch) -> None:
    plans = InMemoryTenantPlanRepo()
    usage = InMemoryUsageCounterRepo()
    service = BillingService(plans_repo=plans, usage_repo=usage)

    from logs_sentinel.infrastructure.settings import config as config_module

    monkeypatch.setattr(config_module.settings, "default_plan", "monthly", raising=False)
    monkeypatch.setattr(config_module.settings, "monthly_events_limit", 5, raising=False)

    tenant_id = TenantId(1)
    await service.check_and_increment(tenant_id=tenant_id, events=5)

    with pytest.raises(ValueError) as exc:
        await service.check_and_increment(tenant_id=tenant_id, events=1)
    assert str(exc.value) == "USAGE_LIMIT_EXCEEDED"

