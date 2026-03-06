"""Application service for projects and ingestion tokens."""

from __future__ import annotations

from secrets import token_urlsafe

from logs_sentinel.domains.identity.entities import TenantId
from logs_sentinel.domains.ingestion.entities import (
    IngestToken,
    IngestTokenId,
    hash_ingest_token,
)
from logs_sentinel.domains.ingestion.repositories import IngestTokenRepository
from logs_sentinel.domains.projects.entities import Project, ProjectId
from logs_sentinel.domains.projects.repositories import ProjectRepository


class ProjectsService:
    """Service for managing projects and ingestion tokens."""

    def __init__(
        self,
        project_repo: ProjectRepository,
        token_repo: IngestTokenRepository,
    ) -> None:
        self._projects = project_repo
        self._tokens = token_repo

    async def list_projects(self, tenant_id: int) -> list[Project]:
        return list(await self._projects.list_projects(TenantId(tenant_id)))

    async def create_project(self, *, tenant_id: int, name: str) -> Project:
        return await self._projects.create_project(TenantId(tenant_id), name)

    async def list_tokens(self, *, tenant_id: int, project_id: int) -> list[IngestToken]:
        return list(
            await self._tokens.list_tokens(
                TenantId(tenant_id),
                ProjectId(project_id),
            )
        )

    async def create_token(
        self,
        *,
        tenant_id: int,
        project_id: int,
        name: str | None,
    ) -> tuple[IngestToken, str]:
        project = await self._projects.get_project(
            TenantId(tenant_id),
            ProjectId(project_id),
        )
        if project is None:
            raise ValueError("PROJECT_NOT_FOUND")

        raw_token = token_urlsafe(32)
        token_hash = hash_ingest_token(raw_token)
        token = await self._tokens.create_token(
            TenantId(tenant_id),
            ProjectId(project_id),
            token_hash=token_hash,
            name=name,
        )
        return token, raw_token

    async def revoke_token(self, *, tenant_id: int, token_id: int) -> None:
        await self._tokens.revoke_token(TenantId(tenant_id), IngestTokenId(token_id))

