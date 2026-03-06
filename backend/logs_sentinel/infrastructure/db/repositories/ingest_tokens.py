"""SQLAlchemy implementation of IngestTokenRepository."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from logs_sentinel.domains.identity.entities import TenantId
from logs_sentinel.domains.ingestion.entities import (
    IngestToken,
    IngestTokenId,
    ProjectId,
)
from logs_sentinel.domains.ingestion.repositories import IngestTokenRepository
from logs_sentinel.infrastructure.db.models import IngestTokenModel


class IngestTokenRepositorySQLAlchemy(IngestTokenRepository):
    """IngestTokenRepository implementation using IngestTokenModel."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_tokens(
        self,
        tenant_id: TenantId,
        project_id: ProjectId,
    ) -> list[IngestToken]:
        stmt = select(IngestTokenModel).where(
            IngestTokenModel.tenant_id == int(tenant_id),
            IngestTokenModel.project_id == int(project_id),
        )
        result = await self._session.execute(stmt)
        rows = result.scalars().all()
        return [
            IngestToken(
                id=IngestTokenId(m.id),
                tenant_id=TenantId(m.tenant_id),
                project_id=ProjectId(m.project_id),
                name=m.name,
                token_hash=m.token_hash,
                last_used_at=m.last_used_at,
                revoked_at=m.revoked_at,
            )
            for m in rows
        ]

    async def create_token(
        self,
        tenant_id: TenantId,
        project_id: ProjectId,
        token_hash: str,
        name: str | None,
    ) -> IngestToken:
        model = IngestTokenModel(
            tenant_id=int(tenant_id),
            project_id=int(project_id),
            name=name,
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
            name=model.name,
            token_hash=model.token_hash,
            last_used_at=model.last_used_at,
            revoked_at=model.revoked_at,
        )

    async def revoke_token(self, tenant_id: TenantId, token_id: IngestTokenId) -> None:
        model = await self._session.get(IngestTokenModel, int(token_id))
        if model is None or model.tenant_id != int(tenant_id):
            return
        model.revoked_at = datetime.now(tz=UTC)
        await self._session.flush()

    async def get_by_token_hash(self, token_hash: str) -> IngestToken | None:
        stmt = select(IngestTokenModel).where(IngestTokenModel.token_hash == token_hash)
        result = await self._session.execute(stmt)
        m = result.scalar_one_or_none()
        if m is None:
            return None
        return IngestToken(
            id=IngestTokenId(m.id),
            tenant_id=TenantId(m.tenant_id),
            project_id=ProjectId(m.project_id),
            name=m.name,
            token_hash=m.token_hash,
            last_used_at=m.last_used_at,
            revoked_at=m.revoked_at,
        )

    async def touch_last_used(self, token_id: IngestTokenId) -> None:
        model = await self._session.get(IngestTokenModel, int(token_id))
        if model is None:
            return
        model.last_used_at = datetime.now(tz=UTC)
        await self._session.flush()

