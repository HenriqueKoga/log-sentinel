from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from logs_sentinel.domains.identity.entities import TenantId

from .entities import IngestToken, IngestTokenId, ProjectId


class IngestTokenRepository(Protocol):
    """Repository for ingestion tokens."""

    async def list_tokens(
        self, tenant_id: TenantId, project_id: ProjectId
    ) -> Sequence[IngestToken]: ...

    async def create_token(
        self,
        tenant_id: TenantId,
        project_id: ProjectId,
        token_hash: str,
        name: str | None,
    ) -> IngestToken: ...

    async def revoke_token(self, tenant_id: TenantId, token_id: IngestTokenId) -> None: ...

    async def get_by_token_hash(self, token_hash: str) -> IngestToken | None: ...

    async def touch_last_used(self, token_id: IngestTokenId) -> None: ...
