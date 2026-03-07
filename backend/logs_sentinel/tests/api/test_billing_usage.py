from __future__ import annotations

from datetime import datetime

import pytest

from logs_sentinel.application.services.billing_service import BillingService
from logs_sentinel.domains.billing.entities import (
    PlanStatus,
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
        enable_llm_enrichment: bool = False,
    ) -> TenantPlan:
        plan = TenantPlan(
            id=TenantPlanId(self._next_id),
            tenant_id=tenant_id,
            plan_type=PlanType(plan_type),
            starts_at=starts_at,
            ends_at=None,
            status=PlanStatus.ACTIVE,
            enable_llm_enrichment=enable_llm_enrichment,
        )
        self._next_id += 1
        self._plans[int(tenant_id)] = plan
        return plan

    async def set_plan_llm_enrichment(self, tenant_id: TenantId, enable: bool) -> None:
        plan = self._plans.get(int(tenant_id))
        if plan is not None:
            self._plans[int(tenant_id)] = TenantPlan(
                id=plan.id,
                tenant_id=plan.tenant_id,
                plan_type=plan.plan_type,
                starts_at=plan.starts_at,
                ends_at=plan.ends_at,
                status=plan.status,
                enable_llm_enrichment=enable,
            )


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
        events_delta: int,
        llm_delta: int,
        credits_delta: int,
    ) -> UsageCounter:
        key = (int(tenant_id), period_start, period.value)
        existing = self._counters.get(key)
        if existing is None:
            counter = UsageCounter(
                id=UsageCounterId(self._next_id),
                tenant_id=tenant_id,
                period_start=period_start,
                period=period,
                events_ingested=events_delta,
                llm_enrichments=llm_delta,
                credits_used=credits_delta,
            )
            self._next_id += 1
            self._counters[key] = counter
            return counter
        existing.events_ingested += events_delta
        existing.llm_enrichments += llm_delta
        existing.credits_used += credits_delta
        return existing


@pytest.mark.asyncio
async def test_billing_allows_within_monthly_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    plans = InMemoryTenantPlanRepo()
    usage = InMemoryUsageCounterRepo()
    service = BillingService(plans_repo=plans, usage_repo=usage)

    from logs_sentinel.infrastructure.settings import config as config_module

    monkeypatch.setattr(config_module.settings, "default_plan", "monthly", raising=False)
    monkeypatch.setattr(config_module.settings, "credits_per_event", 1, raising=False)
    monkeypatch.setattr(config_module.settings, "monthly_credits_limit", 10, raising=False)

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
    monkeypatch.setattr(config_module.settings, "credits_per_event", 1, raising=False)
    monkeypatch.setattr(config_module.settings, "monthly_credits_limit", 5, raising=False)

    tenant_id = TenantId(1)
    await service.check_and_increment(tenant_id=tenant_id, events=5)

    with pytest.raises(ValueError) as exc:
        await service.check_and_increment(tenant_id=tenant_id, events=1)
    assert str(exc.value) == "USAGE_LIMIT_EXCEEDED"


@pytest.mark.asyncio
async def test_is_llm_enabled_when_plan_has_llm() -> None:
    plans = InMemoryTenantPlanRepo()
    usage = InMemoryUsageCounterRepo()
    service = BillingService(plans_repo=plans, usage_repo=usage)
    tenant_id = TenantId(1)
    await plans.create_plan(
        tenant_id=tenant_id,
        plan_type="monthly",
        starts_at=datetime.now(),
        enable_llm_enrichment=True,
    )
    assert await service.is_llm_enabled(tenant_id) is True


@pytest.mark.asyncio
async def test_is_llm_enabled_false_when_no_plan() -> None:
    plans = InMemoryTenantPlanRepo()
    usage = InMemoryUsageCounterRepo()
    service = BillingService(plans_repo=plans, usage_repo=usage)
    assert await service.is_llm_enabled(TenantId(1)) is False


@pytest.mark.asyncio
async def test_record_llm_usage_raises_when_limit_exceeded(monkeypatch: pytest.MonkeyPatch) -> None:
    from logs_sentinel.infrastructure.settings import config as config_module

    plans = InMemoryTenantPlanRepo()
    usage = InMemoryUsageCounterRepo()
    await plans.create_plan(
        tenant_id=TenantId(1),
        plan_type="monthly",
        starts_at=datetime.now(),
        enable_llm_enrichment=True,
    )
    monkeypatch.setattr(config_module.settings, "default_plan", "monthly", raising=False)
    monkeypatch.setattr(config_module.settings, "monthly_credits_limit", 1, raising=False)
    monkeypatch.setattr(config_module.settings, "credits_per_llm_enrichment", 10, raising=False)
    service = BillingService(plans_repo=plans, usage_repo=usage)
    with pytest.raises(ValueError) as exc:
        await service.record_llm_usage(TenantId(1))
    assert str(exc.value) == "USAGE_LIMIT_EXCEEDED"


@pytest.mark.asyncio
async def test_get_usage_summary() -> None:
    plans = InMemoryTenantPlanRepo()
    usage = InMemoryUsageCounterRepo()
    service = BillingService(plans_repo=plans, usage_repo=usage)
    tenant_id = TenantId(1)
    summary = await service.get_usage_summary(tenant_id)
    assert summary.tenant_id == tenant_id
    assert summary.used == 0
