"""Tests for GET /api/v1/logs router."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import UTC, datetime

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.pool import StaticPool

from logs_sentinel.api.v1.dependencies.auth import TenantContext, get_tenant_context
from logs_sentinel.infrastructure.db.base import get_session
from logs_sentinel.infrastructure.db.models import (
    LogEventModel,
    ProjectModel,
    TenantModel,
    create_all_tables,
)

try:
    import aiosqlite  # noqa: F401

    HAS_AIOSQLITE = True
except ModuleNotFoundError:
    HAS_AIOSQLITE = False


@pytest.fixture
async def db_engine() -> AsyncGenerator[AsyncEngine]:
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(create_all_tables)
    yield engine
    await engine.dispose()


@pytest.fixture
async def seeded_session(db_engine: AsyncEngine) -> AsyncGenerator[AsyncSession]:
    async with AsyncSession(db_engine, expire_on_commit=False) as session:
        now = datetime.now(tz=UTC)
        t = TenantModel(name="Acme", created_at=now)
        session.add(t)
        await session.flush()
        p = ProjectModel(tenant_id=t.id, name="Backend", created_at=now)
        session.add(p)
        await session.flush()
        log1 = LogEventModel(
            tenant_id=t.id,
            project_id=p.id,
            received_at=now,
            level="error",
            message="Unhandled exception",
            exception_type=None,
            stacktrace=None,
            raw_json={"source": "api"},
        )
        log2 = LogEventModel(
            tenant_id=t.id,
            project_id=p.id,
            received_at=now,
            level="info",
            message="Started",
            exception_type=None,
            stacktrace=None,
            raw_json={},
        )
        session.add_all([log1, log2])
        await session.commit()
    async with AsyncSession(db_engine, expire_on_commit=False) as session:
        yield session


@pytest.mark.asyncio
@pytest.mark.skipif(not HAS_AIOSQLITE, reason="aiosqlite not installed")
async def test_list_logs_returns_items(
    seeded_session: AsyncSession, db_engine: AsyncEngine
) -> None:
    from logs_sentinel.main import create_app

    app = create_app()

    async def override_get_session() -> AsyncGenerator[AsyncSession]:
        async with AsyncSession(db_engine, expire_on_commit=False) as session:
            yield session

    def override_get_tenant_context() -> TenantContext:
        from logs_sentinel.domains.identity.entities import Role, TenantId, UserId

        return TenantContext(tenant_id=TenantId(1), user_id=UserId(1), role=Role.OWNER)

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_tenant_context] = override_get_tenant_context

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/api/v1/logs", headers={"Authorization": "Bearer skip"})
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert data["total"] >= 2
    assert len(data["items"]) >= 2
    levels = {it["level"] for it in data["items"]}
    assert "error" in levels
    assert "info" in levels

    app.dependency_overrides.clear()
