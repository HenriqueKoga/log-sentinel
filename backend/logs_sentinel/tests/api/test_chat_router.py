"""Tests for chat router with real DB and mocked billing (LLM disabled)."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from unittest.mock import MagicMock

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from logs_sentinel.api.v1.dependencies.auth import TenantContext, get_tenant_context
from logs_sentinel.api.v1.dependencies.services import get_billing_service, get_chat_service
from logs_sentinel.application.services.chat_service import ChatService
from logs_sentinel.infrastructure.db.base import get_session
from logs_sentinel.tests.factories import create_project, create_tenant


@pytest.fixture
async def seeded_chat(db_engine: AsyncEngine) -> tuple[AsyncEngine, int, int]:
    """Create tenant and project; return (engine, tenant_id, project_id)."""
    async with AsyncSession(db_engine, expire_on_commit=False) as session:
        tenant = create_tenant(session, name="Chat Tenant")
        await session.flush()
        project = create_project(session, tenant_id=tenant.id, name="API")
        await session.commit()
        tenant_id, project_id = tenant.id, project.id
    return db_engine, tenant_id, project_id


@pytest.mark.asyncio
async def test_create_session_returns_403_when_llm_disabled(
    seeded_chat: tuple[AsyncEngine, int, int],
) -> None:
    """POST /chat/sessions returns 403 LLM_DISABLED when tenant has no LLM-enabled plan."""
    from logs_sentinel.application.services.billing_service import BillingService
    from logs_sentinel.domains.identity.entities import Role, TenantId, UserId
    from logs_sentinel.main import create_app
    from logs_sentinel.tests.api.test_billing_usage import (
        InMemoryTenantPlanRepo,
        InMemoryUsageCounterRepo,
    )

    db_engine, tenant_id, project_id = seeded_chat
    app = create_app()

    async def override_get_session() -> AsyncGenerator[AsyncSession]:
        async with AsyncSession(db_engine, expire_on_commit=False) as session:
            yield session

    def override_get_tenant_context() -> TenantContext:
        return TenantContext(tenant_id=TenantId(tenant_id), user_id=UserId(1), role=Role.OWNER)

    # Billing with no plan -> is_llm_enabled False. Stub chat service to avoid OpenAI agent init.
    billing = BillingService(
        plans_repo=InMemoryTenantPlanRepo(),
        usage_repo=InMemoryUsageCounterRepo(),
    )
    stub_chat = MagicMock(spec=ChatService)

    def override_get_billing_service() -> BillingService:
        return billing

    def override_get_chat_service() -> ChatService:
        return stub_chat

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_tenant_context] = override_get_tenant_context
    app.dependency_overrides[get_billing_service] = override_get_billing_service
    app.dependency_overrides[get_chat_service] = override_get_chat_service

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/chat/sessions",
            json={"project_id": project_id, "title": "Test"},
            headers={"Authorization": "Bearer skip"},
        )
    assert response.status_code == 403
    assert response.json().get("detail", {}).get("code") == "LLM_DISABLED"

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_list_sessions_returns_403_when_llm_disabled(
    seeded_chat: tuple[AsyncEngine, int, int],
) -> None:
    """GET /chat/sessions returns 403 LLM_DISABLED when tenant has no LLM-enabled plan."""
    from logs_sentinel.application.services.billing_service import BillingService
    from logs_sentinel.domains.identity.entities import Role, TenantId, UserId
    from logs_sentinel.main import create_app
    from logs_sentinel.tests.api.test_billing_usage import (
        InMemoryTenantPlanRepo,
        InMemoryUsageCounterRepo,
    )

    db_engine, tenant_id, _ = seeded_chat
    app = create_app()

    async def override_get_session() -> AsyncGenerator[AsyncSession]:
        async with AsyncSession(db_engine, expire_on_commit=False) as session:
            yield session

    def override_get_tenant_context() -> TenantContext:
        return TenantContext(tenant_id=TenantId(tenant_id), user_id=UserId(1), role=Role.OWNER)

    billing = BillingService(
        plans_repo=InMemoryTenantPlanRepo(),
        usage_repo=InMemoryUsageCounterRepo(),
    )
    stub_chat = MagicMock(spec=ChatService)

    def override_get_billing_service() -> BillingService:
        return billing

    def override_get_chat_service() -> ChatService:
        return stub_chat

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_tenant_context] = override_get_tenant_context
    app.dependency_overrides[get_billing_service] = override_get_billing_service
    app.dependency_overrides[get_chat_service] = override_get_chat_service

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            "/api/v1/chat/sessions",
            headers={"Authorization": "Bearer skip"},
        )
    assert response.status_code == 403
    assert response.json().get("detail", {}).get("code") == "LLM_DISABLED"

    app.dependency_overrides.clear()
