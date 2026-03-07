"""Tests for identity DB repositories (tenant isolation) with real DB and repos."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from logs_sentinel.domains.identity.entities import Tenant, TenantId, User, UserId
from logs_sentinel.infrastructure.db.repositories.identity import (
    MembershipRepositorySQLAlchemy,
    TenantRepositorySQLAlchemy,
    UserRepositorySQLAlchemy,
)
from logs_sentinel.tests.factories import create_membership, create_tenant, create_user


@pytest.mark.asyncio
async def test_membership_repository_respects_tenant_isolation(
    db_engine: AsyncEngine,
) -> None:
    """Real Tenant/User/Membership repos read from seeded DB (new session after commit)."""
    async with AsyncSession(db_engine, expire_on_commit=False) as session:
        tenant1 = create_tenant(session, name="T1")
        create_tenant(session, name="T2")
        user = create_user(session, email="user@example.com", password_hash="hash")
        await session.flush()
        create_membership(session, tenant_id=tenant1.id, user_id=user.id, role="owner")
        await session.commit()
        tenant_id, user_id = tenant1.id, user.id

    async with AsyncSession(db_engine, expire_on_commit=False) as session:
        tenant_repo = TenantRepositorySQLAlchemy(session)
        user_repo = UserRepositorySQLAlchemy(session)
        membership_repo = MembershipRepositorySQLAlchemy(session)

        tenant = await tenant_repo.get_by_id(TenantId(tenant_id))
        user_loaded = await user_repo.get_by_id(UserId(user_id))
        assert isinstance(tenant, Tenant)
        assert isinstance(user_loaded, User)

        auth_user = await membership_repo.get_primary_membership(UserId(user_id))
        assert auth_user is not None
        assert auth_user.tenant.id == TenantId(tenant_id)
