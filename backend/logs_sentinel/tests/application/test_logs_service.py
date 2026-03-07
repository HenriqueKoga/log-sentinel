"""Tests for LogsService (list_logs, get_log_detail) with real DB and repos."""

from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from logs_sentinel.application.services.logs_service import LogsService
from logs_sentinel.infrastructure.db.repositories.ai_enrichment import (
    IssueEnrichmentLookupRepositorySQLAlchemy,
)
from logs_sentinel.infrastructure.db.repositories.logs import LogsRepositorySQLAlchemy
from logs_sentinel.tests.factories import (
    create_issue,
    create_issue_enrichment,
    create_log_event,
    create_project,
    create_tenant,
)


@pytest.fixture
async def logs_service_session(
    db_engine: AsyncEngine,
) -> AsyncGenerator[tuple[LogsService, AsyncSession, int, int, int]]:
    """Seed tenant, project, log events; yield (service, session, tenant_id, project_id, first_log_id)."""
    async with AsyncSession(db_engine, expire_on_commit=False) as session:
        tenant = create_tenant(session, name="Logs Tenant")
        await session.flush()
        project = create_project(session, tenant_id=tenant.id, name="API")
        await session.flush()
        log1 = create_log_event(
            session,
            tenant_id=tenant.id,
            project_id=project.id,
            message="ValueError: invalid",
            exception_type="ValueError",
            stacktrace="line 1",
            raw_json={"source": "api"},
        )
        create_log_event(
            session,
            tenant_id=tenant.id,
            project_id=project.id,
            level="info",
            message="Started",
            raw_json={},
        )
        await session.commit()
        tenant_id, project_id, log_id = tenant.id, project.id, log1.id

    async with AsyncSession(db_engine, expire_on_commit=False) as session:
        logs_repo = LogsRepositorySQLAlchemy(session)
        enrichment_repo = IssueEnrichmentLookupRepositorySQLAlchemy(session)
        service = LogsService(logs_repo=logs_repo, enrichment_lookup_repo=enrichment_repo)
        yield service, session, tenant_id, project_id, log_id


@pytest.mark.asyncio
async def test_list_logs_returns_items(
    logs_service_session: tuple[LogsService, AsyncSession, int, int, int],
) -> None:
    service, _, tenant_id, _, _ = logs_service_session
    result = await service.list_logs(
        tenant_id=tenant_id,
        project_id=None,
        level=None,
        q=None,
        from_dt=None,
        to_dt=None,
        page=1,
        page_size=50,
        without_issue=False,
    )
    assert result.total >= 2
    assert len(result.items) >= 2
    levels = {it.level for it in result.items}
    assert "error" in levels
    assert "info" in levels


@pytest.mark.asyncio
async def test_list_logs_without_issue_filters_existing_issues(
    db_engine: AsyncEngine,
) -> None:
    """When without_issue=True, logs that have an issue are excluded."""
    from logs_sentinel.domains.ingestion.normalization import compute_fingerprint, normalize_message

    async with AsyncSession(db_engine, expire_on_commit=False) as session:
        tenant = create_tenant(session, name="T")
        await session.flush()
        project = create_project(session, tenant_id=tenant.id, name="P")
        await session.flush()
        create_log_event(
            session,
            tenant_id=tenant.id,
            project_id=project.id,
            message="ValueError: x",
            exception_type="ValueError",
            stacktrace="line 1",
            raw_json={},
        )
        await session.commit()
        tenant_id, project_id = tenant.id, project.id

    norm = normalize_message("ValueError: x")
    fp = compute_fingerprint(norm, "ValueError", ["line 1"])

    async with AsyncSession(db_engine, expire_on_commit=False) as session:
        create_issue(
            session,
            tenant_id=tenant_id,
            project_id=project_id,
            fingerprint=fp,
            title="Error",
        )
        await session.flush()
        await session.commit()

    async with AsyncSession(db_engine, expire_on_commit=False) as session:
        logs_repo = LogsRepositorySQLAlchemy(session)
        enrichment_repo = IssueEnrichmentLookupRepositorySQLAlchemy(session)
        service = LogsService(logs_repo=logs_repo, enrichment_lookup_repo=enrichment_repo)
        result = await service.list_logs(
            tenant_id=tenant_id,
            project_id=project_id,
            level=None,
            q=None,
            from_dt=None,
            to_dt=None,
            page=1,
            page_size=50,
            without_issue=True,
        )
    assert result.total == 0
    assert len(result.items) == 0


@pytest.mark.asyncio
async def test_get_log_detail_returns_none_for_wrong_tenant(
    logs_service_session: tuple[LogsService, AsyncSession, int, int, int],
) -> None:
    service, _, _, _, log_id = logs_service_session
    wrong_tenant = 99999
    detail = await service.get_log_detail(log_id=log_id, tenant_id=wrong_tenant)
    assert detail is None


@pytest.mark.asyncio
async def test_get_log_detail_with_enrichment(db_engine: AsyncEngine) -> None:
    """get_log_detail returns related_issue and enrichment when issue + enrichment exist."""
    from logs_sentinel.domains.ingestion.normalization import compute_fingerprint, normalize_message

    async with AsyncSession(db_engine, expire_on_commit=False) as session:
        tenant = create_tenant(session, name="Detail Tenant")
        await session.flush()
        project = create_project(session, tenant_id=tenant.id, name="Backend")
        await session.flush()
        stacktrace = "  File 'a.py', line 1"
        log = create_log_event(
            session,
            tenant_id=tenant.id,
            project_id=project.id,
            message="TypeError: bad type",
            exception_type="TypeError",
            stacktrace=stacktrace,
            raw_json={"source": "worker"},
        )
        await session.flush()
        norm = normalize_message("TypeError: bad type")
        fp = compute_fingerprint(norm, "TypeError", stacktrace.splitlines())
        issue = create_issue(
            session,
            tenant_id=tenant.id,
            project_id=project.id,
            fingerprint=fp,
            title="TypeError in worker",
        )
        await session.flush()
        create_issue_enrichment(
            session,
            tenant_id=tenant.id,
            issue_id=issue.id,
            summary="AI summary",
            suspected_cause="Wrong type passed",
            checklist_json=["Check types"],
        )
        await session.commit()
        tenant_id, log_id = tenant.id, log.id

    async with AsyncSession(db_engine, expire_on_commit=False) as session:
        logs_repo = LogsRepositorySQLAlchemy(session)
        enrichment_repo = IssueEnrichmentLookupRepositorySQLAlchemy(session)
        service = LogsService(logs_repo=logs_repo, enrichment_lookup_repo=enrichment_repo)
        detail = await service.get_log_detail(log_id=log_id, tenant_id=tenant_id)
    assert detail is not None
    assert detail.message == "TypeError: bad type"
    assert detail.source == "worker"
    assert detail.related_issue is not None
    assert detail.related_issue.title == "TypeError in worker"
    assert detail.enrichment is not None
    assert detail.enrichment.summary == "AI summary"
    assert detail.enrichment.suspected_cause == "Wrong type passed"
    assert "Check types" in detail.enrichment.checklist
