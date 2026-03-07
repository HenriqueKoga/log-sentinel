"""Tests for GET /api/v1/logs router (real DB and repositories)."""

from __future__ import annotations

from collections.abc import AsyncGenerator

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
async def seeded_logs(db_engine: AsyncEngine) -> tuple[AsyncEngine, int, int]:
    """Create tenant, project, and log events in the real DB; return (engine, tenant_id, project_id)."""
    async with AsyncSession(db_engine, expire_on_commit=False) as session:
        tenant = create_tenant(session, name="Acme")
        await session.flush()
        project = create_project(session, tenant_id=tenant.id, name="Backend")
        await session.flush()
        create_log_event(
            session,
            tenant_id=tenant.id,
            project_id=project.id,
            level="error",
            message="Unhandled exception",
            raw_json={"source": "api"},
        )
        create_log_event(
            session,
            tenant_id=tenant.id,
            project_id=project.id,
            level="info",
            message="Started",
            raw_json={},
        )
        await session.commit()
        tenant_id, project_id = tenant.id, project.id
    return db_engine, tenant_id, project_id


@pytest.mark.asyncio
async def test_list_logs_returns_items(seeded_logs: tuple[AsyncEngine, int, int]) -> None:
    from logs_sentinel.domains.identity.entities import Role, TenantId, UserId
    from logs_sentinel.main import create_app

    db_engine, tenant_id, project_id = seeded_logs
    del project_id  # list can be without project filter

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


@pytest.mark.asyncio
async def test_get_log_detail_success(seeded_logs: tuple[AsyncEngine, int, int]) -> None:
    from logs_sentinel.domains.identity.entities import Role, TenantId, UserId
    from logs_sentinel.main import create_app

    db_engine, tenant_id, project_id = seeded_logs
    async with AsyncSession(db_engine, expire_on_commit=False) as session:
        from sqlalchemy import select

        from logs_sentinel.infrastructure.db.models import LogEventModel
        r = await session.execute(select(LogEventModel).where(LogEventModel.tenant_id == tenant_id).limit(1))
        log = r.scalar_one_or_none()
    assert log is not None
    log_id = log.id

    app = create_app()

    async def override_get_session() -> AsyncGenerator[AsyncSession]:
        async with AsyncSession(db_engine, expire_on_commit=False) as session:
            yield session

    def override_get_tenant_context() -> TenantContext:
        return TenantContext(tenant_id=TenantId(tenant_id), user_id=UserId(1), role=Role.OWNER)

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_tenant_context] = override_get_tenant_context

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(f"/api/v1/logs/{log_id}", headers={"Authorization": "Bearer skip"})
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == log_id
    assert "message" in data
    assert "level" in data

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_log_detail_not_found(seeded_logs: tuple[AsyncEngine, int, int]) -> None:
    from logs_sentinel.domains.identity.entities import Role, TenantId, UserId
    from logs_sentinel.main import create_app

    db_engine, tenant_id, _ = seeded_logs
    app = create_app()

    async def override_get_session() -> AsyncGenerator[AsyncSession]:
        async with AsyncSession(db_engine, expire_on_commit=False) as session:
            yield session

    def override_get_tenant_context() -> TenantContext:
        return TenantContext(tenant_id=TenantId(tenant_id), user_id=UserId(1), role=Role.OWNER)

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_tenant_context] = override_get_tenant_context

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/logs/999999", headers={"Authorization": "Bearer skip"})
    assert response.status_code == 404
    assert response.json().get("detail", {}).get("code") == "LOG_NOT_FOUND"

    app.dependency_overrides.clear()
