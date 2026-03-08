from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from logs_sentinel.api.v1.dependencies.auth import TenantContext, get_tenant_context
from logs_sentinel.api.v1.dependencies.services import get_billing_service
from logs_sentinel.api.v1.schemas.billing import (
    BillingPlanResponse,
    BillingUsageResponse,
    CreditBarResponse,
    CreditPolicyOut,
    FeatureBreakdownOut,
    LlmModelIn,
    LlmModelOut,
    LlmModelsListResponse,
    LlmModelUpdateIn,
    LlmUsageSummaryResponse,
    LlmUsageTotals,
    ModelBreakdownOut,
    PlanStatusEnum,
    PlanTypeEnum,
    SettingsUpdateRequest,
)
from logs_sentinel.application.services.billing_service import BillingService
from logs_sentinel.domains.billing.entities import (
    LlmModel,
    LlmModelId,
)
from logs_sentinel.infrastructure.db.base import get_session
from logs_sentinel.infrastructure.db.repositories.billing import (
    CreditPolicyRepositorySQLAlchemy,
    LlmModelRepositorySQLAlchemy,
)

router = APIRouter(prefix="/billing", tags=["billing"])


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
        enable_llm_enrichment=plan.enable_llm_enrichment if plan else False,
        monthly_credits_limit=plan.monthly_credits_limit if plan else 1000.0,
    )


@router.get("/credit-bar", response_model=CreditBarResponse)
async def get_credit_bar(
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    billing: Annotated[BillingService, Depends(get_billing_service)],
) -> CreditBarResponse:
    bar = await billing.get_credit_bar(ctx.tenant_id)
    return CreditBarResponse(
        credits_used=bar.credits_used,
        credits_limit=bar.credits_limit,
        percentage=bar.percentage,
        period_start=bar.period_start,
        period_end=bar.period_end,
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
        enable_llm_enrichment=plan_after.enable_llm_enrichment if plan_after else False,
        monthly_credits_limit=plan_after.monthly_credits_limit if plan_after else 1000.0,
    )


@router.get("/llm-usage", response_model=LlmUsageSummaryResponse)
async def get_llm_usage(
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    billing: Annotated[BillingService, Depends(get_billing_service)],
    from_: Annotated[datetime | None, Query(alias="from")] = None,
    to: Annotated[datetime | None, Query()] = None,
    project_id: Annotated[int | None, Query()] = None,
) -> LlmUsageSummaryResponse:
    now = datetime.now(tz=UTC)
    period_start = from_ or now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    period_end = to or (now + timedelta(seconds=1))
    summary = await billing.get_llm_usage_summary(
        ctx.tenant_id, period_start, period_end, project_id=project_id,
    )
    return LlmUsageSummaryResponse(
        period_start=summary.period_start,
        period_end=summary.period_end,
        totals=LlmUsageTotals(
            input_tokens=summary.totals_input_tokens,
            output_tokens=summary.totals_output_tokens,
            total_cost=summary.totals_cost,
            credits_used=summary.totals_credits,
        ),
        by_model=[
            ModelBreakdownOut(
                model_id=m.model_id,
                model_name=m.model_name,
                display_name=m.display_name,
                input_tokens=m.input_tokens,
                output_tokens=m.output_tokens,
                total_cost=m.total_cost,
                credits_used=m.credits_used,
            )
            for m in summary.by_model
        ],
        by_feature=[
            FeatureBreakdownOut(
                feature=f.feature,
                input_tokens=f.input_tokens,
                output_tokens=f.output_tokens,
                total_cost=f.total_cost,
                credits_used=f.credits_used,
            )
            for f in summary.by_feature
        ],
    )


# ---------------------------------------------------------------------------
# LLM model CRUD
# ---------------------------------------------------------------------------

@router.get("/llm-models", response_model=LlmModelsListResponse)
async def list_llm_models(
    _ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
    active_only: Annotated[bool, Query()] = True,
) -> LlmModelsListResponse:
    repo = LlmModelRepositorySQLAlchemy(session)
    models = await repo.list_models(active_only=active_only)
    return LlmModelsListResponse(items=[_llm_model_out(m) for m in models])


@router.post("/llm-models", response_model=LlmModelOut, status_code=status.HTTP_201_CREATED)
async def create_llm_model(
    _ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    body: Annotated[LlmModelIn, Body()],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> LlmModelOut:
    repo = LlmModelRepositorySQLAlchemy(session)
    existing = await repo.get_by_name(body.provider, body.model_name)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "MODEL_ALREADY_EXISTS"},
        )
    now = datetime.now(tz=UTC)
    model = LlmModel(
        id=LlmModelId(0),
        provider=body.provider,
        model_name=body.model_name,
        display_name=body.display_name,
        input_token_price=body.input_token_price,
        output_token_price=body.output_token_price,
        currency=body.currency,
        is_active=body.is_active,
        supports_usage_tracking=body.supports_usage_tracking,
        created_at=now,
        updated_at=now,
    )
    created = await repo.create(model)
    return _llm_model_out(created)


@router.patch("/llm-models/{model_id}", response_model=LlmModelOut)
async def update_llm_model(
    model_id: int,
    _ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    body: Annotated[LlmModelUpdateIn, Body()],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> LlmModelOut:
    repo = LlmModelRepositorySQLAlchemy(session)
    existing = await repo.get_by_id(LlmModelId(model_id))
    if existing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "MODEL_NOT_FOUND"},
        )
    if body.display_name is not None:
        existing.display_name = body.display_name
    if body.input_token_price is not None:
        existing.input_token_price = body.input_token_price
    if body.output_token_price is not None:
        existing.output_token_price = body.output_token_price
    if body.currency is not None:
        existing.currency = body.currency
    if body.is_active is not None:
        existing.is_active = body.is_active
    if body.supports_usage_tracking is not None:
        existing.supports_usage_tracking = body.supports_usage_tracking
    existing.updated_at = datetime.now(tz=UTC)
    updated = await repo.update(existing)
    return _llm_model_out(updated)


# ---------------------------------------------------------------------------
# Credit policy (read-only for now, admin-managed)
# ---------------------------------------------------------------------------

@router.get("/credit-policy", response_model=CreditPolicyOut | None)
async def get_credit_policy(
    _ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CreditPolicyOut | None:
    repo = CreditPolicyRepositorySQLAlchemy(session)
    policy = await repo.get_active()
    if policy is None:
        return None
    return CreditPolicyOut(
        id=int(policy.id),
        name=policy.name,
        currency=policy.currency,
        credits_per_currency_unit=policy.credits_per_currency_unit,
        is_active=policy.is_active,
        created_at=policy.created_at,
        updated_at=policy.updated_at,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _llm_model_out(m: LlmModel) -> LlmModelOut:
    return LlmModelOut(
        id=int(m.id),
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
