"""Billing service: plans, operational counters, LLM usage recording and dynamic credit calculation."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from logs_sentinel.domains.billing.entities import (
    CreditPolicy,
    LlmModel,
    LlmUsage,
    LlmUsageId,
    PlanType,
    TenantPlan,
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
from logs_sentinel.infrastructure.settings.config import settings


@dataclass(slots=True)
class UsageSummary:
    """Current operational usage snapshot for a tenant."""

    tenant_id: TenantId
    plan_type: PlanType
    period_start: datetime
    events_ingested: int = 0
    llm_enrichments: int = 0


@dataclass(slots=True)
class ModelBreakdown:
    """Usage breakdown for a single LLM model."""

    model_id: int
    model_name: str
    display_name: str
    input_tokens: int
    output_tokens: int
    total_cost: float
    credits_used: float


@dataclass(slots=True)
class FeatureBreakdown:
    """Usage breakdown for a single LLM feature."""

    feature: str
    input_tokens: int
    output_tokens: int
    total_cost: float
    credits_used: float


@dataclass(slots=True)
class CreditBar:
    """Snapshot of credit consumption vs monthly limit for the current period."""

    credits_used: float
    credits_limit: float
    percentage: float
    period_start: datetime
    period_end: datetime


@dataclass(slots=True)
class LlmUsageSummary:
    """Full LLM usage summary with dynamic credit calculation."""

    period_start: datetime
    period_end: datetime
    totals_input_tokens: int = 0
    totals_output_tokens: int = 0
    totals_cost: float = 0.0
    totals_credits: float = 0.0
    by_model: list[ModelBreakdown] = field(default_factory=list)
    by_feature: list[FeatureBreakdown] = field(default_factory=list)


class BillingService:
    """Application service for plans, operational counters, and LLM usage billing."""

    def __init__(
        self,
        plans_repo: TenantPlanRepository,
        usage_repo: UsageCounterRepository,
        llm_model_repo: LlmModelRepository | None = None,
        llm_usage_repo: LlmUsageRepository | None = None,
        credit_policy_repo: CreditPolicyRepository | None = None,
    ) -> None:
        self._plans = plans_repo
        self._usage = usage_repo
        self._llm_models = llm_model_repo
        self._llm_usage = llm_usage_repo
        self._credit_policy = credit_policy_repo


    async def get_active_plan(self, tenant_id: TenantId) -> TenantPlan | None:
        return await self._plans.get_active_plan(tenant_id)

    async def is_llm_enabled(self, tenant_id: TenantId) -> bool:
        plan = await self._plans.get_active_plan(tenant_id)
        return plan is not None and plan.enable_llm_enrichment

    async def set_tenant_llm_enrichment(self, tenant_id: TenantId, enable: bool) -> None:
        await self._plans.set_plan_llm_enrichment(tenant_id, enable)

    async def _ensure_plan(self, tenant_id: TenantId) -> tuple[PlanType, datetime]:
        plan = await self._plans.get_active_plan(tenant_id)
        if plan is not None:
            return plan.plan_type, plan.starts_at

        now = datetime.now(tz=UTC)
        plan_type = PlanType(settings.default_plan)
        created = await self._plans.create_plan(
            tenant_id=tenant_id,
            plan_type=plan_type.value,
            starts_at=now,
        )
        return created.plan_type, created.starts_at

    @staticmethod
    def _current_month_start(now: datetime) -> datetime:
        return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    async def increment_events(self, tenant_id: TenantId, events: int) -> UsageSummary:
        """Increment event ingestion counter without any credit logic."""
        plan_type, _ = await self._ensure_plan(tenant_id)
        now = datetime.now(tz=UTC)
        period_start = self._current_month_start(now)
        counter = await self._usage.increment_counter(
            tenant_id=tenant_id,
            period_start=period_start,
            period=UsagePeriod.MONTH,
            events_delta=events,
            llm_delta=0,
        )
        return UsageSummary(
            tenant_id=tenant_id,
            plan_type=plan_type,
            period_start=period_start,
            events_ingested=counter.events_ingested,
            llm_enrichments=counter.llm_enrichments,
        )

    async def increment_llm_counter(self, tenant_id: TenantId) -> None:
        """Increment the operational LLM enrichment counter by 1."""
        now = datetime.now(tz=UTC)
        period_start = self._current_month_start(now)
        await self._usage.increment_counter(
            tenant_id=tenant_id,
            period_start=period_start,
            period=UsagePeriod.MONTH,
            events_delta=0,
            llm_delta=1,
        )

    async def get_usage_summary(self, tenant_id: TenantId) -> UsageSummary:
        """Return current operational usage snapshot."""
        plan_type, _ = await self._ensure_plan(tenant_id)
        now = datetime.now(tz=UTC)
        period_start = self._current_month_start(now)
        counter = await self._usage.get_counter(
            tenant_id=tenant_id,
            period_start=period_start,
            period=UsagePeriod.MONTH,
        )
        if counter is None:
            return UsageSummary(
                tenant_id=tenant_id,
                plan_type=plan_type,
                period_start=period_start,
            )
        return UsageSummary(
            tenant_id=tenant_id,
            plan_type=plan_type,
            period_start=period_start,
            events_ingested=counter.events_ingested,
            llm_enrichments=counter.llm_enrichments,
        )


    async def get_credit_bar(self, tenant_id: TenantId) -> CreditBar:
        """Return current-month credit usage vs the plan's monthly limit."""
        plan = await self._plans.get_active_plan(tenant_id)
        credits_limit = plan.monthly_credits_limit if plan else 1000.0

        now = datetime.now(tz=UTC)
        period_start = self._current_month_start(now)
        period_end = now

        summary = await self.get_llm_usage_summary(
            tenant_id, period_start, period_end,
        )
        credits_used = summary.totals_credits
        percentage = (credits_used / credits_limit * 100.0) if credits_limit > 0 else 0.0
        return CreditBar(
            credits_used=credits_used,
            credits_limit=credits_limit,
            percentage=min(percentage, 100.0),
            period_start=period_start,
            period_end=period_end,
        )

    async def would_exceed_credit_limit(self, tenant_id: TenantId) -> bool:
        """Return True if current usage already meets or exceeds the plan's monthly credit limit."""
        bar = await self.get_credit_bar(tenant_id)
        return bar.percentage >= 100.0

    async def record_llm_usage(
        self,
        *,
        tenant_id: TenantId,
        feature_name: str,
        model_name: str,
        input_tokens: int,
        output_tokens: int,
        project_id: int | None = None,
        user_id: int | None = None,
        correlation_id: str | None = None,
        metadata_json: dict[str, object] | None = None,
    ) -> LlmUsage | None:
        """Record raw LLM usage. Returns the record, or None if repos are not configured."""
        if self._llm_models is None or self._llm_usage is None:
            return None

        provider, name = _parse_model_name(model_name)
        llm_model = await self._llm_models.get_by_name(provider, name)
        if llm_model is None:
            llm_model = await self._llm_models.get_by_name("openai", model_name)
        if llm_model is None:
            return None

        await self.increment_llm_counter(tenant_id)

        total_tokens = input_tokens + output_tokens
        now = datetime.now(tz=UTC)
        usage = LlmUsage(
            id=LlmUsageId(0),
            tenant_id=tenant_id,
            project_id=project_id,
            user_id=user_id,
            llm_model_id=llm_model.id,
            feature_name=feature_name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            correlation_id=correlation_id,
            metadata_json=metadata_json,
            created_at=now,
        )
        return await self._llm_usage.record(usage)

    async def get_llm_usage_summary(
        self,
        tenant_id: TenantId,
        period_start: datetime,
        period_end: datetime,
        project_id: int | None = None,
    ) -> LlmUsageSummary:
        """Calculate LLM usage with credits dynamically — nothing persisted."""
        if self._llm_usage is None or self._llm_models is None:
            return LlmUsageSummary(period_start=period_start, period_end=period_end)

        records = await self._llm_usage.list_by_tenant(
            tenant_id,
            period_start=period_start,
            period_end=period_end,
            project_id=project_id,
        )

        policy = await self._get_credit_policy()
        ratio = policy.credits_per_currency_unit if policy else 100.0
        models_cache: dict[int, LlmModel] = {}

        model_agg: dict[int, _ModelAcc] = {}
        feature_agg: dict[str, _FeatureAcc] = {}
        total_input = 0
        total_output = 0
        total_cost = 0.0

        for rec in records:
            mid = int(rec.llm_model_id)
            if mid not in models_cache:
                m = await self._llm_models.get_by_id(rec.llm_model_id)
                if m is None:
                    continue
                models_cache[mid] = m
            llm_model = models_cache[mid]

            inp_cost = rec.input_tokens * llm_model.input_token_price
            out_cost = rec.output_tokens * llm_model.output_token_price
            cost = inp_cost + out_cost

            total_input += rec.input_tokens
            total_output += rec.output_tokens
            total_cost += cost

            if mid not in model_agg:
                model_agg[mid] = _ModelAcc(llm_model.model_name, llm_model.display_name)
            ma = model_agg[mid]
            ma.input_tokens += rec.input_tokens
            ma.output_tokens += rec.output_tokens
            ma.total_cost += cost

            feat = rec.feature_name
            if feat not in feature_agg:
                feature_agg[feat] = _FeatureAcc()
            fa = feature_agg[feat]
            fa.input_tokens += rec.input_tokens
            fa.output_tokens += rec.output_tokens
            fa.total_cost += cost

        by_model = [
            ModelBreakdown(
                model_id=mid,
                model_name=v.model_name,
                display_name=v.display_name,
                input_tokens=v.input_tokens,
                output_tokens=v.output_tokens,
                total_cost=v.total_cost,
                credits_used=v.total_cost * ratio,
            )
            for mid, v in model_agg.items()
        ]
        by_feature = [
            FeatureBreakdown(
                feature=feat,
                input_tokens=v.input_tokens,
                output_tokens=v.output_tokens,
                total_cost=v.total_cost,
                credits_used=v.total_cost * ratio,
            )
            for feat, v in feature_agg.items()
        ]

        return LlmUsageSummary(
            period_start=period_start,
            period_end=period_end,
            totals_input_tokens=total_input,
            totals_output_tokens=total_output,
            totals_cost=total_cost,
            totals_credits=total_cost * ratio,
            by_model=by_model,
            by_feature=by_feature,
        )

    async def _get_credit_policy(self) -> CreditPolicy | None:
        if self._credit_policy is None:
            return None
        return await self._credit_policy.get_active()


@dataclass
class _ModelAcc:
    model_name: str
    display_name: str
    input_tokens: int = 0
    output_tokens: int = 0
    total_cost: float = 0.0


@dataclass
class _FeatureAcc:
    input_tokens: int = 0
    output_tokens: int = 0
    total_cost: float = 0.0


def _parse_model_name(model_name: str) -> tuple[str, str]:
    """Split 'provider/model' into (provider, model). Default provider is 'openai'."""
    if "/" in model_name:
        parts = model_name.split("/", 1)
        return parts[0], parts[1]
    return "openai", model_name
