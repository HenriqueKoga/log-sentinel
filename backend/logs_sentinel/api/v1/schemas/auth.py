from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field


class ErrorResponse(BaseModel):
    """Standard error payload with code and optional message."""

    code: str = Field(..., description="Stable error code for i18n.")
    message: str | None = Field(default=None, description="Human-readable message (optional).")


class SignUpRequest(BaseModel):
    tenant_name: str = Field(..., max_length=255)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)


class TokenPairResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str
