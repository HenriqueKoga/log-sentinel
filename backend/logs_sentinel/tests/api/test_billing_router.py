"""Tests for billing router (plan, usage, settings) with real DB."""

from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from logs_sentinel.api.v1.dependencies.auth import TenantContext, get_tenant_context
from logs_sentinel.api.v1.dependencies.services import get_billing_service
from logs_sentinel.infrastructure.db.base import get_session
from logs_sentinel.tests.factories import create_tenant


@pytest.fixture
async def seeded_billing(db_engine: AsyncEngine) -> tuple[AsyncEngine, int]:
    """Create tenant; return (engine, tenant_id)."""
    async with AsyncSession(db_engine, expire_on_commit=False) as session:
        tenant = create_tenant(session, name="Billing Tenant")
        await session.commit()
        tenant_id = tenant.id
    return db_engine, tenant_id


@pytest.mark.asyncio
async def test_get_plan_returns_200(seeded_billing: tuple[AsyncEngine, int]) -> None:
    from logs_sentinel.domains.identity.entities import Role, TenantId, UserId
    from logs_sentinel.main import create_app

    db_engine, tenant_id = seeded_billing
    app = create_app()

    async def override_get_session() -> AsyncGenerator[AsyncSession]:
        async with AsyncSession(db_engine, expire_on_commit=False) as session:
            yield session

    def override_get_tenant_context() -> TenantContext:
        return TenantContext(tenant_id=TenantId(tenant_id), user_id=UserId(1), role=Role.OWNER)

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_tenant_context] = override_get_tenant_context

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/billing/plan", headers={"Authorization": "Bearer skip"})
    assert response.status_code == 200
    data = response.json()
    assert "plan_type" in data
    assert "status" in data
    assert "enable_llm_enrichment" in data

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_usage_returns_200(seeded_billing: tuple[AsyncEngine, int]) -> None:
    from logs_sentinel.domains.identity.entities import Role, TenantId, UserId
    from logs_sentinel.main import create_app

    db_engine, tenant_id = seeded_billing
    app = create_app()

    async def override_get_session() -> AsyncGenerator[AsyncSession]:
        async with AsyncSession(db_engine, expire_on_commit=False) as session:
            yield session

    def override_get_tenant_context() -> TenantContext:
        return TenantContext(tenant_id=TenantId(tenant_id), user_id=UserId(1), role=Role.OWNER)

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_tenant_context] = override_get_tenant_context

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/billing/usage", headers={"Authorization": "Bearer skip"})
    assert response.status_code == 200
    data = response.json()
    assert "plan_type" in data
    assert "events_ingested" in data
    assert "llm_enrichments" in data

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_credit_bar_returns_200(seeded_billing: tuple[AsyncEngine, int]) -> None:
    from logs_sentinel.domains.identity.entities import Role, TenantId, UserId
    from logs_sentinel.main import create_app

    db_engine, tenant_id = seeded_billing
    app = create_app()

    async def override_get_session() -> AsyncGenerator[AsyncSession]:
        async with AsyncSession(db_engine, expire_on_commit=False) as session:
            yield session

    def override_get_tenant_context() -> TenantContext:
        return TenantContext(tenant_id=TenantId(tenant_id), user_id=UserId(1), role=Role.OWNER)

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_tenant_context] = override_get_tenant_context

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.get("/api/v1/billing/plan", headers={"Authorization": "Bearer skip"})
        response = await client.get("/api/v1/billing/credit-bar", headers={"Authorization": "Bearer skip"})
    assert response.status_code == 200
    data = response.json()
    assert "credits_used" in data
    assert "credits_limit" in data
    assert "percentage" in data
    assert data["percentage"] >= 0

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_update_settings_returns_400_when_no_plan(seeded_billing: tuple[AsyncEngine, int]) -> None:
    """PATCH /settings without an active plan returns 400 NO_ACTIVE_PLAN.
    (With default flow, GET /plan creates a plan; so we use a fresh tenant and mock no plan.)
    """
    from logs_sentinel.domains.identity.entities import Role, TenantId, UserId
    from logs_sentinel.main import create_app

    db_engine, tenant_id = seeded_billing
    app = create_app()

    async def override_get_session() -> AsyncGenerator[AsyncSession]:
        async with AsyncSession(db_engine, expire_on_commit=False) as session:
            yield session

    def override_get_tenant_context() -> TenantContext:
        return TenantContext(tenant_id=TenantId(tenant_id), user_id=UserId(1), role=Role.OWNER)

    # Use a billing service that has no plan: create tenant with no plan and don't call get_plan first.
    # Actually get_usage_summary in get_plan creates the plan. So to get NO_ACTIVE_PLAN we need
    # a billing service that returns None for get_active_plan. Easiest: override get_billing_service
    # with a stub that has get_active_plan -> None, then get_plan would still call get_usage_summary
    # which would create plan... So the billing router get_plan calls billing.get_usage_summary
    # and billing.get_active_plan. For update_settings it only calls billing.get_active_plan and
    # if None returns 400. So we need a tenant that has no plan in DB. But get_usage_summary
    # creates one. So the only way is to override get_billing_service with a stub that
    # get_active_plan returns None. Let me do that.
    from logs_sentinel.application.services.billing_service import BillingService
    from logs_sentinel.tests.api.test_billing_usage import (
        InMemoryTenantPlanRepo,
        InMemoryUsageCounterRepo,
    )

    async def override_get_billing_service() -> BillingService:
        return BillingService(
            plans_repo=InMemoryTenantPlanRepo(),
            usage_repo=InMemoryUsageCounterRepo(),
        )

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_tenant_context] = override_get_tenant_context
    app.dependency_overrides[get_billing_service] = override_get_billing_service

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.patch(
            "/api/v1/billing/settings",
            json={"enable_llm_enrichment": True},
            headers={"Authorization": "Bearer skip"},
        )
    assert response.status_code == 400
    assert response.json().get("detail", {}).get("code") == "NO_ACTIVE_PLAN"

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_update_settings_success(seeded_billing: tuple[AsyncEngine, int]) -> None:
    """GET /plan creates default plan; then PATCH /settings can enable LLM."""
    from logs_sentinel.domains.identity.entities import Role, TenantId, UserId
    from logs_sentinel.main import create_app

    db_engine, tenant_id = seeded_billing
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
        await client.get("/api/v1/billing/plan", headers={"Authorization": "Bearer skip"})
        patch_resp = await client.patch(
            "/api/v1/billing/settings",
            json={"enable_llm_enrichment": True},
            headers={"Authorization": "Bearer skip"},
        )
    assert patch_resp.status_code == 200
    assert patch_resp.json().get("enable_llm_enrichment") is True

    app.dependency_overrides.clear()
