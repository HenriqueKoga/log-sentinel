from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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
from logs_sentinel.infrastructure.db.models import (
    CreditPolicyModel,
    LlmModelCatalogModel,
    LlmUsageModel,
    TenantPlanModel,
    UsageCounterModel,
)


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
        return self._to_entity(row)

    async def create_plan(
        self,
        tenant_id: TenantId,
        plan_type: str,
        starts_at: datetime,
        enable_llm_enrichment: bool = False,
        monthly_credits_limit: float = 1000.0,
    ) -> TenantPlan:
        model = TenantPlanModel(
            tenant_id=int(tenant_id),
            plan_type=plan_type,
            starts_at=starts_at,
            ends_at=None,
            status=PlanStatus.ACTIVE.value,
            enable_llm_enrichment=enable_llm_enrichment,
            monthly_credits_limit=monthly_credits_limit,
        )
        self._session.add(model)
        await self._session.flush()
        return self._to_entity(model)

    async def set_plan_llm_enrichment(self, tenant_id: TenantId, enable: bool) -> None:
        row = await self._active_plan_row(tenant_id)
        if row is not None:
            row.enable_llm_enrichment = enable
            await self._session.flush()

    async def set_monthly_credits_limit(self, tenant_id: TenantId, limit: float) -> None:
        row = await self._active_plan_row(tenant_id)
        if row is not None:
            row.monthly_credits_limit = limit
            await self._session.flush()

    async def _active_plan_row(self, tenant_id: TenantId) -> TenantPlanModel | None:
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
        return result.scalar_one_or_none()

    @staticmethod
    def _to_entity(m: TenantPlanModel) -> TenantPlan:
        return TenantPlan(
            id=TenantPlanId(m.id),
            tenant_id=TenantId(m.tenant_id),
            plan_type=PlanType(m.plan_type),
            starts_at=m.starts_at,
            ends_at=m.ends_at,
            status=PlanStatus(m.status),
            enable_llm_enrichment=m.enable_llm_enrichment,
            monthly_credits_limit=m.monthly_credits_limit,
        )


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
        return self._to_entity(row)

    async def increment_counter(
        self,
        tenant_id: TenantId,
        period_start: datetime,
        period: UsagePeriod,
        events_delta: int,
        llm_delta: int,
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
            )
            self._session.add(model)
        else:
            model = row
            model.events_ingested += events_delta
            model.llm_enrichments += llm_delta
        await self._session.flush()
        return self._to_entity(model)

    @staticmethod
    def _to_entity(m: UsageCounterModel) -> UsageCounter:
        return UsageCounter(
            id=UsageCounterId(m.id),
            tenant_id=TenantId(m.tenant_id),
            period_start=m.period_start,
            period=UsagePeriod(m.period),
            events_ingested=m.events_ingested,
            llm_enrichments=m.llm_enrichments,
        )


