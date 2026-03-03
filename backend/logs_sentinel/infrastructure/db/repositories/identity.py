from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from logs_sentinel.domains.identity.entities import (
    AuthenticatedUser,
    Membership,
    Role,
    Tenant,
    TenantId,
    User,
    UserId,
)
from logs_sentinel.domains.identity.repositories import (
    MembershipRepository,
    TenantRepository,
    UserRepository,
)
from logs_sentinel.infrastructure.db.models import MembershipModel, TenantModel, UserModel


class TenantRepositorySQLAlchemy(TenantRepository):
    """SQLAlchemy implementation of tenant repository."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, tenant_id: TenantId) -> Tenant | None:
        stmt = select(TenantModel).where(TenantModel.id == int(tenant_id))
        result = await self._session.scalar(stmt)
        if result is None:
            return None
        return Tenant(
            id=TenantId(result.id),
            name=result.name,
            created_at=result.created_at,
        )

    async def get_by_name(self, name: str) -> Tenant | None:
        stmt = select(TenantModel).where(TenantModel.name == name)
        result = await self._session.scalar(stmt)
        if result is None:
            return None
        return Tenant(
            id=TenantId(result.id),
            name=result.name,
            created_at=result.created_at,
        )

    async def create(self, name: str) -> Tenant:
        now = datetime.now(tz=UTC)
        model = TenantModel(name=name, created_at=now)
        self._session.add(model)
        await self._session.flush()
        return Tenant(id=TenantId(model.id), name=model.name, created_at=model.created_at)


class UserRepositorySQLAlchemy(UserRepository):
    """SQLAlchemy implementation of user repository."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, user_id: UserId) -> User | None:
        stmt = select(UserModel).where(UserModel.id == int(user_id))
        result = await self._session.scalar(stmt)
        if result is None:
            return None
        return User(
            id=UserId(result.id),
            email=result.email,
            password_hash=result.password_hash,
            is_active=result.is_active,
            created_at=result.created_at,
        )

    async def get_by_email(self, email: str) -> User | None:
        stmt = select(UserModel).where(UserModel.email == email)
        result = await self._session.scalar(stmt)
        if result is None:
            return None
        return User(
            id=UserId(result.id),
            email=result.email,
            password_hash=result.password_hash,
            is_active=result.is_active,
            created_at=result.created_at,
        )

    async def create(self, email: str, password_hash: str) -> User:
        now = datetime.now(tz=UTC)
        model = UserModel(
            email=email,
            password_hash=password_hash,
            is_active=True,
            created_at=now,
        )
        self._session.add(model)
        await self._session.flush()
        return User(
            id=UserId(model.id),
            email=model.email,
            password_hash=model.password_hash,
            is_active=model.is_active,
            created_at=model.created_at,
        )


class MembershipRepositorySQLAlchemy(MembershipRepository):
    """SQLAlchemy implementation of membership repository."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_primary_membership(self, user_id: UserId) -> AuthenticatedUser | None:
        stmt = (
            select(MembershipModel, TenantModel, UserModel)
            .join(TenantModel, MembershipModel.tenant_id == TenantModel.id)
            .join(UserModel, MembershipModel.user_id == UserModel.id)
            .where(MembershipModel.user_id == int(user_id))
            .limit(1)
        )
        result = await self._session.execute(stmt)
        row = result.first()
        if row is None:
            return None
        membership_model, tenant_model, user_model = row
        tenant = Tenant(
            id=TenantId(tenant_model.id),
            name=tenant_model.name,
            created_at=tenant_model.created_at,
        )
        user = User(
            id=UserId(user_model.id),
            email=user_model.email,
            password_hash=user_model.password_hash,
            is_active=user_model.is_active,
            created_at=user_model.created_at,
        )
        membership = Membership(
            id=membership_model.id,
            tenant_id=TenantId(membership_model.tenant_id),
            user_id=UserId(membership_model.user_id),
            role=Role(membership_model.role),
        )
        _ = membership
        return AuthenticatedUser(user=user, tenant=tenant, role=Role(membership_model.role))

    async def add_membership(
        self,
        tenant: Tenant,
        user: User,
        role: str,
    ) -> AuthenticatedUser:
        model = MembershipModel(
            tenant_id=int(tenant.id),
            user_id=int(user.id),
            role=role,
        )
        self._session.add(model)
        await self._session.flush()
        return AuthenticatedUser(user=user, tenant=tenant, role=Role(role))

