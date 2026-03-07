"""Unit tests for IngestionService."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

import pytest

from logs_sentinel.application.services.ingestion_service import (
    IngestEventInput,
    IngestionService,
)
from logs_sentinel.domains.identity.entities import TenantId
from logs_sentinel.domains.ingestion.entities import (
    IngestToken,
    IngestTokenId,
    LogEvent,
    LogEventId,
    ProjectId,
    hash_ingest_token,
)
from logs_sentinel.domains.ingestion.repositories import IngestTokenRepository
from logs_sentinel.domains.logs.entities import LogDetailRow, LogEventForTenant, LogListRow
from logs_sentinel.domains.logs.repositories import LogsRepository


class InMemoryTokenRepo(IngestTokenRepository):
    def __init__(self, tokens: list[IngestToken] | None = None) -> None:
        self._by_hash: dict[str, IngestToken] = {}
        for t in tokens or []:
            self._by_hash[t.token_hash] = t

    async def get_by_token_hash(self, token_hash: str) -> IngestToken | None:
        return self._by_hash.get(token_hash)

    async def touch_last_used(self, token_id: IngestTokenId) -> None:
        pass

    async def list_tokens(self, tenant_id: TenantId, project_id: ProjectId) -> list[IngestToken]:
        return []

    async def create_token(
        self,
        tenant_id: TenantId,
        project_id: ProjectId,
        token_hash: str,
        name: str | None = None,
    ) -> IngestToken:
        raise NotImplementedError

    async def revoke_token(self, tenant_id: TenantId, token_id: IngestTokenId) -> None:
        pass


class InMemoryLogEventRepo(LogsRepository):
    def __init__(self) -> None:
        self.created: list[dict[str, Any]] = []

    async def create_many(self, events: list[LogEvent]) -> list[LogEventId]:
        start = len(self.created) + 1
        for i, ev in enumerate(events):
            self.created.append(
                {
                    "id": start + i,
                    "tenant_id": int(ev.tenant_id),
                    "project_id": int(ev.project_id),
                    "received_at": ev.received_at,
                    "level": ev.level.value,
                    "message": ev.message,
                    "exception_type": ev.exception_type,
                    "stacktrace": ev.stacktrace,
                    "raw_json": ev.raw_json,
                }
            )
        return [LogEventId(i) for i in range(start, start + len(events))]

    async def list_logs(
        self,
        *,
        tenant_id: int,
        project_id: int | None,
        level: list[str] | None,
        q: str | None,
        from_dt: datetime | None,
        to_dt: datetime | None,
        limit: int,
        offset: int,
    ) -> tuple[list[LogListRow], int]:
        return [], 0

    async def get_log_detail(self, log_id: int, tenant_id: int) -> LogDetailRow | None:
        return None

    async def get_log_event_for_tenant(self, tenant_id: int, log_id: int) -> None:
        return None

    async def get_log_events_by_fingerprint(
        self,
        tenant_id: int,
        project_id: int,
        fingerprint: str,
        limit: int = 20,
        log_id_hint: int | None = None,
    ) -> list[LogEventForTenant]:
        return []


class AllowAllRateLimiter:
    async def check_and_increment(self, key: str, limit: int, window_seconds: int) -> bool:
        return True


class InMemoryQueue:
    def __init__(self) -> None:
        self.batches: list[dict[str, Any]] = []

    async def enqueue_batch(
        self,
        tenant_id: TenantId,
        project_id: ProjectId,
        token_id: int,
        events: Sequence[dict[str, Any]],
    ) -> str:
        self.batches.append(
            {
                "tenant_id": int(tenant_id),
                "project_id": int(project_id),
                "token_id": token_id,
                "events": list(events),
            }
        )
        return "batch-1"


@pytest.fixture
def active_token() -> IngestToken:
    return IngestToken(
        id=IngestTokenId(1),
        tenant_id=TenantId(1),
        project_id=ProjectId(1),
        name="dev-token",
        token_hash=hash_ingest_token("dev-token-change-me"),
        last_used_at=None,
        revoked_at=None,
    )


@pytest.fixture
def token_repo(active_token: IngestToken) -> InMemoryTokenRepo:
    return InMemoryTokenRepo(tokens=[active_token])


@pytest.fixture
def log_repo() -> InMemoryLogEventRepo:
    return InMemoryLogEventRepo()


@pytest.fixture
def ingestion_service(
    token_repo: InMemoryTokenRepo, log_repo: InMemoryLogEventRepo
) -> IngestionService:
    return IngestionService(
        token_repo=token_repo,
        log_repo=log_repo,
        rate_limiter=AllowAllRateLimiter(),
        queue=InMemoryQueue(),
        usage_checker=None,
    )


@pytest.mark.asyncio
async def test_resolve_token_success(ingestion_service: IngestionService) -> None:
    token = await ingestion_service.resolve_token("dev-token-change-me")
    assert token.id == IngestTokenId(1)
    assert token.tenant_id == TenantId(1)
    assert token.project_id == ProjectId(1)


@pytest.mark.asyncio
async def test_resolve_token_raises_when_not_found(ingestion_service: IngestionService) -> None:
    with pytest.raises(ValueError, match="INGEST_INVALID_TOKEN"):
        await ingestion_service.resolve_token("wrong-token")


@pytest.mark.asyncio
async def test_resolve_token_raises_when_revoked(
    token_repo: InMemoryTokenRepo,
    log_repo: InMemoryLogEventRepo,
) -> None:
    revoked = IngestToken(
        id=IngestTokenId(2),
        tenant_id=TenantId(1),
        project_id=ProjectId(1),
        name=None,
        token_hash=hash_ingest_token("revoked-token"),
        last_used_at=None,
        revoked_at=datetime.now(UTC),
    )
    token_repo._by_hash[revoked.token_hash] = revoked
    service = IngestionService(
        token_repo=token_repo,
        log_repo=log_repo,
        rate_limiter=AllowAllRateLimiter(),
        queue=InMemoryQueue(),
        usage_checker=None,
    )
    with pytest.raises(ValueError, match="INGEST_INVALID_TOKEN"):
        await service.resolve_token("revoked-token")


@pytest.mark.asyncio
async def test_ingest_batch_persists_events_and_returns_batch_id(
    ingestion_service: IngestionService,
    log_repo: InMemoryLogEventRepo,
    active_token: IngestToken,
) -> None:
    events = [
        IngestEventInput(
            level="error",
            message="Unhandled exception",
            exception_type="ValueError",
            stacktrace="...",
            raw={"path": "/api"},
        ),
    ]
    result = await ingestion_service.ingest_batch(active_token, events)
    assert result.batch_id == "batch-1"
    assert result.accepted_count == 1
    assert len(log_repo.created) == 1
    assert log_repo.created[0]["level"] == "error"
    assert log_repo.created[0]["message"] == "Unhandled exception"
    assert log_repo.created[0]["raw_json"] == {"path": "/api"}


@pytest.mark.asyncio
async def test_ingest_batch_raises_for_empty_events(
    ingestion_service: IngestionService,
    active_token: IngestToken,
) -> None:
    with pytest.raises(ValueError, match="INGEST_EMPTY_BATCH"):
        await ingestion_service.ingest_batch(active_token, [])


@pytest.mark.asyncio
async def test_ingest_batch_raises_for_invalid_level(
    ingestion_service: IngestionService,
    active_token: IngestToken,
) -> None:
    events = [
        IngestEventInput(
            level="invalid",
            message="msg",
            exception_type=None,
            stacktrace=None,
            raw={},
        ),
    ]
    with pytest.raises(ExceptionGroup) as exc_info:
        await ingestion_service.ingest_batch(active_token, events)
    assert any("INGEST_INVALID_LEVEL" in str(e) for e in exc_info.value.exceptions)


@pytest.mark.asyncio
async def test_ingest_batch_raises_for_empty_message(
    ingestion_service: IngestionService,
    active_token: IngestToken,
) -> None:
    events = [
        IngestEventInput(
            level="info",
            message="",
            exception_type=None,
            stacktrace=None,
            raw={},
        ),
    ]
    with pytest.raises(ExceptionGroup) as exc_info:
        await ingestion_service.ingest_batch(active_token, events)
    assert any("INGEST_EMPTY_MESSAGE" in str(e) for e in exc_info.value.exceptions)
