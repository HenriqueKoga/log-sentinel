from __future__ import annotations

from typing import Protocol, Sequence

from .entities import IngestToken, IngestTokenId, LogEvent, LogEventId, Project, ProjectId
from logs_sentinel.domains.identity.entities import TenantId


class ProjectRepository(Protocol):
    """Repository for projects, scoped by tenant."""

    async def list_projects(self, tenant_id: TenantId) -> Sequence[Project]:
        ...

    async def create_project(self, tenant_id: TenantId, name: str) -> Project:
        ...

    async def get_project(self, tenant_id: TenantId, project_id: ProjectId) -> Project | None:
        ...


class IngestTokenRepository(Protocol):
    """Repository for ingestion tokens."""

    async def list_tokens(self, tenant_id: TenantId, project_id: ProjectId) -> Sequence[IngestToken]:
        ...

    async def create_token(self, tenant_id: TenantId, project_id: ProjectId, token_hash: str) -> IngestToken:
        ...

    async def revoke_token(self, tenant_id: TenantId, token_id: IngestTokenId) -> None:
        ...

    async def get_by_token_hash(self, token_hash: str) -> IngestToken | None:
        ...

    async def touch_last_used(self, token_id: IngestTokenId) -> None:
        ...


class LogEventRepository(Protocol):
    """Repository for raw log events (append-only)."""

    async def create_many(self, events: list[LogEvent]) -> list[LogEventId]:
        ...

