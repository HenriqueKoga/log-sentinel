"""Pytest configuration and shared fixtures."""

from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.pool import StaticPool

from logs_sentinel.infrastructure.db.models import create_all_tables

pytest_plugins = ["pytest_asyncio"]


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "asyncio: mark test as async (pytest-asyncio).")


def _check_aiosqlite() -> bool:
    try:
        import aiosqlite  # noqa: F401
        return True
    except ModuleNotFoundError:
        return False


HAS_AIOSQLITE = _check_aiosqlite()


@pytest.fixture
async def db_engine() -> AsyncGenerator[AsyncEngine]:
    """Shared in-memory SQLite engine for tests that use real DB (no fake repos)."""
    if not HAS_AIOSQLITE:
        pytest.skip("aiosqlite not installed")
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(create_all_tables)
    yield engine
    await engine.dispose()


@pytest.fixture
async def db_session(db_engine: AsyncEngine) -> AsyncGenerator[AsyncSession]:
    """Session bound to the test DB engine; commits are visible to other sessions."""
    async with AsyncSession(db_engine, expire_on_commit=False) as session:
        yield session
