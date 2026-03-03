from __future__ import annotations

from typing import Annotated

from argon2 import PasswordHasher
from fastapi import APIRouter, Depends, HTTPException, Response, status

from logs_sentinel.api.v1.schemas.auth import (
    ErrorResponse,
    LoginRequest,
    RefreshRequest,
    SignUpRequest,
    TokenPairResponse,
)
from logs_sentinel.application.dto.auth import AuthTokens, LoginInput, SignUpInput
from logs_sentinel.application.services.auth_service import AuthService
from logs_sentinel.domains.identity.repositories import (
    MembershipRepository,
    RefreshTokenStore,
    TenantRepository,
    UserRepository,
)
from logs_sentinel.infrastructure.auth.jwt import JWTEncoderImpl, create_jwt_encoder
from logs_sentinel.infrastructure.cache.redis_rate_limiter import create_redis_client
from logs_sentinel.infrastructure.db.base import get_session
from logs_sentinel.infrastructure.db.repositories.identity import (
    MembershipRepositorySQLAlchemy,
    TenantRepositorySQLAlchemy,
    UserRepositorySQLAlchemy,
)
from logs_sentinel.infrastructure.settings.config import settings
from sqlalchemy.ext.asyncio import AsyncSession


router = APIRouter(prefix="/auth", tags=["auth"])


def _build_auth_service(
    session: AsyncSession,
    jwt_encoder: JWTEncoderImpl,
    refresh_store: RefreshTokenStore,
) -> AuthService:
    tenant_repo: TenantRepository = TenantRepositorySQLAlchemy(session)
    user_repo: UserRepository = UserRepositorySQLAlchemy(session)
    membership_repo: MembershipRepository = MembershipRepositorySQLAlchemy(session)
    return AuthService(
        tenant_repo=tenant_repo,
        user_repo=user_repo,
        membership_repo=membership_repo,
        refresh_store=refresh_store,
        jwt_encoder=jwt_encoder,
        password_hasher=PasswordHasher(),
    )


async def get_auth_service(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AuthService:
    jwt_encoder = create_jwt_encoder()
    redis_client = create_redis_client(settings.redis_url)
    from logs_sentinel.infrastructure.auth.jwt import RedisRefreshTokenStore

    refresh_store: RefreshTokenStore = RedisRefreshTokenStore(redis_client)
    return _build_auth_service(session=session, jwt_encoder=jwt_encoder, refresh_store=refresh_store)


@router.post(
    "/signup",
    response_model=TokenPairResponse,
    responses={400: {"model": ErrorResponse}},
)
async def sign_up(
    payload: SignUpRequest,
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> TokenPairResponse:
    try:
        tokens: AuthTokens = await service.sign_up(
            SignUpInput(
                tenant_name=payload.tenant_name,
                email=payload.email,
                password=payload.password,
            )
        )
    except ValueError as exc:
        if str(exc) == "AUTH_EMAIL_EXISTS":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "AUTH_EMAIL_EXISTS"},
            ) from None
        raise
    return TokenPairResponse(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        token_type=tokens.token_type,
    )


@router.post(
    "/login",
    response_model=TokenPairResponse,
    responses={400: {"model": ErrorResponse}},
)
async def login(
    payload: LoginRequest,
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> TokenPairResponse:
    try:
        tokens = await service.login(LoginInput(email=payload.email, password=payload.password))
    except ValueError as exc:
        if str(exc) == "AUTH_INVALID_CREDENTIALS":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "AUTH_INVALID_CREDENTIALS"},
            ) from None
        raise
    return TokenPairResponse(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        token_type=tokens.token_type,
    )


@router.post(
    "/refresh",
    response_model=TokenPairResponse,
    responses={400: {"model": ErrorResponse}},
)
async def refresh(
    payload: RefreshRequest,
    response: Response,
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> TokenPairResponse:
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail={"code": "AUTH_REFRESH_NOT_IMPLEMENTED"},
    )


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def logout() -> None:
    return None

