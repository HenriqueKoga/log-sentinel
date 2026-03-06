from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any, TypeVar, cast

import jwt
import redis.exceptions as redis_exceptions

from logs_sentinel.domains.identity.repositories import RefreshTokenStore
from logs_sentinel.infrastructure.settings.config import settings

T = TypeVar("T")
RETRY_EXCEPTIONS = (redis_exceptions.ConnectionError, OSError, ConnectionError)
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 0.2


async def _retry_redis(coro: Any) -> T:
    """Retry a Redis operation on connection errors (e.g. reset by peer via Docker)."""
    last: BaseException | None = None
    for attempt in range(MAX_RETRIES):
        try:
            return cast(T, await coro())
        except RETRY_EXCEPTIONS as e:
            last = e
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(RETRY_DELAY_SECONDS * (attempt + 1))
    if last is not None:
        raise last
    raise RuntimeError("_retry_redis: no exception captured")


class JWTEncoderImpl:
    """Concrete JWT encoder/decoder used by the auth service and dependencies."""

    def __init__(self, secret_key: str, algorithm: str) -> None:
        self._secret_key = secret_key
        self._algorithm = algorithm

    def encode(self, payload: dict[str, Any], expires_delta: timedelta) -> str:
        now = datetime.now(tz=UTC)
        exp = now + expires_delta
        to_encode = {**payload, "exp": exp}
        return jwt.encode(to_encode, self._secret_key, algorithm=self._algorithm)

    def decode(self, token: str) -> dict[str, Any]:
        return jwt.decode(token, self._secret_key, algorithms=[self._algorithm])


class RedisRefreshTokenStore(RefreshTokenStore):
    """Refresh token store backed by Redis string keys."""

    def __init__(self, redis_client: Any) -> None:
        self._redis = redis_client

    async def store_refresh_token(self, token_id: str, user_id: int, expires_at: int) -> None:
        ttl = expires_at - int(datetime.now(tz=UTC).timestamp())
        if ttl <= 0:
            ttl = 1
        key = self._key(token_id)

        async def _set() -> None:
            await self._redis.set(key, str(user_id), ex=ttl)

        await _retry_redis(_set)

    async def is_refresh_token_active(self, token_id: str) -> bool:
        key = self._key(token_id)

        async def _get() -> bool:
            value = await self._redis.get(key)
            return value is not None

        return await _retry_redis(_get)

    async def revoke_refresh_token(self, token_id: str) -> None:
        key = self._key(token_id)

        async def _delete() -> None:
            await self._redis.delete(key)

        await _retry_redis(_delete)

    @staticmethod
    def _key(token_id: str) -> str:
        return f"refresh:{token_id}"


def create_jwt_encoder() -> JWTEncoderImpl:
    """Factory helper using global settings."""

    return JWTEncoderImpl(secret_key=settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
