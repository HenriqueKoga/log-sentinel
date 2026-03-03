from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class SignUpInput:
    """Input for tenant sign-up."""

    tenant_name: str
    email: str
    password: str


@dataclass(slots=True)
class AuthTokens:
    """Access and refresh token pair."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


@dataclass(slots=True)
class LoginInput:
    """Input for login by email/password."""

    email: str
    password: str

