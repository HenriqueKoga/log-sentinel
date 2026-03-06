"""SQLAlchemy implementation of chat session and message repositories."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from logs_sentinel.domains.chat.entities import ChatMessage, ChatSession
from logs_sentinel.domains.chat.repositories import (
    ChatMessageRepository,
    ChatSessionRepository,
)
from logs_sentinel.infrastructure.db.models import ChatMessageModel, ChatSessionModel


class ChatSessionRepositorySQLAlchemy(ChatSessionRepository):
    """SQLAlchemy implementation of ChatSessionRepository."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        tenant_id: int,
        user_id: int,
        project_id: int | None,
        title: str = "",
    ) -> ChatSession:
        now = datetime.now(UTC)
        model = ChatSessionModel(
            tenant_id=tenant_id,
            user_id=user_id,
            project_id=project_id,
            title=title or "",
            created_at=now,
        )
        self._session.add(model)
        await self._session.flush()
        return ChatSession(
            id=model.id,
            tenant_id=model.tenant_id,
            user_id=model.user_id,
            project_id=model.project_id,
            title=model.title,
            created_at=model.created_at,
        )

    async def list_sessions(
        self,
        *,
        tenant_id: int,
        user_id: int,
        project_id: int | None,
        limit: int = 50,
    ) -> Sequence[ChatSession]:
        last_msg = (
            select(
                ChatMessageModel.session_id,
                func.max(ChatMessageModel.created_at).label("last_at"),
            )
            .group_by(ChatMessageModel.session_id)
            .subquery()
        )
        stmt = (
            select(ChatSessionModel)
            .outerjoin(last_msg, ChatSessionModel.id == last_msg.c.session_id)
            .where(
                ChatSessionModel.tenant_id == tenant_id,
                ChatSessionModel.user_id == user_id,
            )
        )
        if project_id is not None:
            stmt = stmt.where(ChatSessionModel.project_id == project_id)
        stmt = stmt.order_by(
            func.coalesce(last_msg.c.last_at, ChatSessionModel.created_at).desc()
        ).limit(limit)
        result = await self._session.execute(stmt)
        rows = result.scalars().all()
        return [
            ChatSession(
                id=m.id,
                tenant_id=m.tenant_id,
                user_id=m.user_id,
                project_id=m.project_id,
                title=m.title,
                created_at=m.created_at,
            )
            for m in rows
        ]

    async def get_by_id(
        self, session_id: int, tenant_id: int, user_id: int
    ) -> ChatSession | None:
        stmt = select(ChatSessionModel).where(
            ChatSessionModel.id == session_id,
            ChatSessionModel.tenant_id == tenant_id,
            ChatSessionModel.user_id == user_id,
        )
        result = await self._session.execute(stmt)
        m = result.scalar_one_or_none()
        if m is None:
            return None
        return ChatSession(
            id=m.id,
            tenant_id=m.tenant_id,
            user_id=m.user_id,
            project_id=m.project_id,
            title=m.title,
            created_at=m.created_at,
        )

    async def update_title(
        self,
        *,
        session_id: int,
        tenant_id: int,
        user_id: int,
        title: str,
    ) -> bool:
        stmt = (
            update(ChatSessionModel)
            .where(
                ChatSessionModel.id == session_id,
                ChatSessionModel.tenant_id == tenant_id,
                ChatSessionModel.user_id == user_id,
            )
            .values(title=title[:255] if title else "")
        )
        result = await self._session.execute(stmt)
        affected = getattr(result, "rowcount", 0) or 0
        return affected > 0

    async def delete(
        self,
        *,
        session_id: int,
        tenant_id: int,
        user_id: int,
    ) -> bool:
        stmt = delete(ChatSessionModel).where(
            ChatSessionModel.id == session_id,
            ChatSessionModel.tenant_id == tenant_id,
            ChatSessionModel.user_id == user_id,
        )
        result = await self._session.execute(stmt)
        affected = getattr(result, "rowcount", 0) or 0
        return affected > 0


class ChatMessageRepositorySQLAlchemy(ChatMessageRepository):
    """SQLAlchemy implementation of ChatMessageRepository."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add_message(
        self,
        *,
        session_id: int,
        role: str,
        content: str,
        metadata: dict[str, object] | None = None,
    ) -> ChatMessage:
        now = datetime.now(UTC)
        model = ChatMessageModel(
            session_id=session_id,
            role=role,
            content=content,
            created_at=now,
            metadata_json=metadata,
        )
        self._session.add(model)
        await self._session.flush()
        return ChatMessage(
            id=model.id,
            session_id=model.session_id,
            role=model.role,
            content=model.content,
            created_at=model.created_at,
            metadata_json=model.metadata_json,
        )

    async def get_messages(
        self, session_id: int, tenant_id: int, user_id: int
    ) -> Sequence[ChatMessage]:
        stmt = (
            select(ChatMessageModel)
            .join(ChatSessionModel, ChatMessageModel.session_id == ChatSessionModel.id)
            .where(
                ChatMessageModel.session_id == session_id,
                ChatSessionModel.tenant_id == tenant_id,
                ChatSessionModel.user_id == user_id,
            )
            .order_by(ChatMessageModel.created_at.asc())
        )
        result = await self._session.execute(stmt)
        rows = result.scalars().all()
        return [
            ChatMessage(
                id=m.id,
                session_id=m.session_id,
                role=m.role,
                content=m.content,
                created_at=m.created_at,
                metadata_json=m.metadata_json,
            )
            for m in rows
        ]
