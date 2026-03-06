"""Project repository protocol."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from logs_sentinel.domains.identity.entities import TenantId

from .entities import Project, ProjectId


class ProjectRepository(Protocol):
    """Repository for projects, scoped by tenant."""

    async def list_projects(self, tenant_id: TenantId) -> Sequence[Project]: ...

    async def create_project(self, tenant_id: TenantId, name: str) -> Project: ...

    async def get_project(self, tenant_id: TenantId, project_id: ProjectId) -> Project | None: ...
