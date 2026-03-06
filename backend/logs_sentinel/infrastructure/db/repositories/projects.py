"""SQLAlchemy implementation of ProjectRepository."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from logs_sentinel.domains.identity.entities import TenantId
from logs_sentinel.domains.projects.entities import Project, ProjectId
from logs_sentinel.domains.projects.repositories import ProjectRepository
from logs_sentinel.infrastructure.db.models import ProjectModel


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
