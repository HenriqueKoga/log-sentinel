from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from logs_sentinel.domains.identity.entities import Tenant, TenantId, User, UserId
from logs_sentinel.infrastructure.db.base import Base, engine
from logs_sentinel.infrastructure.db.models import MembershipModel, TenantModel, UserModel
from logs_sentinel.infrastructure.db.repositories.identity import (
    MembershipRepositorySQLAlchemy,
    TenantRepositorySQLAlchemy,
    UserRepositorySQLAlchemy,
)


@pytest.mark.asyncio
async def test_membership_repository_respects_tenant_isolation() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSession(engine, expire_on_commit=False) as session:
        # Create two tenants and one user, but only one membership
        now = datetime.now(tz=timezone.utc)
        t1 = TenantModel(name="T1", created_at=now)
        t2 = TenantModel(name="T2", created_at=now)
        u1 = UserModel(
            email="user@example.com",
            password_hash="hash",
            is_active=True,
            created_at=now,
        )
        session.add_all([t1, t2, u1])
        await session.flush()

        m1 = MembershipModel(tenant_id=t1.id, user_id=u1.id, role="owner")
        session.add(m1)
        await session.commit()

        tenant_repo = TenantRepositorySQLAlchemy(session)
        user_repo = UserRepositorySQLAlchemy(session)
        membership_repo = MembershipRepositorySQLAlchemy(session)

        tenant = await tenant_repo.get_by_id(TenantId(t1.id))
        user = await user_repo.get_by_id(UserId(u1.id))
        assert isinstance(tenant, Tenant)
        assert isinstance(user, User)

        auth_user = await membership_repo.get_primary_membership(UserId(u1.id))
        assert auth_user is not None
        assert auth_user.tenant.id == TenantId(t1.id)

