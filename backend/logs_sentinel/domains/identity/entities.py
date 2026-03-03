from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import NewType

TenantId = NewType("TenantId", int)
UserId = NewType("UserId", int)
MembershipId = NewType("MembershipId", int)


class Role(StrEnum):
    """RBAC roles within a tenant."""

    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"


@dataclass(slots=True)
class Tenant:
    """Represents an organization / tenant."""

    id: TenantId
    name: str
    created_at: datetime


@dataclass(slots=True)
class User:
    """Represents a user that can belong to one or more tenants."""

    id: UserId
    email: str
    password_hash: str
    is_active: bool
    created_at: datetime


@dataclass(slots=True)
class Membership:
    """Associates a user with a tenant and role."""

    id: MembershipId
    tenant_id: TenantId
    user_id: UserId
    role: Role


@dataclass(slots=True)
class AuthenticatedUser:
    """Value object representing an authenticated principal with tenant context."""

    user: User
    tenant: Tenant
    role: Role

