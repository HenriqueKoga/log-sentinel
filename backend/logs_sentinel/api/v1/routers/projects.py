from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from secrets import token_urlsafe
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from logs_sentinel.api.v1.dependencies.auth import TenantContext, get_tenant_context
from logs_sentinel.api.v1.schemas.projects import (
    IngestTokenResponse,
    ProjectCreateRequest,
    ProjectResponse,
)
from logs_sentinel.domains.identity.entities import TenantId
from logs_sentinel.domains.ingestion.entities import IngestToken, IngestTokenId, Project, ProjectId
from logs_sentinel.domains.ingestion.repositories import IngestTokenRepository, ProjectRepository
from logs_sentinel.infrastructure.db.base import get_session
from logs_sentinel.infrastructure.db.models import IngestTokenModel, ProjectModel

router = APIRouter(prefix="/projects", tags=["projects"])


class ProjectRepositorySQLAlchemy(ProjectRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_projects(self, tenant_id: TenantId) -> Sequence[Project]:
        result = await self._session.execute(
            ProjectModel.__table__.select().where(ProjectModel.tenant_id == int(tenant_id))
        )
        rows = result.fetchall()
        projects: list[Project] = []
        for row in rows:
            model: ProjectModel = ProjectModel(**row._mapping)
            projects.append(
                Project(
                    id=ProjectId(model.id),
                    tenant_id=TenantId(model.tenant_id),
                    name=model.name,
                    created_at=model.created_at,
                )
            )
        return projects

    async def create_project(self, tenant_id: TenantId, name: str) -> Project:
        now = datetime.now(tz=UTC)
        model = ProjectModel(tenant_id=int(tenant_id), name=name, created_at=now)
        self._session.add(model)
        await self._session.flush()
        return Project(
            id=ProjectId(model.id),
            tenant_id=TenantId(model.tenant_id),
            name=model.name,
            created_at=model.created_at,
        )

    async def get_project(self, tenant_id: TenantId, project_id: ProjectId) -> Project | None:
        model = await self._session.get(
            ProjectModel,
            int(project_id),
            with_for_update=False,
        )
        if model is None or model.tenant_id != int(tenant_id):
            return None
        return Project(
            id=ProjectId(model.id),
            tenant_id=TenantId(model.tenant_id),
            name=model.name,
            created_at=model.created_at,
        )


class IngestTokenRepositorySQLAlchemy(IngestTokenRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_tokens(self, tenant_id: TenantId, project_id: ProjectId) -> Sequence[IngestToken]:
        result = await self._session.execute(
            IngestTokenModel.__table__.select().where(
                IngestTokenModel.tenant_id == int(tenant_id),
                IngestTokenModel.project_id == int(project_id),
            )
        )
        tokens: list[IngestToken] = []
        for row in result.fetchall():
            model: IngestTokenModel = IngestTokenModel(**row._mapping)
            tokens.append(
                IngestToken(
                    id=IngestTokenId(model.id),
                    tenant_id=TenantId(model.tenant_id),
                    project_id=ProjectId(model.project_id),
                    token_hash=model.token_hash,
                    last_used_at=model.last_used_at,
                    revoked_at=model.revoked_at,
                )
            )
        return tokens

    async def create_token(self, tenant_id: TenantId, project_id: ProjectId, token_hash: str) -> IngestToken:
        model = IngestTokenModel(
            tenant_id=int(tenant_id),
            project_id=int(project_id),
            token_hash=token_hash,
            last_used_at=None,
            revoked_at=None,
        )
        self._session.add(model)
        await self._session.flush()
        return IngestToken(
            id=IngestTokenId(model.id),
            tenant_id=TenantId(model.tenant_id),
            project_id=ProjectId(model.project_id),
            token_hash=model.token_hash,
            last_used_at=model.last_used_at,
            revoked_at=model.revoked_at,
        )

    async def revoke_token(self, tenant_id: TenantId, token_id: int) -> None:
        model = await self._session.get(IngestTokenModel, token_id)
        if model is None or model.tenant_id != int(tenant_id):
            return
        model.revoked_at = datetime.now(tz=UTC)
        await self._session.flush()

    async def get_by_token_hash(self, token_hash: str) -> IngestToken | None:
        result = await self._session.execute(
            IngestTokenModel.__table__.select().where(IngestTokenModel.token_hash == token_hash)
        )
        row = result.first()
        if row is None:
            return None
        model: IngestTokenModel = IngestTokenModel(**row._mapping)
        return IngestToken(
            id=IngestTokenId(model.id),
            tenant_id=TenantId(model.tenant_id),
            project_id=ProjectId(model.project_id),
            token_hash=model.token_hash,
            last_used_at=model.last_used_at,
            revoked_at=model.revoked_at,
        )

    async def touch_last_used(self, token_id: int) -> None:
        model = await self._session.get(IngestTokenModel, token_id)
        if model is None:
            return
        model.last_used_at = datetime.now(tz=UTC)
        await self._session.flush()


async def get_project_repo(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ProjectRepository:
    return ProjectRepositorySQLAlchemy(session)


async def get_token_repo(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> IngestTokenRepository:
    return IngestTokenRepositorySQLAlchemy(session)


@router.get("", response_model=list[ProjectResponse])
async def list_projects(
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    repo: Annotated[ProjectRepository, Depends(get_project_repo)],
) -> list[ProjectResponse]:
    projects = await repo.list_projects(ctx.tenant_id)
    return [
        ProjectResponse(id=int(p.id), name=p.name, created_at=p.created_at) for p in projects
    ]


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    payload: ProjectCreateRequest,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    repo: Annotated[ProjectRepository, Depends(get_project_repo)],
) -> ProjectResponse:
    project = await repo.create_project(ctx.tenant_id, name=payload.name)
    return ProjectResponse(id=int(project.id), name=project.name, created_at=project.created_at)


@router.get("/{project_id}/tokens", response_model=list[IngestTokenResponse])
async def list_tokens(
    project_id: int,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    repo: Annotated[IngestTokenRepository, Depends(get_token_repo)],
) -> list[IngestTokenResponse]:
    tokens = await repo.list_tokens(ctx.tenant_id, ProjectId(project_id))
    return [
        IngestTokenResponse(
            id=int(t.id),
            token=t.token_hash,
            last_used_at=t.last_used_at,
            revoked_at=t.revoked_at,
        )
        for t in tokens
    ]


@router.post("/{project_id}/tokens", response_model=IngestTokenResponse, status_code=201)
async def create_token(
    project_id: int,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    repo: Annotated[IngestTokenRepository, Depends(get_token_repo)],
    project_repo: Annotated[ProjectRepository, Depends(get_project_repo)],
) -> IngestTokenResponse:
    project = await project_repo.get_project(ctx.tenant_id, ProjectId(project_id))
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "PROJECT_NOT_FOUND"},
        )
    raw_token = token_urlsafe(32)
    token = await repo.create_token(ctx.tenant_id, ProjectId(project_id), token_hash=raw_token)
    return IngestTokenResponse(
        id=int(token.id),
        token=raw_token,
        last_used_at=token.last_used_at,
        revoked_at=token.revoked_at,
    )

