from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from logs_sentinel.api.v1.dependencies.auth import TenantContext, get_tenant_context
from logs_sentinel.api.v1.dependencies.services import get_projects_service
from logs_sentinel.api.v1.schemas.projects import (
    IngestTokenCreateRequest,
    IngestTokenResponse,
    ProjectCreateRequest,
    ProjectResponse,
)
from logs_sentinel.application.services.projects_service import ProjectsService

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("", response_model=list[ProjectResponse])
async def list_projects(
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    service: Annotated[ProjectsService, Depends(get_projects_service)],
) -> list[ProjectResponse]:
    projects = await service.list_projects(tenant_id=int(ctx.tenant_id))
    return [
        ProjectResponse(id=int(p.id), name=p.name, created_at=p.created_at)
        for p in projects
    ]


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    payload: ProjectCreateRequest,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    service: Annotated[ProjectsService, Depends(get_projects_service)],
) -> ProjectResponse:
    project = await service.create_project(
        tenant_id=int(ctx.tenant_id),
        name=payload.name,
    )
    return ProjectResponse(id=int(project.id), name=project.name, created_at=project.created_at)


@router.get("/{project_id}/tokens", response_model=list[IngestTokenResponse])
async def list_tokens(
    project_id: int,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    service: Annotated[ProjectsService, Depends(get_projects_service)],
) -> list[IngestTokenResponse]:
    tokens = await service.list_tokens(
        tenant_id=int(ctx.tenant_id),
        project_id=project_id,
    )
    responses: list[IngestTokenResponse] = []
    for t in tokens:
        responses.append(
            IngestTokenResponse(
                id=int(t.id),
                name=t.name,
                token="hidden",
                last_used_at=t.last_used_at,
                revoked_at=t.revoked_at,
            )
        )
    return responses


@router.post("/{project_id}/tokens", response_model=IngestTokenResponse, status_code=201)
async def create_token(
    project_id: int,
    payload: IngestTokenCreateRequest | None,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    service: Annotated[ProjectsService, Depends(get_projects_service)],
) -> IngestTokenResponse:
    try:
        token, raw_token = await service.create_token(
            tenant_id=int(ctx.tenant_id),
            project_id=project_id,
            name=payload.name if payload is not None else None,
        )
    except ValueError as exc:
        if str(exc) == "PROJECT_NOT_FOUND":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "PROJECT_NOT_FOUND"},
            ) from exc
        raise
    return IngestTokenResponse(
        id=int(token.id),
        name=token.name,
        token=raw_token,
        last_used_at=token.last_used_at,
        revoked_at=token.revoked_at,
    )


@router.post("/{project_id}/tokens/{token_id}/revoke", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_token(
    project_id: int,
    token_id: int,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    service: Annotated[ProjectsService, Depends(get_projects_service)],
) -> None:
    _ = project_id
    await service.revoke_token(
        tenant_id=int(ctx.tenant_id),
        token_id=token_id,
    )
