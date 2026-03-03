from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from logs_sentinel.application.dto.auth import LoginInput, SignUpInput
from logs_sentinel.application.services.auth_service import AuthService
from logs_sentinel.domains.identity.entities import (
    AuthenticatedUser,
    Role,
    Tenant,
    TenantId,
    User,
    UserId,
)
from logs_sentinel.domains.identity.repositories import (
    MembershipRepository,
    RefreshTokenStore,
    TenantRepository,
    UserRepository,
)


class InMemoryTenantRepo(TenantRepository):
    def __init__(self) -> None:
        self._tenants: dict[int, Tenant] = {}
        self._next_id = 1

    async def get_by_id(self, tenant_id: TenantId):
        return self._tenants.get(int(tenant_id))

    async def get_by_name(self, name: str):
        return next((t for t in self._tenants.values() if t.name == name), None)

    async def create(self, name: str):
        tid = self._next_id
        self._next_id += 1
        t = Tenant(
            id=TenantId(tid),
            name=name,
            created_at=datetime.now(tz=timezone.utc),
        )
        self._tenants[tid] = t
        return t


class InMemoryUserRepo(UserRepository):
    def __init__(self) -> None:
        self._users: dict[int, User] = {}
        self._by_email: dict[str, int] = {}
        self._next_id = 1

    async def get_by_id(self, user_id: UserId):
        return self._users.get(int(user_id))

    async def get_by_email(self, email: str):
        uid = self._by_email.get(email)
        return self._users.get(uid) if uid is not None else None

    async def create(self, email: str, password_hash: str):
        uid = self._next_id
        self._next_id += 1
        user = User(
            id=UserId(uid),
            email=email,
            password_hash=password_hash,
            is_active=True,
            created_at=datetime.now(tz=timezone.utc),
        )
        self._users[uid] = user
        self._by_email[email] = uid
        return user


class InMemoryMembershipRepo(MembershipRepository):
    def __init__(self) -> None:
        self._primary: dict[int, AuthenticatedUser] = {}

    async def get_primary_membership(self, user_id: UserId):
        return self._primary.get(int(user_id))

    async def add_membership(self, tenant: Tenant, user: User, role: str):
        auth = AuthenticatedUser(user=user, tenant=tenant, role=Role(role))
        self._primary[int(user.id)] = auth
        return auth


class InMemoryRefreshStore(RefreshTokenStore):
    def __init__(self) -> None:
        self._active: set[str] = set()

    async def store_refresh_token(self, token_id: str, user_id: int, expires_at: int) -> None:
        self._active.add(token_id)

    async def is_refresh_token_active(self, token_id: str) -> bool:
        return token_id in self._active

    async def revoke_refresh_token(self, token_id: str) -> None:
        self._active.discard(token_id)


class DummyJWTEncoder:
    def encode(self, payload, expires_delta: timedelta) -> str:  # type: ignore[override]
        return f"jwt-{payload['type']}-{payload['sub']}"


@pytest.mark.asyncio
async def test_signup_and_login_issue_tokens() -> None:
    tenants = InMemoryTenantRepo()
    users = InMemoryUserRepo()
    memberships = InMemoryMembershipRepo()
    refresh_store = InMemoryRefreshStore()
    jwt_encoder = DummyJWTEncoder()
    service = AuthService(
        tenant_repo=tenants,
        user_repo=users,
        membership_repo=memberships,
        refresh_store=refresh_store,
        jwt_encoder=jwt_encoder,
    )

    signup_input = SignUpInput(tenant_name="Acme Logs", email="owner@example.com", password="secret123")
    tokens = await service.sign_up(signup_input)
    assert tokens.access_token.startswith("jwt-access-")
    assert tokens.refresh_token.startswith("jwt-refresh-")

    login_input = LoginInput(email="owner@example.com", password="secret123")
    tokens2 = await service.login(login_input)
    assert tokens2.access_token.startswith("jwt-access-")

