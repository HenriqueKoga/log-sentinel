"""Tests for projects router (list, create, tokens) with real DB."""

from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from logs_sentinel.api.v1.dependencies.auth import TenantContext, get_tenant_context
from logs_sentinel.infrastructure.db.base import get_session
from logs_sentinel.tests.factories import create_project, create_tenant


@pytest.fixture
async def seeded_projects(db_engine: AsyncEngine) -> tuple[AsyncEngine, int]:
    async with AsyncSession(db_engine, expire_on_commit=False) as session:
        tenant = create_tenant(session, name="Projects Tenant")
        await session.flush()
        create_project(session, tenant_id=tenant.id, name="API")
        await session.commit()
        tenant_id = tenant.id
    return db_engine, tenant_id


@pytest.mark.asyncio
async def test_list_projects_returns_items(
    seeded_projects: tuple[AsyncEngine, int],
) -> None:
    from logs_sentinel.domains.identity.entities import Role, TenantId, UserId
    from logs_sentinel.main import create_app

    db_engine, tenant_id = seeded_projects
    app = create_app()

    async def override_get_session() -> AsyncGenerator[AsyncSession]:
        async with AsyncSession(db_engine, expire_on_commit=False) as session:
            yield session

    def override_get_tenant_context() -> TenantContext:
        return TenantContext(tenant_id=TenantId(tenant_id), user_id=UserId(1), role=Role.OWNER)

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_tenant_context] = override_get_tenant_context

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/projects", headers={"Authorization": "Bearer skip"})
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert data[0]["name"] == "API"

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_create_project_and_create_token(
    seeded_projects: tuple[AsyncEngine, int],
) -> None:
    from logs_sentinel.domains.identity.entities import Role, TenantId, UserId
    from logs_sentinel.main import create_app

    db_engine, tenant_id = seeded_projects
    app = create_app()

    async def override_get_session() -> AsyncGenerator[AsyncSession]:
        async with AsyncSession(db_engine, expire_on_commit=False) as session:
            async with session.begin():
                yield session

    def override_get_tenant_context() -> TenantContext:
        return TenantContext(tenant_id=TenantId(tenant_id), user_id=UserId(1), role=Role.OWNER)

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_tenant_context] = override_get_tenant_context

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        create_resp = await client.post(
            "/api/v1/projects",
            json={"name": "New Project"},
            headers={"Authorization": "Bearer skip"},
        )
    assert create_resp.status_code == 201
    project = create_resp.json()
    project_id = project["id"]

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token_resp = await client.post(
            f"/api/v1/projects/{project_id}/tokens",
            json={"name": "CI"},
            headers={"Authorization": "Bearer skip"},
        )
    assert token_resp.status_code == 201
    token_data = token_resp.json()
    assert "token" in token_data
    assert len(token_data["token"]) > 0
    assert token_data["name"] == "CI"
    token_id = token_data["id"]

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        revoke_resp = await client.post(
            f"/api/v1/projects/{project_id}/tokens/{token_id}/revoke",
            headers={"Authorization": "Bearer skip"},
        )
    assert revoke_resp.status_code == 204

    app.dependency_overrides.clear()
