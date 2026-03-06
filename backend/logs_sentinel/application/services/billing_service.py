from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from logs_sentinel.domains.billing.entities import PlanType, TenantPlan, UsagePeriod
from logs_sentinel.domains.billing.repositories import TenantPlanRepository, UsageCounterRepository
from logs_sentinel.domains.identity.entities import TenantId
from logs_sentinel.infrastructure.settings.config import settings


@dataclass(slots=True)
class UsageSummary:
    """Current usage and limits for a tenant (used/limit in credits)."""

    tenant_id: TenantId
    plan_type: PlanType
    limit: int | None
    used: int
    period_start: datetime
    events_ingested: int = 0
    llm_enrichments: int = 0


class BillingService:
    """Application service for plans and usage caps."""

    def __init__(
        self,
        plans_repo: TenantPlanRepository,
        usage_repo: UsageCounterRepository,
    ) -> None:
        self._plans = plans_repo
        self._usage = usage_repo

    async def get_active_plan(self, tenant_id: TenantId) -> TenantPlan | None:
        """Return the active tenant plan or None."""
        return await self._plans.get_active_plan(tenant_id)

    async def is_llm_enabled(self, tenant_id: TenantId) -> bool:
        """Return True if the tenant has an active plan with LLM enrichment and API key is set."""
        plan = await self._plans.get_active_plan(tenant_id)
        return (
            plan is not None
            and plan.enable_llm_enrichment
        )

    async def would_exceed_llm_limit(
        self, tenant_id: TenantId, credits_per_use: int | None = None
    ) -> bool:
        """Return True if one more LLM use (by default credits_per_llm_enrichment) would exceed the plan limit."""
        summary = await self.get_usage_summary(tenant_id)
        if summary.limit is None:
            return False
        cost = credits_per_use if credits_per_use is not None else settings.credits_per_llm_enrichment
        return summary.used + cost > summary.limit

    async def set_tenant_llm_enrichment(self, tenant_id: TenantId, enable: bool) -> None:
        """Enable or disable LLM enrichment for the tenant's active plan."""
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

    def _credits_limit(self, plan_type: PlanType) -> int | None:
        if plan_type == PlanType.UNLIMITED:
            return None
        if plan_type == PlanType.MONTHLY:
            return settings.monthly_credits_limit
        return settings.yearly_credits_limit

    async def check_and_increment(
        self,
        tenant_id: TenantId,
        events: int,
        llm_enrichments: int = 0,
    ) -> UsageSummary:
        """Increment usage (events + optional LLM) and credits; raise if caps exceeded."""

        plan_type, _ = await self._ensure_plan(tenant_id)
        credits_delta = (
            events * settings.credits_per_event
            + llm_enrichments * settings.credits_per_llm_enrichment
        )

        now = datetime.now(tz=UTC)
        period_start = self._current_month_start(now)
        counter = await self._usage.increment_counter(
            tenant_id=tenant_id,
            period_start=period_start,
            period=UsagePeriod.MONTH,
            events_delta=events,
            llm_delta=llm_enrichments,
            credits_delta=credits_delta,
        )

        limit = self._credits_limit(plan_type)
        if limit is not None and counter.credits_used > limit:
            raise ValueError("USAGE_LIMIT_EXCEEDED")

        return UsageSummary(
            tenant_id=tenant_id,
            plan_type=plan_type,
            limit=limit,
            used=counter.credits_used,
            period_start=period_start,
            events_ingested=counter.events_ingested,
            llm_enrichments=counter.llm_enrichments,
        )

    async def record_llm_usage(self, tenant_id: TenantId) -> UsageSummary:
        """Record one LLM enrichment and debit credits; raise if caps exceeded."""

        plan_type, _ = await self._ensure_plan(tenant_id)
        credits_delta = settings.credits_per_llm_enrichment

        now = datetime.now(tz=UTC)
        period_start = self._current_month_start(now)
        counter = await self._usage.increment_counter(
            tenant_id=tenant_id,
            period_start=period_start,
            period=UsagePeriod.MONTH,
            events_delta=0,
            llm_delta=1,
            credits_delta=credits_delta,
        )

        limit = self._credits_limit(plan_type)
        if limit is not None and counter.credits_used > limit:
            raise ValueError("USAGE_LIMIT_EXCEEDED")

        return UsageSummary(
            tenant_id=tenant_id,
            plan_type=plan_type,
            limit=limit,
            used=counter.credits_used,
            period_start=period_start,
            events_ingested=counter.events_ingested,
            llm_enrichments=counter.llm_enrichments,
        )

    async def get_usage_summary(self, tenant_id: TenantId) -> UsageSummary:
        """Return current usage snapshot without incrementing (used/limit in credits)."""

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
                limit=self._credits_limit(plan_type),
                used=0,
                period_start=period_start,
                events_ingested=0,
                llm_enrichments=0,
            )
        return UsageSummary(
            tenant_id=tenant_id,
            plan_type=plan_type,
            limit=self._credits_limit(plan_type),
            used=counter.credits_used,
            period_start=period_start,
            events_ingested=counter.events_ingested,
            llm_enrichments=counter.llm_enrichments,
        )
