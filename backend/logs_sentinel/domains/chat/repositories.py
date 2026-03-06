"""Chat domain repository protocols."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from logs_sentinel.domains.chat.entities import ChatMessage, ChatSession


class ChatSessionRepository(Protocol):
    """Repository for chat sessions (Log Chat, per user)."""

    async def create(
        self,
        *,
        tenant_id: int,
        user_id: int,
        project_id: int | None,
        title: str = "",
    ) -> ChatSession:
        """Create a new session for the user."""

    async def list_sessions(
        self,
        *,
        tenant_id: int,
        user_id: int,
        project_id: int | None,
        limit: int = 50,
    ) -> Sequence[ChatSession]:
        """List sessions for user in tenant (optional project filter), newest first."""

    async def get_by_id(
        self, session_id: int, tenant_id: int, user_id: int
    ) -> ChatSession | None:
        """Get session by id if it belongs to tenant and user."""

    async def update_title(
        self,
        *,
        session_id: int,
        tenant_id: int,
        user_id: int,
        title: str,
    ) -> bool:
        """Update session title if it belongs to tenant and user. Returns True if updated."""

    async def delete(
        self,
        *,
        session_id: int,
        tenant_id: int,
        user_id: int,
    ) -> bool:
        """Delete session if it belongs to tenant and user. Returns True if deleted."""


class ChatMessageRepository(Protocol):
    """Repository for chat messages."""

    async def add_message(
        self,
        *,
        session_id: int,
        role: str,
        content: str,
        metadata: dict[str, object] | None = None,
    ) -> ChatMessage:
        """Append a message to a session."""

    async def get_messages(
        self, session_id: int, tenant_id: int, user_id: int
    ) -> Sequence[ChatMessage]:
        """Return messages for session (ownership check via session tenant+user). Ordered by created_at."""
