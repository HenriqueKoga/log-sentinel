"""Tests for GET /api/v1/metrics/dashboard router (real DB and MetricsRepository)."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from logs_sentinel.api.v1.dependencies.auth import TenantContext, get_tenant_context
from logs_sentinel.infrastructure.db.base import get_session
from logs_sentinel.tests.factories import (
    create_log_event,
    create_project,
    create_tenant,
)


@pytest.fixture
async def seeded_metrics(db_engine: AsyncEngine) -> tuple[AsyncEngine, int]:
    """Create tenant, project, and log events for dashboard metrics; return (engine, tenant_id)."""
    now = datetime.now(UTC)
    async with AsyncSession(db_engine, expire_on_commit=False) as session:
        tenant = create_tenant(session, name="Metrics Tenant", created_at=now)
        await session.flush()
        project = create_project(session, tenant_id=tenant.id, name="API", created_at=now)
        await session.flush()
        for i in range(3):
            create_log_event(
                session,
                tenant_id=tenant.id,
                project_id=project.id,
                level="error" if i % 2 == 0 else "info",
                message=f"Event {i}",
                received_at=now - timedelta(minutes=i * 5),
                raw_json={},
            )
        await session.commit()
        tenant_id = tenant.id
    return db_engine, tenant_id


@pytest.mark.asyncio
async def test_dashboard_metrics_returns_series(
    seeded_metrics: tuple[AsyncEngine, int],
) -> None:
    from logs_sentinel.domains.identity.entities import Role, TenantId, UserId
    from logs_sentinel.main import create_app

    db_engine, tenant_id = seeded_metrics

    app = create_app()

    async def override_get_session() -> AsyncGenerator[AsyncSession]:
        async with AsyncSession(db_engine, expire_on_commit=False) as session:
            yield session

    def override_get_tenant_context() -> TenantContext:
        return TenantContext(
            tenant_id=TenantId(tenant_id),
            user_id=UserId(1),
            role=Role.OWNER,
        )

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