class LlmModelRepositorySQLAlchemy(LlmModelRepository):
    """SQLAlchemy implementation of the LLM model catalogue."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, model_id: LlmModelId) -> LlmModel | None:
        stmt = select(LlmModelCatalogModel).where(LlmModelCatalogModel.id == int(model_id))
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        return self._to_entity(row) if row else None

    async def get_by_name(self, provider: str, model_name: str) -> LlmModel | None:
        stmt = select(LlmModelCatalogModel).where(
            LlmModelCatalogModel.provider == provider,
            LlmModelCatalogModel.model_name == model_name,
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        return self._to_entity(row) if row else None

    async def list_models(self, *, active_only: bool = True) -> list[LlmModel]:
        stmt = select(LlmModelCatalogModel).order_by(LlmModelCatalogModel.provider, LlmModelCatalogModel.model_name)
        if active_only:
            stmt = stmt.where(LlmModelCatalogModel.is_active.is_(True))
        result = await self._session.execute(stmt)
        return [self._to_entity(r) for r in result.scalars().all()]

    async def create(self, model: LlmModel) -> LlmModel:
        m = LlmModelCatalogModel(
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
        self._session.add(m)
        await self._session.flush()
        return self._to_entity(m)

    async def update(self, model: LlmModel) -> LlmModel:
        stmt = select(LlmModelCatalogModel).where(LlmModelCatalogModel.id == int(model.id))
        result = await self._session.execute(stmt)
        row = result.scalar_one()
        row.provider = model.provider
        row.model_name = model.model_name
        row.display_name = model.display_name
        row.input_token_price = model.input_token_price
        row.output_token_price = model.output_token_price
        row.currency = model.currency
        row.is_active = model.is_active
        row.supports_usage_tracking = model.supports_usage_tracking
        row.updated_at = model.updated_at
        await self._session.flush()
        return self._to_entity(row)

    @staticmethod
    def _to_entity(m: LlmModelCatalogModel) -> LlmModel:
        return LlmModel(
            id=LlmModelId(m.id),
            provider=m.provider,
            model_name=m.model_name,
            display_name=m.display_name,
            input_token_price=m.input_token_price,
            output_token_price=m.output_token_price,
            currency=m.currency,
            is_active=m.is_active,
            supports_usage_tracking=m.supports_usage_tracking,
            created_at=m.created_at,
            updated_at=m.updated_at,
        )


class LlmUsageRepositorySQLAlchemy(LlmUsageRepository):
    """SQLAlchemy implementation of raw LLM usage records."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def record(self, usage: LlmUsage) -> LlmUsage:
        m = LlmUsageModel(
            tenant_id=int(usage.tenant_id),
            project_id=usage.project_id,
            user_id=usage.user_id,
            llm_model_id=int(usage.llm_model_id),
            feature_name=usage.feature_name,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            total_tokens=usage.total_tokens,
            correlation_id=usage.correlation_id,
            metadata_json=usage.metadata_json,
            created_at=usage.created_at,
        )
        self._session.add(m)
        await self._session.flush()
        return self._to_entity(m)

    async def list_by_tenant(
        self,
        tenant_id: TenantId,
        *,
        period_start: datetime,
        period_end: datetime,
        project_id: int | None = None,
    ) -> list[LlmUsage]:
        stmt = (
            select(LlmUsageModel)
            .where(
                LlmUsageModel.tenant_id == int(tenant_id),
                LlmUsageModel.created_at >= period_start,
                LlmUsageModel.created_at < period_end,
            )
            .order_by(LlmUsageModel.created_at.desc())
        )
        if project_id is not None:
            stmt = stmt.where(LlmUsageModel.project_id == project_id)
        result = await self._session.execute(stmt)
        return [self._to_entity(r) for r in result.scalars().all()]

    @staticmethod
    def _to_entity(m: LlmUsageModel) -> LlmUsage:
        return LlmUsage(
            id=LlmUsageId(m.id),
            tenant_id=TenantId(m.tenant_id),
            project_id=m.project_id,
            user_id=m.user_id,
            llm_model_id=LlmModelId(m.llm_model_id),
            feature_name=m.feature_name,
            input_tokens=m.input_tokens,
            output_tokens=m.output_tokens,
            total_tokens=m.total_tokens,
            correlation_id=m.correlation_id,
            metadata_json=m.metadata_json,
            created_at=m.created_at,
        )


class CreditPolicyRepositorySQLAlchemy(CreditPolicyRepository):
    """SQLAlchemy implementation of credit conversion policies."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_active(self) -> CreditPolicy | None:
        stmt = (
            select(CreditPolicyModel)
            .where(CreditPolicyModel.is_active.is_(True))
            .order_by(CreditPolicyModel.created_at.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        return self._to_entity(row) if row else None

    async def list_policies(self) -> list[CreditPolicy]:
        stmt = select(CreditPolicyModel).order_by(CreditPolicyModel.created_at.desc())
        result = await self._session.execute(stmt)
        return [self._to_entity(r) for r in result.scalars().all()]

    async def create(self, policy: CreditPolicy) -> CreditPolicy:
        m = CreditPolicyModel(
            name=policy.name,
            currency=policy.currency,
            credits_per_currency_unit=policy.credits_per_currency_unit,
            is_active=policy.is_active,
            created_at=policy.created_at,
            updated_at=policy.updated_at,
        )
        self._session.add(m)
        await self._session.flush()
        return self._to_entity(m)

    async def update(self, policy: CreditPolicy) -> CreditPolicy:
        stmt = select(CreditPolicyModel).where(CreditPolicyModel.id == int(policy.id))
        result = await self._session.execute(stmt)
        row = result.scalar_one()
        row.name = policy.name
        row.currency = policy.currency
        row.credits_per_currency_unit = policy.credits_per_currency_unit
        row.is_active = policy.is_active
        row.updated_at = policy.updated_at
        await self._session.flush()
        return self._to_entity(row)

    @staticmethod
    def _to_entity(m: CreditPolicyModel) -> CreditPolicy:
        return CreditPolicy(
            id=CreditPolicyId(m.id),
            name=m.name,
            currency=m.currency,
            credits_per_currency_unit=m.credits_per_currency_unit,
            is_active=m.is_active,
            created_at=m.created_at,
            updated_at=m.updated_at,
        )
