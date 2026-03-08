"""Unit tests for BillingService (new architecture: no credits_used persisted)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from logs_sentinel.application.services.billing_service import BillingService
from logs_sentinel.domains.billing.entities import (
    CreditPolicy,
    CreditPolicyId,
    LlmModel,
    LlmModelId,
    LlmUsage,
    LlmUsageId,
    PlanStatus,
    PlanType,
    TenantPlan,
    TenantPlanId,
    UsageCounter,
    UsageCounterId,
    UsagePeriod,
)
from logs_sentinel.domains.billing.repositories import (
    CreditPolicyRepository,
    LlmModelRepository,
    LlmUsageRepository,
    TenantPlanRepository,
    UsageCounterRepository,
)
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
        monthly_credits_limit: float = 1000.0,
    ) -> TenantPlan:
        plan = TenantPlan(
            id=TenantPlanId(self._next_id),
            tenant_id=tenant_id,
            plan_type=PlanType(plan_type),
            starts_at=starts_at,
            ends_at=None,
            status=PlanStatus.ACTIVE,
            enable_llm_enrichment=enable_llm_enrichment,
            monthly_credits_limit=monthly_credits_limit,
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
                monthly_credits_limit=plan.monthly_credits_limit,
            )

    async def set_monthly_credits_limit(self, tenant_id: TenantId, limit: float) -> None:
        plan = self._plans.get(int(tenant_id))
        if plan is not None:
            self._plans[int(tenant_id)] = TenantPlan(
                id=plan.id,
                tenant_id=plan.tenant_id,
                plan_type=plan.plan_type,
                starts_at=plan.starts_at,
                ends_at=plan.ends_at,
                status=plan.status,
                enable_llm_enrichment=plan.enable_llm_enrichment,
                monthly_credits_limit=limit,
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
            )
            self._next_id += 1
            self._counters[key] = counter
            return counter
        existing.events_ingested += events_delta
        existing.llm_enrichments += llm_delta
        return existing


class InMemoryLlmModelRepo(LlmModelRepository):
    def __init__(self) -> None:
        self._models: dict[int, LlmModel] = {}
        self._next_id = 1

    async def get_by_id(self, model_id: LlmModelId) -> LlmModel | None:
        return self._models.get(int(model_id))

    async def get_by_name(self, provider: str, model_name: str) -> LlmModel | None:
        for m in self._models.values():
            if m.provider == provider and m.model_name == model_name:
                return m
        return None

    async def list_models(self, *, active_only: bool = True) -> list[LlmModel]:
        return [m for m in self._models.values() if not active_only or m.is_active]

    async def create(self, model: LlmModel) -> LlmModel:
        mid = LlmModelId(self._next_id)
        self._next_id += 1
        saved = LlmModel(
            id=mid,
            provider=model.provider,
            model_name=model.model_name,
            display_name=model.display_name,
            input_token_price=model.input_token_price,
            output_token_price=model.output_token_price,
            currency=model.currency,
            is_active=model.is_active,
            supports_usage_tracking=model.supports_usage_tracking,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
        self._models[int(mid)] = saved
        return saved

    async def update(self, model: LlmModel) -> LlmModel:
        self._models[int(model.id)] = model
        return model


class InMemoryLlmUsageRepo(LlmUsageRepository):
    def __init__(self) -> None:
        self._records: list[LlmUsage] = []
        self._next_id = 1

    async def record(self, usage: LlmUsage) -> LlmUsage:
        saved = LlmUsage(
            id=LlmUsageId(self._next_id),
            tenant_id=usage.tenant_id,
            project_id=usage.project_id,
            user_id=usage.user_id,
            llm_model_id=usage.llm_model_id,
            feature_name=usage.feature_name,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            total_tokens=usage.total_tokens,
            correlation_id=usage.correlation_id,
            metadata_json=usage.metadata_json,
            created_at=usage.created_at,
        )
        self._next_id += 1
        self._records.append(saved)
        return saved

    async def list_by_tenant(
        self,
        tenant_id: TenantId,
        *,
        period_start: datetime,
        period_end: datetime,
        project_id: int | None = None,
    ) -> list[LlmUsage]:
        results = []
        for r in self._records:
            if int(r.tenant_id) != int(tenant_id):
                continue
            if r.created_at < period_start or r.created_at >= period_end:
                continue
            if project_id is not None and r.project_id != project_id:
                continue
            results.append(r)
        return results


class InMemoryCreditPolicyRepo(CreditPolicyRepository):
    def __init__(self, policy: CreditPolicy | None = None) -> None:
        self._policies: list[CreditPolicy] = [policy] if policy else []

    async def get_active(self) -> CreditPolicy | None:
        for p in self._policies:
            if p.is_active:
                return p
        return None

    async def list_policies(self) -> list[CreditPolicy]:
        return list(self._policies)

    async def create(self, policy: CreditPolicy) -> CreditPolicy:
        self._policies.append(policy)
        return policy

    async def update(self, policy: CreditPolicy) -> CreditPolicy:
        self._policies = [policy if p.id == policy.id else p for p in self._policies]
        return policy


def _now() -> datetime:
    return datetime.now(tz=UTC)


def _default_policy() -> CreditPolicy:
    now = _now()
    return CreditPolicy(
        id=CreditPolicyId(1), name="default", currency="USD",
        credits_per_currency_unit=100.0, is_active=True,
        created_at=now, updated_at=now,
    )


async def _seed_gpt4o_mini(repo: InMemoryLlmModelRepo) -> LlmModel:
    now = _now()
    return await repo.create(LlmModel(
        id=LlmModelId(0), provider="openai", model_name="gpt-4o-mini",
        display_name="GPT-4o Mini",
        input_token_price=0.00000015, output_token_price=0.0000006,
        currency="USD", is_active=True, supports_usage_tracking=True,
        created_at=now, updated_at=now,
    ))


def _make_service(
    *,
    plans: InMemoryTenantPlanRepo | None = None,
    usage: InMemoryUsageCounterRepo | None = None,
    llm_models: InMemoryLlmModelRepo | None = None,
    llm_usage: InMemoryLlmUsageRepo | None = None,
    credit_policy: InMemoryCreditPolicyRepo | None = None,
) -> BillingService:
    return BillingService(
        plans_repo=plans or InMemoryTenantPlanRepo(),
        usage_repo=usage or InMemoryUsageCounterRepo(),
        llm_model_repo=llm_models,
        llm_usage_repo=llm_usage,
        credit_policy_repo=credit_policy,
    )


@pytest.mark.asyncio
async def test_increment_events_creates_plan_and_counts() -> None:
    service = _make_service()
    result = await service.increment_events(TenantId(1), events=5)
    assert result.events_ingested == 5
    assert result.llm_enrichments == 0
    assert result.plan_type == PlanType.MONTHLY


@pytest.mark.asyncio
async def test_is_llm_enabled_when_plan_has_llm() -> None:
    plans = InMemoryTenantPlanRepo()
    await plans.create_plan(TenantId(1), "monthly", _now(), enable_llm_enrichment=True)
    service = _make_service(plans=plans)
    assert await service.is_llm_enabled(TenantId(1)) is True


@pytest.mark.asyncio
async def test_is_llm_enabled_false_when_no_plan() -> None:
    service = _make_service()
    assert await service.is_llm_enabled(TenantId(1)) is False


@pytest.mark.asyncio
async def test_get_usage_summary_zero_when_no_counter() -> None:
    service = _make_service()
    summary = await service.get_usage_summary(TenantId(1))
    assert summary.events_ingested == 0
    assert summary.llm_enrichments == 0


@pytest.mark.asyncio
async def test_record_llm_usage_creates_record() -> None:
    llm_models = InMemoryLlmModelRepo()
    llm_usage = InMemoryLlmUsageRepo()
    model = await _seed_gpt4o_mini(llm_models)
    service = _make_service(llm_models=llm_models, llm_usage=llm_usage)

    rec = await service.record_llm_usage(
        tenant_id=TenantId(1), feature_name="log_chat",
        model_name="gpt-4o-mini", input_tokens=100, output_tokens=50,
    )
    assert rec is not None
    assert rec.llm_model_id == model.id
    assert rec.input_tokens == 100
    assert rec.output_tokens == 50
    assert rec.total_tokens == 150


@pytest.mark.asyncio
async def test_record_llm_usage_unknown_model_returns_none() -> None:
    llm_models = InMemoryLlmModelRepo()
    llm_usage = InMemoryLlmUsageRepo()
    service = _make_service(llm_models=llm_models, llm_usage=llm_usage)

    rec = await service.record_llm_usage(
        tenant_id=TenantId(1), feature_name="log_chat",
        model_name="unknown-model", input_tokens=100, output_tokens=50,
    )
    assert rec is None


@pytest.mark.asyncio
async def test_record_llm_usage_increments_llm_counter() -> None:
    llm_models = InMemoryLlmModelRepo()
    llm_usage_repo = InMemoryLlmUsageRepo()
    usage_counter = InMemoryUsageCounterRepo()
    await _seed_gpt4o_mini(llm_models)
    service = _make_service(
        usage=usage_counter, llm_models=llm_models, llm_usage=llm_usage_repo,
    )

    await service.record_llm_usage(
        tenant_id=TenantId(1), feature_name="log_chat",
        model_name="gpt-4o-mini", input_tokens=100, output_tokens=50,
    )
    summary = await service.get_usage_summary(TenantId(1))
    assert summary.llm_enrichments == 1


@pytest.mark.asyncio
async def test_record_llm_usage_returns_none_without_repos() -> None:
    service = _make_service()
    rec = await service.record_llm_usage(
        tenant_id=TenantId(1), feature_name="log_chat",
        model_name="gpt-4o-mini", input_tokens=100, output_tokens=50,
    )
    assert rec is None


@pytest.mark.asyncio
async def test_llm_usage_summary_calculates_cost_and_credits() -> None:
    now = _now()
    llm_models = InMemoryLlmModelRepo()
    llm_usage = InMemoryLlmUsageRepo()
    policy = _default_policy()
    credit_policy = InMemoryCreditPolicyRepo(policy)

    model = await _seed_gpt4o_mini(llm_models)
    service = _make_service(
        llm_models=llm_models, llm_usage=llm_usage, credit_policy=credit_policy,
    )

    await service.record_llm_usage(
        tenant_id=TenantId(1), feature_name="log_chat",
        model_name="gpt-4o-mini", input_tokens=1000, output_tokens=500,
    )

    period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    from datetime import timedelta
    period_end = now + timedelta(days=1)

    summary = await service.get_llm_usage_summary(
        TenantId(1), period_start, period_end,
    )

    expected_input_cost = 1000 * model.input_token_price
    expected_output_cost = 500 * model.output_token_price
    expected_total_cost = expected_input_cost + expected_output_cost
    expected_credits = expected_total_cost * 100.0

    assert summary.totals_input_tokens == 1000
    assert summary.totals_output_tokens == 500
    assert abs(summary.totals_cost - expected_total_cost) < 1e-10
    assert abs(summary.totals_credits - expected_credits) < 1e-8
    assert len(summary.by_model) == 1
    assert summary.by_model[0].model_name == "gpt-4o-mini"
    assert len(summary.by_feature) == 1
    assert summary.by_feature[0].feature == "log_chat"


@pytest.mark.asyncio
async def test_llm_usage_summary_aggregates_multiple_features() -> None:
    now = _now()
    llm_models = InMemoryLlmModelRepo()
    llm_usage = InMemoryLlmUsageRepo()
    credit_policy = InMemoryCreditPolicyRepo(_default_policy())

    await _seed_gpt4o_mini(llm_models)
    service = _make_service(
        llm_models=llm_models, llm_usage=llm_usage, credit_policy=credit_policy,
    )

    await service.record_llm_usage(
        tenant_id=TenantId(1), feature_name="log_chat",
        model_name="gpt-4o-mini", input_tokens=1000, output_tokens=500,
    )
    await service.record_llm_usage(
        tenant_id=TenantId(1), feature_name="issue_enrich",
        model_name="gpt-4o-mini", input_tokens=2000, output_tokens=800,
    )

    from datetime import timedelta
    period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    period_end = now + timedelta(days=1)

    summary = await service.get_llm_usage_summary(TenantId(1), period_start, period_end)
    assert summary.totals_input_tokens == 3000
    assert summary.totals_output_tokens == 1300
    assert len(summary.by_feature) == 2
    assert len(summary.by_model) == 1


@pytest.mark.asyncio
async def test_llm_usage_summary_empty_without_repos() -> None:
    service = _make_service()
    now = _now()
    from datetime import timedelta
    summary = await service.get_llm_usage_summary(
        TenantId(1), now, now + timedelta(days=1),
    )
    assert summary.totals_input_tokens == 0
    assert summary.totals_credits == 0.0


@pytest.mark.asyncio
async def test_llm_usage_summary_no_policy_uses_default_ratio() -> None:
    now = _now()
    llm_models = InMemoryLlmModelRepo()
    llm_usage = InMemoryLlmUsageRepo()
    credit_policy = InMemoryCreditPolicyRepo()

    await _seed_gpt4o_mini(llm_models)
    service = _make_service(
        llm_models=llm_models, llm_usage=llm_usage, credit_policy=credit_policy,
    )

    await service.record_llm_usage(
        tenant_id=TenantId(1), feature_name="log_chat",
        model_name="gpt-4o-mini", input_tokens=1000, output_tokens=500,
    )

    from datetime import timedelta
    period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    period_end = now + timedelta(days=1)

    summary = await service.get_llm_usage_summary(TenantId(1), period_start, period_end)
    assert summary.totals_credits == summary.totals_cost * 100.0


@pytest.mark.asyncio
async def test_record_llm_usage_with_provider_slash_format() -> None:
    llm_models = InMemoryLlmModelRepo()
    llm_usage = InMemoryLlmUsageRepo()
    await _seed_gpt4o_mini(llm_models)
    service = _make_service(llm_models=llm_models, llm_usage=llm_usage)

    rec = await service.record_llm_usage(
        tenant_id=TenantId(1), feature_name="log_chat",
        model_name="openai/gpt-4o-mini", input_tokens=100, output_tokens=50,
    )
    assert rec is not None
    assert rec.input_tokens == 100


@pytest.mark.asyncio
async def test_credit_bar_returns_zero_when_no_usage() -> None:
    plans = InMemoryTenantPlanRepo()
    await plans.create_plan(TenantId(1), "monthly", _now(), monthly_credits_limit=500.0)
    service = _make_service(
        plans=plans,
        llm_models=InMemoryLlmModelRepo(),
        llm_usage=InMemoryLlmUsageRepo(),
        credit_policy=InMemoryCreditPolicyRepo(_default_policy()),
    )
    bar = await service.get_credit_bar(TenantId(1))
    assert bar.credits_used == 0.0
    assert bar.credits_limit == 500.0
    assert bar.percentage == 0.0


@pytest.mark.asyncio
async def test_credit_bar_calculates_percentage() -> None:
    plans = InMemoryTenantPlanRepo()
    await plans.create_plan(TenantId(1), "monthly", _now(), monthly_credits_limit=100.0)
    llm_models = InMemoryLlmModelRepo()
    llm_usage = InMemoryLlmUsageRepo()
    policy = _default_policy()
    credit_policy = InMemoryCreditPolicyRepo(policy)
    await _seed_gpt4o_mini(llm_models)

    service = _make_service(
        plans=plans,
        llm_models=llm_models,
        llm_usage=llm_usage,
        credit_policy=credit_policy,
    )
    await service.record_llm_usage(
        tenant_id=TenantId(1), feature_name="log_chat",
        model_name="gpt-4o-mini", input_tokens=1000, output_tokens=500,
    )
    bar = await service.get_credit_bar(TenantId(1))
    assert bar.credits_used > 0
    assert bar.credits_limit == 100.0
    assert 0 < bar.percentage <= 100.0


@pytest.mark.asyncio
async def test_would_exceed_credit_limit_false_when_under() -> None:
    plans = InMemoryTenantPlanRepo()
    await plans.create_plan(TenantId(1), "monthly", _now(), monthly_credits_limit=10_000.0)
    service = _make_service(
        plans=plans,
        llm_models=InMemoryLlmModelRepo(),
        llm_usage=InMemoryLlmUsageRepo(),
        credit_policy=InMemoryCreditPolicyRepo(_default_policy()),
    )
    assert await service.would_exceed_credit_limit(TenantId(1)) is False


@pytest.mark.asyncio
async def test_would_exceed_credit_limit_true_when_over() -> None:
    plans = InMemoryTenantPlanRepo()
    await plans.create_plan(TenantId(1), "monthly", _now(), monthly_credits_limit=0.000001)
    llm_models = InMemoryLlmModelRepo()
    llm_usage = InMemoryLlmUsageRepo()
    credit_policy = InMemoryCreditPolicyRepo(_default_policy())
    await _seed_gpt4o_mini(llm_models)
    service = _make_service(
        plans=plans,
        llm_models=llm_models,
        llm_usage=llm_usage,
        credit_policy=credit_policy,
    )
    await service.record_llm_usage(
        tenant_id=TenantId(1), feature_name="log_chat",
        model_name="gpt-4o-mini", input_tokens=10000, output_tokens=5000,
    )
    assert await service.would_exceed_credit_limit(TenantId(1)) is True


@pytest.mark.asyncio
async def test_credit_bar_caps_at_100_percent() -> None:
    plans = InMemoryTenantPlanRepo()
    await plans.create_plan(TenantId(1), "monthly", _now(), monthly_credits_limit=0.000001)
    llm_models = InMemoryLlmModelRepo()
    llm_usage = InMemoryLlmUsageRepo()
    credit_policy = InMemoryCreditPolicyRepo(_default_policy())
    await _seed_gpt4o_mini(llm_models)

    service = _make_service(
        plans=plans,
        llm_models=llm_models,
        llm_usage=llm_usage,
        credit_policy=credit_policy,
    )
    await service.record_llm_usage(
        tenant_id=TenantId(1), feature_name="log_chat",
        model_name="gpt-4o-mini", input_tokens=10000, output_tokens=5000,
    )
    bar = await service.get_credit_bar(TenantId(1))
    assert bar.percentage == 100.0
