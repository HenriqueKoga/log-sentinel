"""Tests for GET /api/v1/ai-insights/fix-suggestions (real DB, real FixSuggestionsService and repos)."""

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
async def seeded_ai_insights(db_engine: AsyncEngine) -> tuple[AsyncEngine, int, int]:
    """Seed tenant, project, and error log events with two distinct fingerprints."""
    now = datetime.now(UTC)
    async with AsyncSession(db_engine, expire_on_commit=False) as session:
        tenant = create_tenant(session, name="AI Insights Tenant", created_at=now)
        await session.flush()
        project = create_project(session, tenant_id=tenant.id, name="Backend", created_at=now)
        await session.flush()
        # Fingerprint 1: ValueError
        for _ in range(2):
            create_log_event(
                session,
                tenant_id=tenant.id,
                project_id=project.id,
                level="error",
                message="ValueError: invalid value",
                exception_type="ValueError",
                stacktrace="  File 'x.py', line 1",
                received_at=now - timedelta(minutes=5),
                raw_json={},
            )
        # Fingerprint 2: TypeError
        create_log_event(
            session,
            tenant_id=tenant.id,
            project_id=project.id,
            level="error",
            message="TypeError: bad type",
            exception_type="TypeError",
            stacktrace="  File 'y.py', line 2",
            received_at=now - timedelta(minutes=1),
            raw_json={},
        )
        await session.commit()
        tenant_id, project_id = tenant.id, project.id
    return db_engine, tenant_id, project_id


@pytest.mark.asyncio
async def test_fix_suggestions_returns_paginated_response(
    seeded_ai_insights: tuple[AsyncEngine, int, int],
) -> None:
    from logs_sentinel.domains.identity.entities import Role, TenantId, UserId
    from logs_sentinel.main import create_app

    db_engine, tenant_id, project_id = seeded_ai_insights

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
        response = await client.get(
            f"/api/v1/ai-insights/fix-suggestions?project_id={project_id}&page=1&page_size=1&sort_by=occurrences&order=desc"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 2
        assert len(data["items"]) == 1
        first = data["items"][0]
        assert "fingerprint" in first
        assert "occurrences" in first
        assert first["occurrences"] >= 1
        assert "analyzed" in first

        response2 = await client.get(
            f"/api/v1/ai-insights/fix-suggestions?project_id={project_id}&page=2&page_size=1"
        )
        assert response2.status_code == 200
        data2 = response2.json()
        assert data2["total"] >= 2
        assert len(data2["items"]) >= 1

    app.dependency_overrides.clear()
