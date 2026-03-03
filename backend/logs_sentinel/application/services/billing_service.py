from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from logs_sentinel.domains.billing.entities import PlanType, UsagePeriod
from logs_sentinel.domains.billing.repositories import TenantPlanRepository, UsageCounterRepository
from logs_sentinel.domains.identity.entities import TenantId
from logs_sentinel.infrastructure.settings.config import settings


@dataclass(slots=True)
class UsageSummary:
    """Current usage and limits for a tenant."""

    tenant_id: TenantId
    plan_type: PlanType
    limit: int | None
    used: int
    period_start: datetime


class BillingService:
    """Application service for plans and usage caps."""

    def __init__(
        self,
        plans_repo: TenantPlanRepository,
        usage_repo: UsageCounterRepository,
    ) -> None:
        self._plans = plans_repo
        self._usage = usage_repo

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

    async def check_and_increment(self, tenant_id: TenantId, events: int) -> UsageSummary:
        """Increment usage for tenant and raise if caps exceeded."""

        plan_type, _ = await self._ensure_plan(tenant_id)

        # Unlimited plans skip cap enforcement.
        if plan_type == PlanType.UNLIMITED:
            now = datetime.now(tz=UTC)
            period_start = self._current_month_start(now)
            counter = await self._usage.increment_counter(
                tenant_id=tenant_id,
                period_start=period_start,
                period=UsagePeriod.MONTH,
                delta=events,
            )
            return UsageSummary(
                tenant_id=tenant_id,
                plan_type=plan_type,
                limit=None,
                used=counter.events_ingested,
                period_start=period_start,
            )

        now = datetime.now(tz=UTC)
        period_start = self._current_month_start(now)
        counter = await self._usage.increment_counter(
            tenant_id=tenant_id,
            period_start=period_start,
            period=UsagePeriod.MONTH,
            delta=events,
        )

        if plan_type == PlanType.MONTHLY:
            limit = settings.monthly_events_limit
        elif plan_type == PlanType.YEARLY:
            # For MVP we reuse monthly counter with a higher cap.
            limit = settings.yearly_events_limit
        else:
            limit = settings.monthly_events_limit

        if counter.events_ingested > limit:
            raise ValueError("USAGE_LIMIT_EXCEEDED")

        return UsageSummary(
            tenant_id=tenant_id,
            plan_type=plan_type,
            limit=limit,
            used=counter.events_ingested,
            period_start=period_start,
        )

    async def get_usage_summary(self, tenant_id: TenantId) -> UsageSummary:
        """Return current usage snapshot without incrementing."""

        plan_type, _ = await self._ensure_plan(tenant_id)
        now = datetime.now(tz=UTC)
        period_start = self._current_month_start(now)
        counter = await self._usage.get_counter(
            tenant_id=tenant_id,
            period_start=period_start,
            period=UsagePeriod.MONTH,
        )
        used = counter.events_ingested if counter is not None else 0

        if plan_type == PlanType.UNLIMITED:
            limit: int | None = None
        elif plan_type == PlanType.MONTHLY:
            limit = settings.monthly_events_limit
        else:
            limit = settings.yearly_events_limit

        return UsageSummary(
            tenant_id=tenant_id,
            plan_type=plan_type,
            limit=limit,
            used=used,
            period_start=period_start,
        )

