from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import InvalidTokenError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from logs_sentinel.domains.identity.entities import (
    AuthenticatedUser,
    Role,
    Tenant,
    TenantId,
    User,
    UserId,
)
from logs_sentinel.infrastructure.auth.jwt import JWTEncoderImpl, create_jwt_encoder
from logs_sentinel.infrastructure.db.base import get_session
from logs_sentinel.infrastructure.db.models import MembershipModel, TenantModel, UserModel

security_scheme = HTTPBearer(auto_error=False)


@dataclass(slots=True)
class TenantContext:
    """Per-request tenant and user context."""

    tenant_id: TenantId
    user_id: UserId
    role: Role


async def get_jwt_encoder() -> JWTEncoderImpl:
    return create_jwt_encoder()


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security_scheme)],
    session: Annotated[AsyncSession, Depends(get_session)],
    jwt_encoder: Annotated[JWTEncoderImpl, Depends(get_jwt_encoder)],
) -> AuthenticatedUser:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "AUTH_MISSING_TOKEN"},
        )

    token = credentials.credentials
    try:
        payload = jwt_encoder.decode(token)
    except InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "AUTH_INVALID_TOKEN"},
        ) from None

    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "AUTH_INVALID_TOKEN_TYPE"},
        )

    user_id_raw = payload.get("sub")
    tenant_id_raw = payload.get("tenant_id")
    role_value = payload.get("role")
    if user_id_raw is None or tenant_id_raw is None or role_value is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "AUTH_INVALID_TOKEN"},
        )

    user_id = int(user_id_raw)
    tenant_id = int(tenant_id_raw)

    stmt = (
        select(UserModel, TenantModel, MembershipModel)
        .join(MembershipModel, MembershipModel.user_id == UserModel.id)
        .join(TenantModel, MembershipModel.tenant_id == TenantModel.id)
        .where(UserModel.id == user_id, TenantModel.id == tenant_id)
        .limit(1)
    )
    result = await session.execute(stmt)
    row = result.first()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "AUTH_SUBJECT_NOT_FOUND"},
        )

    user_model, tenant_model, membership_model = row
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
    role = Role(membership_model.role)

    return AuthenticatedUser(user=user, tenant=tenant, role=role)


async def get_tenant_context(
    auth_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> TenantContext:
    return TenantContext(
        tenant_id=auth_user.tenant.id,
        user_id=auth_user.user.id,
        role=auth_user.role,
    )
