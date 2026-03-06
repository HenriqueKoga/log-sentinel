from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from logs_sentinel.api.v1.dependencies.auth import TenantContext, get_tenant_context
from logs_sentinel.api.v1.schemas.billing import (
    BillingPlanResponse,
    BillingUsageResponse,
    PlanStatusEnum,
    PlanTypeEnum,
    SettingsUpdateRequest,
)
from logs_sentinel.application.services.billing_service import BillingService
from logs_sentinel.infrastructure.db.base import get_session
from logs_sentinel.infrastructure.db.repositories.billing import (
    TenantPlanRepositorySQLAlchemy,
    UsageCounterRepositorySQLAlchemy,
)

router = APIRouter(prefix="/billing", tags=["billing"])


async def get_billing_service(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> BillingService:
    plans_repo = TenantPlanRepositorySQLAlchemy(session)
    usage_repo = UsageCounterRepositorySQLAlchemy(session)
    return BillingService(plans_repo=plans_repo, usage_repo=usage_repo)


@router.get("/plan", response_model=BillingPlanResponse)
async def get_plan(
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    billing: Annotated[BillingService, Depends(get_billing_service)],
) -> BillingPlanResponse:
    summary = await billing.get_usage_summary(ctx.tenant_id)
    plan = await billing.get_active_plan(ctx.tenant_id)
    return BillingPlanResponse(
        plan_type=PlanTypeEnum(summary.plan_type.value),
        status=PlanStatusEnum.ACTIVE,
        starts_at=summary.period_start,
        ends_at=None,
        limit=summary.limit,
        enable_llm_enrichment=plan.enable_llm_enrichment if plan else False,
    )


@router.get("/usage", response_model=BillingUsageResponse)
async def get_usage(
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    billing: Annotated[BillingService, Depends(get_billing_service)],
) -> BillingUsageResponse:
    summary = await billing.get_usage_summary(ctx.tenant_id)
    return BillingUsageResponse(
        plan_type=PlanTypeEnum(summary.plan_type.value),
        period_start=summary.period_start,
        used=summary.used,
        limit=summary.limit,
        events_ingested=summary.events_ingested,
        llm_enrichments=summary.llm_enrichments,
    )


@router.patch("/settings", response_model=BillingPlanResponse)
async def update_settings(
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    body: SettingsUpdateRequest,
    billing: Annotated[BillingService, Depends(get_billing_service)],
) -> BillingPlanResponse:
    plan = await billing.get_active_plan(ctx.tenant_id)
    if plan is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "NO_ACTIVE_PLAN"},
        )
    await billing.set_tenant_llm_enrichment(ctx.tenant_id, body.enable_llm_enrichment)
    summary = await billing.get_usage_summary(ctx.tenant_id)
    plan_after = await billing.get_active_plan(ctx.tenant_id)
    return BillingPlanResponse(
        plan_type=PlanTypeEnum(summary.plan_type.value),
        status=PlanStatusEnum.ACTIVE,
        starts_at=summary.period_start,
        ends_at=None,
        limit=summary.limit,
        enable_llm_enrichment=plan_after.enable_llm_enrichment if plan_after else False,
    )
