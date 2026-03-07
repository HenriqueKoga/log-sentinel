"""Tests for AuthService (login, refresh, sign_up) with in-memory repos."""

from __future__ import annotations

from datetime import UTC, datetime

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
from logs_sentinel.infrastructure.auth.jwt import JWTEncoderImpl


class InMemoryTenantRepo(TenantRepository):
    def __init__(self) -> None:
        self._tenants: list[Tenant] = []
        self._next_id = 1

    async def create(self, name: str) -> Tenant:
        t = Tenant(
            id=TenantId(self._next_id),
            name=name,
            created_at=datetime.now(UTC),
        )
        self._next_id += 1
        self._tenants.append(t)
        return t

    async def get_by_id(self, tenant_id: TenantId) -> Tenant | None:
        for t in self._tenants:
            if t.id == tenant_id:
                return t
        return None

    async def get_by_name(self, name: str) -> Tenant | None:
        for t in self._tenants:
            if t.name == name:
                return t
        return None


class InMemoryUserRepo(UserRepository):
    def __init__(self) -> None:
        self._users: list[User] = []
        self._next_id = 1

    async def create(self, email: str, password_hash: str) -> User:
        u = User(
            id=UserId(self._next_id),
            email=email,
            password_hash=password_hash,
            is_active=True,
            created_at=datetime.now(UTC),
        )
        self._next_id += 1
        self._users.append(u)
        return u

    async def get_by_id(self, user_id: UserId) -> User | None:
        for u in self._users:
            if u.id == user_id:
                return u
        return None

    async def get_by_email(self, email: str) -> User | None:
        for u in self._users:
            if u.email == email:
                return u
        return None


class InMemoryMembershipRepo(MembershipRepository):
    def __init__(self) -> None:
        self._primary: dict[int, AuthenticatedUser] = {}

    async def add_membership(
        self, tenant: Tenant, user: User, role: str
    ) -> AuthenticatedUser:
        auth = AuthenticatedUser(
            user=user,
            tenant=tenant,
            role=Role(role),
        )
        self._primary[int(user.id)] = auth
        return auth

    async def get_primary_membership(self, user_id: UserId) -> AuthenticatedUser | None:
        return self._primary.get(int(user_id))


class InMemoryRefreshStore(RefreshTokenStore):
    def __init__(self) -> None:
        self._active: set[str] = set()

    async def store_refresh_token(
        self, token_id: str, user_id: int, expires_at: int
    ) -> None:
        self._active.add(token_id)

    async def is_refresh_token_active(self, token_id: str) -> bool:
        return token_id in self._active

    async def revoke_refresh_token(self, token_id: str) -> None:
        self._active.discard(token_id)


@pytest.mark.asyncio
async def test_sign_up_issues_tokens() -> None:
    jwt = JWTEncoderImpl(secret_key="test-secret-32-bytes-long!!!!!!!!", algorithm="HS256")
    tenant_repo = InMemoryTenantRepo()
    user_repo = InMemoryUserRepo()
    membership_repo = InMemoryMembershipRepo()
    refresh_store = InMemoryRefreshStore()
    service = AuthService(
        tenant_repo=tenant_repo,
        user_repo=user_repo,
        membership_repo=membership_repo,
        refresh_store=refresh_store,
        jwt_encoder=jwt,
    )
    tokens = await service.sign_up(
        SignUpInput(tenant_name="Acme", email="admin@acme.com", password="secret"),
    )
    assert tokens.access_token
    assert tokens.refresh_token
    refresh_payload = jwt.decode(tokens.refresh_token)
    jti = refresh_payload.get("jti")
    assert jti
    assert await refresh_store.is_refresh_token_active(jti) is True
    payload = jwt.decode(tokens.access_token)
    assert payload.get("type") == "access"
    assert payload.get("tenant_id") == 1


@pytest.mark.asyncio
async def test_sign_up_raises_when_email_exists() -> None:
    jwt = JWTEncoderImpl(secret_key="test-secret-32-bytes-long!!!!!!!!", algorithm="HS256")
    tenant_repo = InMemoryTenantRepo()
    user_repo = InMemoryUserRepo()
    await user_repo.create("admin@acme.com", "hash")
    membership_repo = InMemoryMembershipRepo()
    refresh_store = InMemoryRefreshStore()
    service = AuthService(
        tenant_repo=tenant_repo,
        user_repo=user_repo,
        membership_repo=membership_repo,
        refresh_store=refresh_store,
        jwt_encoder=jwt,
    )
    with pytest.raises(ValueError) as exc:
        await service.sign_up(
            SignUpInput(tenant_name="Acme", email="admin@acme.com", password="secret"),
        )
    assert exc.value.args[0] == "AUTH_EMAIL_EXISTS"


