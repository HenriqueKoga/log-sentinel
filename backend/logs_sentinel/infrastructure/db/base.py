from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from logs_sentinel.infrastructure.settings.config import settings


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models."""


def _create_engine() -> AsyncEngine:
    return create_async_engine(
        settings.db_url,
        echo=False,
        pool_pre_ping=True,
    )


engine: AsyncEngine = _create_engine()
SessionFactory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency that yields an async database session."""

    async with SessionFactory() as session:
        async with session.begin():
            yield session
