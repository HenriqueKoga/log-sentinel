"""Tests for ProjectsService (list, create, tokens) with in-memory repos."""

from __future__ import annotations

import pytest

from logs_sentinel.application.services.projects_service import ProjectsService
from logs_sentinel.domains.identity.entities import TenantId
from logs_sentinel.domains.ingestion.entities import IngestToken, IngestTokenId, ProjectId
from logs_sentinel.domains.ingestion.repositories import IngestTokenRepository
from logs_sentinel.domains.projects.entities import Project
from logs_sentinel.domains.projects.repositories import ProjectRepository


class InMemoryProjectRepo(ProjectRepository):
    def __init__(self) -> None:
        self._projects: list[Project] = []
        self._next_id = 1

    async def list_projects(self, tenant_id: TenantId) -> list[Project]:
        return [p for p in self._projects if p.tenant_id == tenant_id]

    async def create_project(self, tenant_id: TenantId, name: str) -> Project:
        from datetime import UTC, datetime
        p = Project(
            id=ProjectId(self._next_id),
            tenant_id=tenant_id,
            name=name,
            created_at=datetime.now(UTC),
        )
        self._next_id += 1
        self._projects.append(p)
        return p

    async def get_project(self, tenant_id: TenantId, project_id: ProjectId) -> Project | None:
        for p in self._projects:
            if p.id == project_id and p.tenant_id == tenant_id:
                return p
        return None


class InMemoryIngestTokenRepo(IngestTokenRepository):
    def __init__(self) -> None:
        self._tokens: list[IngestToken] = []
        self._next_id = 1

    async def list_tokens(
        self, tenant_id: TenantId, project_id: ProjectId
    ) -> list[IngestToken]:
        return [
            t
            for t in self._tokens
            if t.tenant_id == tenant_id and t.project_id == project_id
        ]

    async def create_token(
        self,
        tenant_id: TenantId,
        project_id: ProjectId,
        token_hash: str,
        name: str | None,
    ) -> IngestToken:
        t = IngestToken(
            id=IngestTokenId(self._next_id),
            tenant_id=tenant_id,
            project_id=project_id,
            name=name,
            token_hash=token_hash,
            last_used_at=None,
            revoked_at=None,
        )
        self._next_id += 1
        self._tokens.append(t)
        return t

    async def revoke_token(self, tenant_id: TenantId, token_id: IngestTokenId) -> None:
        for i, t in enumerate(self._tokens):
            if t.id == token_id and t.tenant_id == tenant_id:
                from datetime import UTC, datetime
                self._tokens[i] = IngestToken(
                    id=t.id,
                    tenant_id=t.tenant_id,
                    project_id=t.project_id,
                    name=t.name,
                    token_hash=t.token_hash,
                    last_used_at=t.last_used_at,
                    revoked_at=datetime.now(UTC),
                )
                return

    async def get_by_token_hash(self, token_hash: str) -> IngestToken | None:
        for t in self._tokens:
            if t.token_hash == token_hash:
                return t
        return None

    async def touch_last_used(self, token_id: IngestTokenId) -> None:
        pass


@pytest.mark.asyncio
async def test_list_projects_empty() -> None:
    svc = ProjectsService(project_repo=InMemoryProjectRepo(), token_repo=InMemoryIngestTokenRepo())
    out = await svc.list_projects(tenant_id=1)
    assert out == []


@pytest.mark.asyncio
async def test_create_project_and_list() -> None:
    proj_repo = InMemoryProjectRepo()
    svc = ProjectsService(project_repo=proj_repo, token_repo=InMemoryIngestTokenRepo())
    p = await svc.create_project(tenant_id=1, name="Backend")
    assert p.name == "Backend"
    assert int(p.id) >= 1
    listed = await svc.list_projects(tenant_id=1)
    assert len(listed) == 1
    assert listed[0].name == "Backend"


@pytest.mark.asyncio
async def test_create_token_project_not_found() -> None:
    proj_repo = InMemoryProjectRepo()
    svc = ProjectsService(project_repo=proj_repo, token_repo=InMemoryIngestTokenRepo())
    with pytest.raises(ValueError) as exc:
        await svc.create_token(tenant_id=1, project_id=999, name=None)
    assert exc.value.args[0] == "PROJECT_NOT_FOUND"


@pytest.mark.asyncio
async def test_create_token_and_revoke() -> None:
    proj_repo = InMemoryProjectRepo()
    token_repo = InMemoryIngestTokenRepo()
    await proj_repo.create_project(TenantId(1), "API")
    svc = ProjectsService(project_repo=proj_repo, token_repo=token_repo)
    token, raw = await svc.create_token(tenant_id=1, project_id=1, name="CI")
    assert len(raw) > 0
    tokens = await svc.list_tokens(tenant_id=1, project_id=1)
    assert len(tokens) == 1
    await svc.revoke_token(tenant_id=1, token_id=int(token.id))
    tokens_after = await svc.list_tokens(tenant_id=1, project_id=1)
    assert len(tokens_after) == 1
    assert tokens_after[0].revoked_at is not None
