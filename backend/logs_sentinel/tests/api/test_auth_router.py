"""Tests for auth router (login, refresh) with real DB and in-memory refresh store."""

from __future__ import annotations

from collections.abc import AsyncGenerator, Callable

import pytest
from argon2 import PasswordHasher
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from logs_sentinel.api.v1.routers.auth import get_auth_service
from logs_sentinel.application.services.auth_service import AuthService
from logs_sentinel.infrastructure.auth.jwt import JWTEncoderImpl
from logs_sentinel.infrastructure.db.repositories.identity import (
    MembershipRepositorySQLAlchemy,
    TenantRepositorySQLAlchemy,
    UserRepositorySQLAlchemy,
)
from logs_sentinel.tests.application.test_auth_service import InMemoryRefreshStore
from logs_sentinel.tests.factories import create_membership, create_tenant, create_user


@pytest.fixture
async def seeded_auth_user(db_engine: AsyncEngine) -> tuple[AsyncEngine, str, str]:
    """Create tenant, user (with hashed password), membership; return (engine, email, password)."""
    password = "test-pass-123"
    hasher = PasswordHasher()
    async with AsyncSession(db_engine, expire_on_commit=False) as session:
        tenant = create_tenant(session, name="Auth Tenant")
        await session.flush()
        user = create_user(
            session,
            email="user@example.com",
            password_hash=hasher.hash(password),
        )
        await session.flush()
        create_membership(session, tenant_id=tenant.id, user_id=user.id, role="owner")
        await session.commit()
    return db_engine, "user@example.com", password


# 32-byte secret to avoid PyJWT InsecureKeyLengthWarning (HS256 recommends >= 32 bytes)
_JWT_SECRET_32 = "test-jwt-secret-32-bytes-long!!!!!!!!"


def _make_auth_service_override(
    db_engine: AsyncEngine, refresh_store: InMemoryRefreshStore
) -> Callable[[], AsyncGenerator[AuthService]]:
    from argon2 import PasswordHasher
    jwt_encoder = JWTEncoderImpl(secret_key=_JWT_SECRET_32, algorithm="HS256")
    async def override_get_auth_service() -> AsyncGenerator[AuthService]:
        async with AsyncSession(db_engine, expire_on_commit=False) as session:
            yield AuthService(
                tenant_repo=TenantRepositorySQLAlchemy(session),
                user_repo=UserRepositorySQLAlchemy(session),
                membership_repo=MembershipRepositorySQLAlchemy(session),
                refresh_store=refresh_store,
                jwt_encoder=jwt_encoder,
                password_hasher=PasswordHasher(),
            )
    return override_get_auth_service


@pytest.mark.asyncio
async def test_login_success(seeded_auth_user: tuple[AsyncEngine, str, str]) -> None:
    from logs_sentinel.main import create_app

    db_engine, email, password = seeded_auth_user
    app = create_app()
    refresh_store = InMemoryRefreshStore()
    app.dependency_overrides[get_auth_service] = _make_auth_service_override(db_engine, refresh_store)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": password},
        )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_login_invalid_credentials(seeded_auth_user: tuple[AsyncEngine, str, str]) -> None:
    from logs_sentinel.main import create_app

    db_engine, email, _ = seeded_auth_user
    app = create_app()
    refresh_store = InMemoryRefreshStore()
    app.dependency_overrides[get_auth_service] = _make_auth_service_override(db_engine, refresh_store)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": "wrongpassword"},
        )
    assert response.status_code == 400
    assert response.json().get("detail", {}).get("code") == "AUTH_INVALID_CREDENTIALS"

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_refresh_success(seeded_auth_user: tuple[AsyncEngine, str, str]) -> None:
    from logs_sentinel.main import create_app

    db_engine, email, password = seeded_auth_user
    app = create_app()
    refresh_store = InMemoryRefreshStore()
    app.dependency_overrides[get_auth_service] = _make_auth_service_override(db_engine, refresh_store)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        login_resp = await client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": password},
        )
    assert login_resp.status_code == 200
    refresh_token = login_resp.json()["refresh_token"]

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        refresh_resp = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )
    assert refresh_resp.status_code == 200
    refresh_data = refresh_resp.json()
    assert "access_token" in refresh_data and "refresh_token" in refresh_data

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_signup_success(db_engine: AsyncEngine) -> None:
    from logs_sentinel.main import create_app

    app = create_app()
    refresh_store = InMemoryRefreshStore()
    app.dependency_overrides[get_auth_service] = _make_auth_service_override(db_engine, refresh_store)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/auth/signup",
            json={
                "tenant_name": "New Tenant",
                "email": "owner@example.com",
                "password": "password123",
            },
        )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data and "refresh_token" in data

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_signup_email_exists(seeded_auth_user: tuple[AsyncEngine, str, str]) -> None:
    from logs_sentinel.main import create_app

    db_engine, email, _ = seeded_auth_user
    app = create_app()
    refresh_store = InMemoryRefreshStore()
    app.dependency_overrides[get_auth_service] = _make_auth_service_override(db_engine, refresh_store)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/auth/signup",
            json={
                "tenant_name": "Other Tenant",
                "email": email,
                "password": "password123",
            },
        )
    assert response.status_code == 400
    assert response.json().get("detail", {}).get("code") == "AUTH_EMAIL_EXISTS"

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_logout_returns_204() -> None:
    from logs_sentinel.main import create_app

    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/auth/logout")
    assert response.status_code == 204

    app.dependency_overrides.clear()
