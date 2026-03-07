"""Tests for POST /api/v1/ingest router."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from logs_sentinel.application.services.ingestion_service import IngestionService
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
    def __init__(self, tokens: IngestToken | list[IngestToken] | None = None) -> None:
        if tokens is None:
            tokens = []
        elif not isinstance(tokens, list):
            tokens = [tokens]
        self._by_hash: dict[str, IngestToken] = {t.token_hash: t for t in tokens}

    async def list_tokens(
        self, tenant_id: TenantId, project_id: ProjectId
    ) -> Sequence[IngestToken]:
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

    async def get_by_token_hash(self, token_hash: str) -> IngestToken | None:
        return self._by_hash.get(token_hash)

    async def touch_last_used(self, token_id: IngestTokenId) -> None:
        pass


class InMemoryLogEventRepo(LogsRepository):
    def __init__(self) -> None:
        self.created: list[dict[str, Any]] = []

    async def create_many(self, events: list[LogEvent]) -> list[LogEventId]:
        start = len(self.created) + 1
        for i in range(len(events)):
            self.created.append({"id": start + i})
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
        # Not needed for these tests
        return None

    async def get_log_events_by_fingerprint(
        self,
        tenant_id: int,
        project_id: int,
        fingerprint: str,
        limit: int = 20,
        log_id_hint: int | None = None,
    ) -> list[LogEventForTenant]:
        # Not needed for these tests
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
        self.batches.append({"events": list(events)})
        return "batch-123"


@pytest.fixture
def ingest_service() -> IngestionService:
    token = IngestToken(
        id=IngestTokenId(1),
        tenant_id=TenantId(1),
        project_id=ProjectId(1),
        name=None,
        token_hash=hash_ingest_token("dev-token-change-me"),
        last_used_at=None,
        revoked_at=None,
    )
    token_repo = InMemoryTokenRepo(token)
    log_repo = InMemoryLogEventRepo()
    return IngestionService(
        token_repo=token_repo,
        log_repo=log_repo,
        rate_limiter=AllowAllRateLimiter(),
        queue=InMemoryQueue(),
        usage_checker=None,
    )


@pytest.mark.asyncio
async def test_ingest_returns_401_when_token_header_missing() -> None:
    from logs_sentinel.main import create_app

    app = create_app()
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/v1/ingest",
            json={"events": [{"level": "error", "message": "x"}]},
        )
    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "INGEST_MISSING_TOKEN"


@pytest.mark.asyncio
async def test_ingest_returns_400_when_token_invalid() -> None:
    from logs_sentinel.api.v1.dependencies.services import get_ingestion_service
    from logs_sentinel.main import create_app

    empty_repo = InMemoryTokenRepo([])
    service_no_tokens = IngestionService(
        token_repo=empty_repo,
        log_repo=InMemoryLogEventRepo(),
        rate_limiter=AllowAllRateLimiter(),
        queue=InMemoryQueue(),
        usage_checker=None,
    )
    app = create_app()

    async def override_get_ingestion_service() -> IngestionService:
        return service_no_tokens

    app.dependency_overrides[get_ingestion_service] = override_get_ingestion_service
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/v1/ingest",
            headers={"X-Project-Token": "invalid-token"},
            json={"events": [{"level": "error", "message": "x"}]},
        )
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "INGEST_INVALID_TOKEN"
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_ingest_returns_202_and_accepts_events(ingest_service: IngestionService) -> None:
    from logs_sentinel.api.v1.dependencies.services import get_ingestion_service
    from logs_sentinel.main import create_app

    app = create_app()

    async def override_get_ingestion_service() -> IngestionService:
        return ingest_service

    app.dependency_overrides[get_ingestion_service] = override_get_ingestion_service

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/v1/ingest",
            headers={"X-Project-Token": "dev-token-change-me"},
            json={
                "events": [
                    {
                        "level": "error",
                        "message": "Unhandled exception",
                        "exception_type": "ValueError",
                        "stacktrace": "...",
                        "context": {"path": "/api"},
                    }
                ]
            },
        )
    assert response.status_code == 202
    data = response.json()
    assert data["batch_id"] == "batch-123"
    assert data["accepted_count"] == 1
    log_repo = ingest_service._log_repo
    assert len(getattr(log_repo, "created", [])) == 1

    app.dependency_overrides.clear()
