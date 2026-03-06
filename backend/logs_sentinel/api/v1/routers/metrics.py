"""Metrics API router."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from logs_sentinel.api.v1.dependencies.auth import TenantContext, get_tenant_context
from logs_sentinel.api.v1.dependencies.services import get_metrics_service
from logs_sentinel.api.v1.schemas.metrics import DashboardMetricsResponse
from logs_sentinel.application.services.metrics_service import MetricsService

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("/dashboard", response_model=DashboardMetricsResponse)
async def get_dashboard_metrics(
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    service: Annotated[MetricsService, Depends(get_metrics_service)],
    minutes: Annotated[int, Query(ge=1, le=1440)] = 30,
) -> DashboardMetricsResponse:
    return await service.get_dashboard_metrics(
        tenant_id=int(ctx.tenant_id),
        minutes=minutes,
    )
