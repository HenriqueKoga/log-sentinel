"""Tests for Celery ingest task (process_ingest_batch) with real DB."""

from __future__ import annotations

import threading
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import Any
from unittest.mock import patch

import pytest
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from logs_sentinel.infrastructure.db.models import create_all_tables
from logs_sentinel.tests.factories import create_project, create_tenant


def _create_ingest_engine() -> AsyncEngine:
    try:
        import aiosqlite  # noqa: F401
    except ModuleNotFoundError:
        pytest.skip("aiosqlite not installed")
    return create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )


@pytest.fixture
async def ingest_db_engine() -> AsyncGenerator[AsyncEngine]:
    """In-memory SQLite engine for worker test."""
    engine = _create_ingest_engine()
    async with engine.begin() as conn:
        await conn.run_sync(create_all_tables)
    yield engine
    await engine.dispose()


@pytest.fixture
async def seeded_tenant_project(
    ingest_db_engine: AsyncEngine,
) -> AsyncGenerator[tuple[AsyncEngine, int, int, Any]]:
    """Create tenant and project; return (engine, tenant_id, project_id, session_factory)."""
    session_factory = async_sessionmaker(
        bind=ingest_db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with session_factory() as session:
        tenant = create_tenant(session, name="Worker Tenant")
        await session.flush()
        project = create_project(session, tenant_id=tenant.id, name="API")
        await session.commit()
        tenant_id, project_id = tenant.id, project.id
    yield ingest_db_engine, tenant_id, project_id, session_factory


@pytest.mark.asyncio
async def test_process_ingest_batch_runs_with_real_session(
    seeded_tenant_project: tuple[AsyncEngine, int, int, Any],
) -> None:
    """Run process_ingest_batch in a thread (task uses asyncio.run) with patched SessionFactory."""
    from logs_sentinel.workers.tasks.ingest import process_ingest_batch

    _engine, tenant_id, project_id, session_factory = seeded_tenant_project
    now = datetime.now(UTC).isoformat()
    payload = {
        "events": [
            {
                "tenant_id": tenant_id,
                "project_id": project_id,
                "message": "Test error",
                "received_at": now,
                "level": "error",
            }
        ]
    }
    result: list[Exception] = []

    def run_task() -> None:
        try:
            with patch("logs_sentinel.workers.tasks.ingest.SessionFactory", session_factory):
                process_ingest_batch(payload)
        except Exception as e:
            result.append(e)

    thread = threading.Thread(target=run_task)
    thread.start()
    thread.join()
    if result:
        raise result[0]