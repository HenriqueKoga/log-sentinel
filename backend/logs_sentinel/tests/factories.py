"""Factories for building test data in the real DB (no fake repositories)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from logs_sentinel.infrastructure.db.models import (
    IssueEnrichmentModel,
    IssueModel,
    LogEventModel,
    MembershipModel,
    ProjectModel,
    TenantModel,
    UserModel,
)


def create_tenant(
    session: AsyncSession,
    *,
    name: str = "Test Tenant",
    created_at: datetime | None = None,
) -> TenantModel:
    now = created_at or datetime.now(UTC)
    tenant = TenantModel(name=name, created_at=now)
    session.add(tenant)
    return tenant


def create_user(
    session: AsyncSession,
    *,
    email: str = "user@test.example",
    password_hash: str = "hash",
    is_active: bool = True,
    created_at: datetime | None = None,
) -> UserModel:
    now = created_at or datetime.now(UTC)
    user = UserModel(
        email=email,
        password_hash=password_hash,
        is_active=is_active,
        created_at=now,
    )
    session.add(user)
    return user


def create_membership(
    session: AsyncSession,
    *,
    tenant_id: int,
    user_id: int,
    role: str = "owner",
) -> MembershipModel:
    m = MembershipModel(tenant_id=tenant_id, user_id=user_id, role=role)
    session.add(m)
    return m


def create_project(
    session: AsyncSession,
    *,
    tenant_id: int,
    name: str = "Test Project",
    created_at: datetime | None = None,
) -> ProjectModel:
    now = created_at or datetime.now(UTC)
    project = ProjectModel(tenant_id=tenant_id, name=name, created_at=now)
    session.add(project)
    return project


def create_log_event(
    session: AsyncSession,
    *,
    tenant_id: int,
    project_id: int,
    level: str = "error",
    message: str = "Error message",
    exception_type: str | None = None,
    stacktrace: str | None = None,
    received_at: datetime | None = None,
    raw_json: dict[str, Any] | None = None,
) -> LogEventModel:
    now = received_at or datetime.now(UTC)
    raw = raw_json if raw_json is not None else {}
    log = LogEventModel(
        tenant_id=tenant_id,
        project_id=project_id,
        received_at=now,
        level=level,
        message=message,
        exception_type=exception_type,
        stacktrace=stacktrace,
        raw_json=raw,
    )
    session.add(log)
    return log


def create_issue(
    session: AsyncSession,
    *,
    tenant_id: int,
    project_id: int,
    fingerprint: str = "fp-default",
    title: str = "Issue",
    severity: str = "high",
    status: str = "open",
    first_seen: datetime | None = None,
    last_seen: datetime | None = None,
    total_count: int = 1,
    priority_score: float = 0.0,
) -> IssueModel:
    now = first_seen or datetime.now(UTC)
    last = last_seen or now
    issue = IssueModel(
        tenant_id=tenant_id,
        project_id=project_id,
        fingerprint=fingerprint,
        title=title,
        severity=severity,
        status=status,
        first_seen=now,
        last_seen=last,
        total_count=total_count,
        priority_score=priority_score,
    )
    session.add(issue)
    return issue


def create_issue_enrichment(
    session: AsyncSession,
    *,
    tenant_id: int,
    issue_id: int,
    model_name: str = "test-model",
    summary: str = "Summary",
    suspected_cause: str = "Cause",
    checklist_json: list[str] | None = None,
    created_at: datetime | None = None,
) -> IssueEnrichmentModel:
    now = created_at or datetime.now(UTC)
    checklist = checklist_json if checklist_json is not None else []
    enrich = IssueEnrichmentModel(
        tenant_id=tenant_id,
        issue_id=issue_id,
        model_name=model_name,
        summary=summary,
        suspected_cause=suspected_cause,
        checklist_json=checklist,
        created_at=now,
    )
    session.add(enrich)
    return enrich