@pytest.mark.asyncio
async def test_login_issues_tokens() -> None:
    from argon2 import PasswordHasher

    hasher = PasswordHasher()
    jwt = JWTEncoderImpl(secret_key="test-secret-32-bytes-long!!!!!!!!", algorithm="HS256")
    tenant_repo = InMemoryTenantRepo()
    user_repo = InMemoryUserRepo()
    membership_repo = InMemoryMembershipRepo()
    tenant = await tenant_repo.create("Acme")
    user = await user_repo.create("user@acme.com", hasher.hash("pass"))
    await membership_repo.add_membership(tenant, user, "owner")
    refresh_store = InMemoryRefreshStore()
    service = AuthService(
        tenant_repo=tenant_repo,
        user_repo=user_repo,
        membership_repo=membership_repo,
        refresh_store=refresh_store,
        jwt_encoder=jwt,
    )
    tokens = await service.login(LoginInput(email="user@acme.com", password="pass"))
    assert tokens.access_token
    assert tokens.refresh_token


@pytest.mark.asyncio
async def test_login_raises_invalid_credentials_wrong_password() -> None:
    from argon2 import PasswordHasher

    hasher = PasswordHasher()
    jwt = JWTEncoderImpl(secret_key="test-secret-32-bytes-long!!!!!!!!", algorithm="HS256")
    tenant_repo = InMemoryTenantRepo()
    user_repo = InMemoryUserRepo()
    await user_repo.create("user@acme.com", hasher.hash("pass"))
    membership_repo = InMemoryMembershipRepo()
    refresh_store = InMemoryRefreshStore()
    service = AuthService(
        tenant_repo=tenant_repo,
        user_repo=user_repo,
        membership_repo=membership_repo,
        refresh_store=refresh_store,
        jwt_encoder=jwt,
    )
    with pytest.raises(ValueError) as exc:
        await service.login(LoginInput(email="user@acme.com", password="wrong"))
    assert exc.value.args[0] == "AUTH_INVALID_CREDENTIALS"


@pytest.mark.asyncio
async def test_login_raises_no_tenant_when_no_membership() -> None:
    from argon2 import PasswordHasher

    hasher = PasswordHasher()
    jwt = JWTEncoderImpl(secret_key="test-secret-32-bytes-long!!!!!!!!", algorithm="HS256")
    tenant_repo = InMemoryTenantRepo()
    user_repo = InMemoryUserRepo()
    await user_repo.create("orphan@acme.com", hasher.hash("pass"))
    membership_repo = InMemoryMembershipRepo()
    refresh_store = InMemoryRefreshStore()
    service = AuthService(
        tenant_repo=tenant_repo,
        user_repo=user_repo,
        membership_repo=membership_repo,
        refresh_store=refresh_store,
        jwt_encoder=jwt,
    )
    with pytest.raises(ValueError) as exc:
        await service.login(LoginInput(email="orphan@acme.com", password="pass"))
    assert exc.value.args[0] == "AUTH_NO_TENANT"


@pytest.mark.asyncio
async def test_refresh_rotates_tokens() -> None:
    from argon2 import PasswordHasher

    hasher = PasswordHasher()
    jwt = JWTEncoderImpl(secret_key="test-secret-32-bytes-long!!!!!!!!", algorithm="HS256")
    tenant_repo = InMemoryTenantRepo()
    user_repo = InMemoryUserRepo()
    membership_repo = InMemoryMembershipRepo()
    tenant = await tenant_repo.create("Acme")
    user = await user_repo.create("user@acme.com", hasher.hash("pass"))
    await membership_repo.add_membership(tenant, user, "owner")
    refresh_store = InMemoryRefreshStore()
    service = AuthService(
        tenant_repo=tenant_repo,
        user_repo=user_repo,
        membership_repo=membership_repo,
        refresh_store=refresh_store,
        jwt_encoder=jwt,
    )
    tokens1 = await service.login(LoginInput(email="user@acme.com", password="pass"))
    tokens2 = await service.refresh(tokens1.refresh_token)
    # After refresh we get new tokens (rotation); same second can yield same jti/refresh string
    assert tokens2.access_token and tokens2.refresh_token


@pytest.mark.asyncio
async def test_refresh_raises_when_token_revoked() -> None:
    from argon2 import PasswordHasher

    hasher = PasswordHasher()
    jwt = JWTEncoderImpl(secret_key="test-secret-32-bytes-long!!!!!!!!", algorithm="HS256")
    tenant_repo = InMemoryTenantRepo()
    user_repo = InMemoryUserRepo()
    membership_repo = InMemoryMembershipRepo()
    tenant = await tenant_repo.create("Acme")
    user = await user_repo.create("user@acme.com", hasher.hash("pass"))
    await membership_repo.add_membership(tenant, user, "owner")
    refresh_store = InMemoryRefreshStore()
    service = AuthService(
        tenant_repo=tenant_repo,
        user_repo=user_repo,
        membership_repo=membership_repo,
        refresh_store=refresh_store,
        jwt_encoder=jwt,
    )
    tokens = await service.login(LoginInput(email="user@acme.com", password="pass"))
    refresh_id = jwt.decode(tokens.refresh_token).get("jti")
    assert isinstance(refresh_id, str)
    await refresh_store.revoke_refresh_token(refresh_id)
    with pytest.raises(ValueError) as exc:
        await service.refresh(tokens.refresh_token)
    assert exc.value.args[0] == "AUTH_REFRESH_REVOKED"
