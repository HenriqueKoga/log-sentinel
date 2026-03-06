from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Protocol

from .entities import AuthenticatedUser, Tenant, TenantId, User, UserId


class TenantRepository(Protocol):
    """Read/write access to tenants."""

    async def get_by_id(self, tenant_id: TenantId) -> Tenant | None: ...

    async def get_by_name(self, name: str) -> Tenant | None: ...

    async def create(self, name: str) -> Tenant: ...


class UserRepository(Protocol):
    """Read/write access to users."""

    async def get_by_id(self, user_id: UserId) -> User | None: ...

    async def get_by_email(self, email: str) -> User | None: ...

    async def create(self, email: str, password_hash: str) -> User: ...


class MembershipRepository(Protocol):
    """Access memberships to connect users and tenants."""

    async def get_primary_membership(self, user_id: UserId) -> AuthenticatedUser | None: ...

    async def add_membership(
        self,
        tenant: Tenant,
        user: User,
        role: str,
    ) -> AuthenticatedUser: ...


class RefreshTokenStore(ABC):
    """Abstract store for refresh token rotation and revocation."""

    @abstractmethod
    async def store_refresh_token(self, token_id: str, user_id: int, expires_at: int) -> None: ...

    @abstractmethod
    async def is_refresh_token_active(self, token_id: str) -> bool: ...

    @abstractmethod
    async def revoke_refresh_token(self, token_id: str) -> None: ...
