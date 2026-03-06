"""Chat domain entities."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class ChatSession:
    """Chat session for Log Chat (per user, within tenant + optional project)."""

    id: int
    tenant_id: int
    user_id: int
    project_id: int | None
    title: str
    created_at: datetime


@dataclass(slots=True)
class ChatMessage:
    """Single message in a chat session (user or assistant)."""

    id: int
    session_id: int
    role: str
    content: str
    created_at: datetime
    metadata_json: dict[str, object] | None
