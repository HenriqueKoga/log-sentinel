from __future__ import annotations

from datetime import UTC, datetime

from logs_sentinel.domains.identity.entities import TenantId
from logs_sentinel.domains.ingestion.entities import (
    IngestToken,
    IngestTokenId,
    ProjectId,
    hash_ingest_token,
)


def test_hash_ingest_token_is_deterministic_and_hides_value() -> None:
    raw = "super-secret-token"
    h1 = hash_ingest_token(raw)
    h2 = hash_ingest_token(raw)
    assert h1 == h2
    assert raw not in h1


def test_ingest_token_is_active_when_not_revoked() -> None:
    token = IngestToken(
        id=IngestTokenId(1),
        tenant_id=TenantId(1),
        project_id=ProjectId(1),
        name=None,
        token_hash="hash",
        last_used_at=None,
        revoked_at=None,
    )
    assert token.is_active


def test_ingest_token_is_inactive_when_revoked() -> None:
    now = datetime.now(tz=UTC)
    token = IngestToken(
        id=IngestTokenId(1),
        tenant_id=TenantId(1),
        project_id=ProjectId(1),
        name=None,
        token_hash="hash",
        last_used_at=None,
        revoked_at=now,
    )
    assert not token.is_active
