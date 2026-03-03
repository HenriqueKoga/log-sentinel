from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import jwt

from logs_sentinel.domains.identity.repositories import RefreshTokenStore
from logs_sentinel.infrastructure.settings.config import settings


class JWTEncoderImpl:
    """Concrete JWT encoder/decoder used by the auth service and dependencies."""

    def __init__(self, secret_key: str, algorithm: str) -> None:
        self._secret_key = secret_key
        self._algorithm = algorithm

    def encode(self, payload: dict[str, Any], expires_delta: timedelta) -> str:
        now = datetime.now(tz=timezone.utc)
        exp = now + expires_delta
        to_encode = {**payload, "exp": exp}
        return jwt.encode(to_encode, self._secret_key, algorithm=self._algorithm)

    def decode(self, token: str) -> dict[str, Any]:
        return jwt.decode(token, self._secret_key, algorithms=[self._algorithm])


class RedisRefreshTokenStore(RefreshTokenStore):
    """Refresh token store backed by Redis string keys."""

    def __init__(self, redis_client) -> None:
        self._redis = redis_client

    async def store_refresh_token(self, token_id: str, user_id: int, expires_at: int) -> None:
        ttl = expires_at - int(datetime.now(tz=timezone.utc).timestamp())
        if ttl <= 0:
            ttl = 1
        key = self._key(token_id)
        await self._redis.set(key, str(user_id), ex=ttl)

    async def is_refresh_token_active(self, token_id: str) -> bool:
        key = self._key(token_id)
        value = await self._redis.get(key)
        return value is not None

    async def revoke_refresh_token(self, token_id: str) -> None:
        key = self._key(token_id)
        await self._redis.delete(key)

    @staticmethod
    def _key(token_id: str) -> str:
        return f"refresh:{token_id}"


def create_jwt_encoder() -> JWTEncoderImpl:
    """Factory helper using global settings."""

    return JWTEncoderImpl(secret_key=settings.jwt_secret_key, algorithm=settings.jwt_algorithm)

