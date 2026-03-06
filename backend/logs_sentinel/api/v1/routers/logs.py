"""Logs API router."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from logs_sentinel.api.v1.dependencies.auth import TenantContext, get_tenant_context
from logs_sentinel.api.v1.dependencies.services import get_logs_service
from logs_sentinel.api.v1.schemas.logs import LogDetailResponse, LogsListResponse
from logs_sentinel.application.services.logs_service import LogsService

router = APIRouter(prefix="/logs", tags=["logs"])


@router.get("", response_model=LogsListResponse)
async def list_logs(
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    service: Annotated[LogsService, Depends(get_logs_service)],
    project_id: Annotated[int | None, Query()] = None,
    level: Annotated[list[str] | None, Query()] = None,
    q: Annotated[str | None, Query()] = None,
    from_: Annotated[datetime | None, Query(alias="from")] = None,
    to: Annotated[datetime | None, Query()] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 50,
    without_issue: Annotated[bool, Query()] = False,
) -> LogsListResponse:
    return await service.list_logs(
        tenant_id=int(ctx.tenant_id),
        project_id=project_id,
        level=level,
        q=q,
        from_dt=from_,
        to_dt=to,
        page=page,
        page_size=page_size,
        without_issue=without_issue,
    )


@router.get("/{log_id}", response_model=LogDetailResponse)
async def get_log_detail(
    log_id: int,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    service: Annotated[LogsService, Depends(get_logs_service)],
) -> LogDetailResponse:
    result = await service.get_log_detail(log_id=log_id, tenant_id=int(ctx.tenant_id))
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "LOG_NOT_FOUND"},
        )
    return result
