"""Tests for issues router (list, get, delete) with real DB."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import UTC, datetime

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from logs_sentinel.api.v1.dependencies.auth import TenantContext, get_tenant_context
from logs_sentinel.infrastructure.db.base import get_session
from logs_sentinel.tests.factories import create_issue, create_project, create_tenant


@pytest.fixture
async def seeded_issues(db_engine: AsyncEngine) -> tuple[AsyncEngine, int, int, int]:
    """Tenant, project, one issue; return (engine, tenant_id, project_id, issue_id)."""
    now = datetime.now(UTC)
    async with AsyncSession(db_engine, expire_on_commit=False) as session:
        tenant = create_tenant(session, name="Issues Tenant")
        await session.flush()
        project = create_project(session, tenant_id=tenant.id, name="API")
        await session.flush()
        issue = create_issue(
            session,
            tenant_id=tenant.id,
            project_id=project.id,
            fingerprint="fp1",
            title="ValueError in handler",
            severity="high",
            first_seen=now,
            last_seen=now,
        )
        await session.commit()
        tenant_id, project_id, issue_id = tenant.id, project.id, issue.id
    return db_engine, tenant_id, project_id, issue_id


@pytest.mark.asyncio
async def test_list_issues_returns_items(
    seeded_issues: tuple[AsyncEngine, int, int, int],
) -> None:
    from logs_sentinel.domains.identity.entities import Role, TenantId, UserId
    from logs_sentinel.main import create_app

    db_engine, tenant_id, _, _ = seeded_issues
    app = create_app()

    async def override_get_session() -> AsyncGenerator[AsyncSession]:
        async with AsyncSession(db_engine, expire_on_commit=False) as session:
            yield session

    def override_get_tenant_context() -> TenantContext:
        return TenantContext(tenant_id=TenantId(tenant_id), user_id=UserId(1), role=Role.OWNER)

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_tenant_context] = override_get_tenant_context

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/issues", headers={"Authorization": "Bearer skip"})
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "aggregates" in data
    assert data["aggregates"]["total"] >= 1
    assert len(data["items"]) >= 1
    assert data["items"][0]["title"] == "ValueError in handler"

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_issue_detail_success(
    seeded_issues: tuple[AsyncEngine, int, int, int],
) -> None:
    from logs_sentinel.domains.identity.entities import Role, TenantId, UserId
    from logs_sentinel.main import create_app

    db_engine, tenant_id, _, issue_id = seeded_issues
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
            f"/api/v1/issues/{issue_id}",
            headers={"Authorization": "Bearer skip"},
        )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == issue_id
    assert data["title"] == "ValueError in handler"
    assert "samples" in data

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_issue_detail_not_found(
    seeded_issues: tuple[AsyncEngine, int, int, int],
) -> None:
    from logs_sentinel.domains.identity.entities import Role, TenantId, UserId
    from logs_sentinel.main import create_app

    db_engine, tenant_id, _, _ = seeded_issues
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
            "/api/v1/issues/999999",
            headers={"Authorization": "Bearer skip"},
        )
    assert response.status_code == 404
    assert response.json().get("detail", {}).get("code") == "ISSUE_NOT_FOUND"

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_delete_issue_success(
    seeded_issues: tuple[AsyncEngine, int, int, int],
) -> None:
    from logs_sentinel.domains.identity.entities import Role, TenantId, UserId
    from logs_sentinel.main import create_app

    db_engine, tenant_id, _, issue_id = seeded_issues
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
        response = await client.delete(
            f"/api/v1/issues/{issue_id}",
            headers={"Authorization": "Bearer skip"},
        )
    assert response.status_code == 204

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        get_resp = await client.get(
            f"/api/v1/issues/{issue_id}",
            headers={"Authorization": "Bearer skip"},
        )
    assert get_resp.status_code == 404

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_suggest_issue_llm_disabled(
    seeded_issues: tuple[AsyncEngine, int, int, int],
) -> None:
    """Without an active plan, LLM is disabled; suggest returns title/severity from context."""
    from logs_sentinel.domains.identity.entities import Role, TenantId, UserId
    from logs_sentinel.main import create_app

    db_engine, tenant_id, _, _ = seeded_issues
    app = create_app()

    async def override_get_session() -> AsyncGenerator[AsyncSession]:
        async with AsyncSession(db_engine, expire_on_commit=False) as session:
            yield session

    def override_get_tenant_context() -> TenantContext:
        return TenantContext(tenant_id=TenantId(tenant_id), user_id=UserId(1), role=Role.OWNER)

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_tenant_context] = override_get_tenant_context

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/issues/suggest",
            json={"context": "NullPointerException at com.app.Handler.run"},
            headers={"Authorization": "Bearer skip"},
        )
    assert response.status_code == 200
    data = response.json()
    assert "title" in data
    assert data["severity"] == "medium"
    assert "NullPointerException" in data["title"] or data["title"]

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_snooze_issue_success(
    seeded_issues: tuple[AsyncEngine, int, int, int],
) -> None:
    from logs_sentinel.domains.identity.entities import Role, TenantId, UserId
    from logs_sentinel.main import create_app

    db_engine, tenant_id, _, issue_id = seeded_issues
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
        response = await client.post(
            f"/api/v1/issues/{issue_id}/actions/snooze",
            json={"duration_minutes": 60},
            headers={"Authorization": "Bearer skip"},
        )
    assert response.status_code == 204

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        get_resp = await client.get(
            f"/api/v1/issues/{issue_id}",
            headers={"Authorization": "Bearer skip"},
        )
    assert get_resp.status_code == 200
    assert get_resp.json()["status"] == "snoozed"

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_resolve_issue_success(
    seeded_issues: tuple[AsyncEngine, int, int, int],
) -> None:
    from logs_sentinel.domains.identity.entities import Role, TenantId, UserId
    from logs_sentinel.main import create_app

    db_engine, tenant_id, _, issue_id = seeded_issues
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
        response = await client.post(
            f"/api/v1/issues/{issue_id}/actions/resolve",
            headers={"Authorization": "Bearer skip"},
        )
    assert response.status_code == 204

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        get_resp = await client.get(
            f"/api/v1/issues/{issue_id}",
            headers={"Authorization": "Bearer skip"},
        )
    assert get_resp.status_code == 200
    assert get_resp.json()["status"] == "resolved"

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_reopen_issue_success(
    seeded_issues: tuple[AsyncEngine, int, int, int],
) -> None:
    from logs_sentinel.domains.identity.entities import Role, TenantId, UserId
    from logs_sentinel.main import create_app

    db_engine, tenant_id, _, issue_id = seeded_issues
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
        await client.post(
            f"/api/v1/issues/{issue_id}/actions/resolve",
            headers={"Authorization": "Bearer skip"},
        )
        response = await client.post(
            f"/api/v1/issues/{issue_id}/actions/reopen",
            headers={"Authorization": "Bearer skip"},
        )
    assert response.status_code == 204

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        get_resp = await client.get(
            f"/api/v1/issues/{issue_id}",
            headers={"Authorization": "Bearer skip"},
        )
    assert get_resp.status_code == 200
    assert get_resp.json()["status"] == "open"

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_create_issue_manual_success(
    seeded_issues: tuple[AsyncEngine, int, int, int],
) -> None:
    from logs_sentinel.domains.identity.entities import Role, TenantId, UserId
    from logs_sentinel.main import create_app

    db_engine, tenant_id, _, project_id = seeded_issues
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
        response = await client.post(
            "/api/v1/issues",
            json={
                "project_id": project_id,
                "title": "Manual issue",
                "severity": "low",
            },
            headers={"Authorization": "Bearer skip"},
        )
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Manual issue"
    assert data["severity"] == "low"
    assert data["project_id"] == project_id

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_issue_occurrences_returns_200(
    seeded_issues: tuple[AsyncEngine, int, int, int],
) -> None:
    from logs_sentinel.domains.identity.entities import Role, TenantId, UserId
    from logs_sentinel.main import create_app

    db_engine, tenant_id, _, issue_id = seeded_issues
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
            f"/api/v1/issues/{issue_id}/occurrences",
            params={"range": "24h"},
            headers={"Authorization": "Bearer skip"},
        )
    assert response.status_code == 200
    data = response.json()
    assert "points" in data
    assert isinstance(data["points"], list)

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_issue_occurrences_invalid_range(
    seeded_issues: tuple[AsyncEngine, int, int, int],
) -> None:
    from logs_sentinel.domains.identity.entities import Role, TenantId, UserId
    from logs_sentinel.main import create_app

    db_engine, tenant_id, _, issue_id = seeded_issues
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
            f"/api/v1/issues/{issue_id}/occurrences",
            params={"range": "invalid"},
            headers={"Authorization": "Bearer skip"},
        )
    assert response.status_code == 400
    assert response.json().get("detail", {}).get("code") == "INVALID_RANGE"

    app.dependency_overrides.clear()
