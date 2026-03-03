from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Protocol

from argon2 import PasswordHasher

from logs_sentinel.application.dto.auth import AuthTokens, LoginInput, SignUpInput
from logs_sentinel.domains.identity.entities import AuthenticatedUser, Role, Tenant, User
from logs_sentinel.domains.identity.repositories import (
    MembershipRepository,
    RefreshTokenStore,
    TenantRepository,
    UserRepository,
)
from logs_sentinel.infrastructure.settings.config import settings


class JWTEncoder(Protocol):
    """Abstraction for JWT encode/decode operations."""

    def encode(self, payload: dict[str, object], expires_delta: timedelta) -> str:
        ...


class AuthService:
    """Application service handling signup, login, and token rotation."""

    def __init__(
        self,
        tenant_repo: TenantRepository,
        user_repo: UserRepository,
        membership_repo: MembershipRepository,
        refresh_store: RefreshTokenStore,
        jwt_encoder: JWTEncoder,
        password_hasher: PasswordHasher | None = None,
    ) -> None:
        self._tenant_repo = tenant_repo
        self._user_repo = user_repo
        self._membership_repo = membership_repo
        self._refresh_store = refresh_store
        self._jwt = jwt_encoder
        self._hasher = password_hasher or PasswordHasher()

    async def sign_up(self, data: SignUpInput) -> AuthTokens:
        """Create tenant, first user, and membership, returning tokens."""

        existing = await self._user_repo.get_by_email(data.email)
        if existing:
            raise ValueError("AUTH_EMAIL_EXISTS")

        tenant: Tenant = await self._tenant_repo.create(name=data.tenant_name)
        password_hash = self._hasher.hash(data.password)
        user: User = await self._user_repo.create(email=data.email, password_hash=password_hash)
        auth_user: AuthenticatedUser = await self._membership_repo.add_membership(
            tenant=tenant,
            user=user,
            role=Role.OWNER.value,
        )
        return await self._issue_tokens(auth_user)

    async def login(self, data: LoginInput) -> AuthTokens:
        """Login an existing user and issue tokens."""

        user = await self._user_repo.get_by_email(data.email)
        if not user:
            raise ValueError("AUTH_INVALID_CREDENTIALS")

        try:
            self._hasher.verify(user.password_hash, data.password)
        except Exception:
            raise ValueError("AUTH_INVALID_CREDENTIALS") from None

        auth_user = await self._membership_repo.get_primary_membership(user.id)
        if not auth_user:
            raise ValueError("AUTH_NO_TENANT")

        return await self._issue_tokens(auth_user)

    async def refresh_tokens(self, refresh_token_id: str, user: AuthenticatedUser) -> AuthTokens:
        """Rotate refresh token if still active."""

        is_active = await self._refresh_store.is_refresh_token_active(refresh_token_id)
        if not is_active:
            raise ValueError("AUTH_REFRESH_REVOKED")

        await self._refresh_store.revoke_refresh_token(refresh_token_id)
        return await self._issue_tokens(user)

    async def logout(self, refresh_token_id: str) -> None:
        """Revoke a refresh token."""

        await self._refresh_store.revoke_refresh_token(refresh_token_id)

    async def _issue_tokens(self, auth_user: AuthenticatedUser) -> AuthTokens:
        now = datetime.now(tz=UTC)
        access_exp = timedelta(minutes=settings.access_token_exp_minutes)
        refresh_exp = timedelta(days=settings.refresh_token_exp_days)

        access_payload = {
            "sub": str(auth_user.user.id),
            "tenant_id": int(auth_user.tenant.id),
            "role": auth_user.role.value,
            "type": "access",
            "iat": int(now.timestamp()),
        }
        refresh_id = f"rt_{auth_user.user.id}_{int(now.timestamp())}"
        refresh_payload = {
            "sub": str(auth_user.user.id),
            "tenant_id": int(auth_user.tenant.id),
            "role": auth_user.role.value,
            "type": "refresh",
            "jti": refresh_id,
            "iat": int(now.timestamp()),
        }

        access_token = self._jwt.encode(access_payload, expires_delta=access_exp)
        refresh_token = self._jwt.encode(refresh_payload, expires_delta=refresh_exp)

        expires_at = int((now + refresh_exp).timestamp())
        await self._refresh_store.store_refresh_token(
            token_id=refresh_id,
            user_id=int(auth_user.user.id),
            expires_at=expires_at,
        )

        return AuthTokens(access_token=access_token, refresh_token=refresh_token)

