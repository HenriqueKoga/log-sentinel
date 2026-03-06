from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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
from logs_sentinel.infrastructure.db.models import TenantPlanModel, UsageCounterModel


class TenantPlanRepositorySQLAlchemy(TenantPlanRepository):
    """SQLAlchemy implementation of tenant plan repository."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_active_plan(self, tenant_id: TenantId) -> TenantPlan | None:
        stmt = (
            select(TenantPlanModel)
            .where(
                TenantPlanModel.tenant_id == int(tenant_id),
                TenantPlanModel.status == PlanStatus.ACTIVE.value,
            )
            .order_by(TenantPlanModel.starts_at.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return None
        model: TenantPlanModel = row
        return TenantPlan(
            id=TenantPlanId(model.id),
            tenant_id=TenantId(model.tenant_id),
            plan_type=PlanType(model.plan_type),
            starts_at=model.starts_at,
            ends_at=model.ends_at,
            status=PlanStatus(model.status),
            enable_llm_enrichment=model.enable_llm_enrichment,
        )

    async def create_plan(
        self,
        tenant_id: TenantId,
        plan_type: str,
        starts_at: datetime,
        enable_llm_enrichment: bool = False,
    ) -> TenantPlan:
        model = TenantPlanModel(
            tenant_id=int(tenant_id),
            plan_type=plan_type,
            starts_at=starts_at,
            ends_at=None,
            status=PlanStatus.ACTIVE.value,
            enable_llm_enrichment=enable_llm_enrichment,
        )
        self._session.add(model)
        await self._session.flush()
        return TenantPlan(
            id=TenantPlanId(model.id),
            tenant_id=TenantId(model.tenant_id),
            plan_type=PlanType(model.plan_type),
            starts_at=model.starts_at,
            ends_at=model.ends_at,
            status=PlanStatus(model.status),
            enable_llm_enrichment=enable_llm_enrichment,
        )

    async def set_plan_llm_enrichment(self, tenant_id: TenantId, enable: bool) -> None:
        stmt = (
            select(TenantPlanModel)
            .where(
                TenantPlanModel.tenant_id == int(tenant_id),
                TenantPlanModel.status == PlanStatus.ACTIVE.value,
            )
            .order_by(TenantPlanModel.starts_at.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is not None:
            row.enable_llm_enrichment = enable
            await self._session.flush()


class UsageCounterRepositorySQLAlchemy(UsageCounterRepository):
    """SQLAlchemy implementation of usage counter repository."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_counter(
        self,
        tenant_id: TenantId,
        period_start: datetime,
        period: UsagePeriod,
    ) -> UsageCounter | None:
        stmt = select(UsageCounterModel).where(
            UsageCounterModel.tenant_id == int(tenant_id),
            UsageCounterModel.period_start == period_start,
            UsageCounterModel.period == period.value,
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return None
        model: UsageCounterModel = row
        return UsageCounter(
            id=UsageCounterId(model.id),
            tenant_id=TenantId(model.tenant_id),
            period_start=model.period_start,
            period=UsagePeriod(model.period),
            events_ingested=model.events_ingested,
            llm_enrichments=model.llm_enrichments,
            credits_used=model.credits_used,
        )

    async def increment_counter(
        self,
        tenant_id: TenantId,
        period_start: datetime,
        period: UsagePeriod,
        events_delta: int,
        llm_delta: int,
        credits_delta: int,
    ) -> UsageCounter:
        stmt = (
            select(UsageCounterModel)
            .where(
                UsageCounterModel.tenant_id == int(tenant_id),
                UsageCounterModel.period_start == period_start,
                UsageCounterModel.period == period.value,
            )
            .limit(1)
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            model = UsageCounterModel(
                tenant_id=int(tenant_id),
                period_start=period_start,
                period=period.value,
                events_ingested=events_delta,
                llm_enrichments=llm_delta,
                credits_used=credits_delta,
            )
            self._session.add(model)
        else:
            model = row
            model.events_ingested += events_delta
            model.llm_enrichments += llm_delta
            model.credits_used += credits_delta
        await self._session.flush()
        return UsageCounter(
            id=UsageCounterId(model.id),
            tenant_id=TenantId(model.tenant_id),
            period_start=model.period_start,
            period=UsagePeriod(model.period),
            events_ingested=model.events_ingested,
            llm_enrichments=model.llm_enrichments,
            credits_used=model.credits_used,
        )
