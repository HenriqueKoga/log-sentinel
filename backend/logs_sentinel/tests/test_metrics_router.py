"""Tests for GET /api/v1/metrics/dashboard router."""

from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.pool import StaticPool

from logs_sentinel.api.v1.dependencies.auth import TenantContext, get_tenant_context
from logs_sentinel.infrastructure.db.base import get_session
from logs_sentinel.infrastructure.db.models import create_all_tables

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


@pytest.mark.asyncio
@pytest.mark.skipif(not HAS_AIOSQLITE, reason="aiosqlite not installed")
async def test_dashboard_metrics_returns_series(db_engine: AsyncEngine) -> None:
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
        response = await client.get("/api/v1/metrics/dashboard?minutes=30")
    assert response.status_code == 200
    data = response.json()
    assert "log_volume" in data
    assert "error_rate" in data
    assert isinstance(data["log_volume"], list)
    assert isinstance(data["error_rate"], list)

    app.dependency_overrides.clear()
