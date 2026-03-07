"""Tests for alerts router (rules CRUD) with real DB."""

from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from logs_sentinel.api.v1.dependencies.auth import TenantContext, get_tenant_context
from logs_sentinel.infrastructure.db.base import get_session
from logs_sentinel.tests.factories import create_project, create_tenant


@pytest.fixture
async def seeded_alerts(db_engine: AsyncEngine) -> tuple[AsyncEngine, int, int]:
    """Create tenant and project; return (engine, tenant_id, project_id)."""
    async with AsyncSession(db_engine, expire_on_commit=False) as session:
        tenant = create_tenant(session, name="Alerts Tenant")
        await session.flush()
        project = create_project(session, tenant_id=tenant.id, name="API")
        await session.commit()
        tenant_id, project_id = tenant.id, project.id
    return db_engine, tenant_id, project_id


@pytest.mark.asyncio
async def test_create_rule_and_list_rules(
    seeded_alerts: tuple[AsyncEngine, int, int],
) -> None:
    from logs_sentinel.domains.identity.entities import Role, TenantId, UserId
    from logs_sentinel.main import create_app

    db_engine, tenant_id, project_id = seeded_alerts
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
            "/api/v1/alerts/rules",
            json={
                "project_id": project_id,
                "name": "High error count",
                "kind": "count_5m",
                "threshold": 10.0,
            },
            headers={"Authorization": "Bearer skip"},
        )
    assert create_resp.status_code == 201
    rule = create_resp.json()
    assert rule["name"] == "High error count"
    assert rule["kind"] == "count_5m"
    assert rule["threshold"] == 10.0
    assert rule["project_id"] == project_id
    rule_id = rule["id"]

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        list_resp = await client.get(
            "/api/v1/alerts/rules",
            params={"project_id": project_id},
            headers={"Authorization": "Bearer skip"},
        )
    assert list_resp.status_code == 200
    rules = list_resp.json()
    assert isinstance(rules, list)
    assert len(rules) >= 1
    assert any(r["id"] == rule_id and r["name"] == "High error count" for r in rules)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        patch_resp = await client.patch(
            f"/api/v1/alerts/rules/{rule_id}",
            json={"name": "Updated name", "enabled": False},
            headers={"Authorization": "Bearer skip"},
        )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["name"] == "Updated name"
    assert patch_resp.json()["enabled"] is False

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        del_resp = await client.delete(
            f"/api/v1/alerts/rules/{rule_id}",
            headers={"Authorization": "Bearer skip"},
        )
    assert del_resp.status_code == 204

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_list_rules_empty(seeded_alerts: tuple[AsyncEngine, int, int]) -> None:
    from logs_sentinel.domains.identity.entities import Role, TenantId, UserId
    from logs_sentinel.main import create_app

    db_engine, tenant_id, project_id = seeded_alerts
    app = create_app()

    async def override_get_session() -> AsyncGenerator[AsyncSession]:
        async with AsyncSession(db_engine, expire_on_commit=False) as session:
            yield session

    def override_get_tenant_context() -> TenantContext:
        return TenantContext(tenant_id=TenantId(tenant_id), user_id=UserId(1), role=Role.OWNER)

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_tenant_context] = override_get_tenant_context

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            "/api/v1/alerts/rules",
            headers={"Authorization": "Bearer skip"},
        )
    assert response.status_code == 200
    assert response.json() == []

    app.dependency_overrides.clear()
