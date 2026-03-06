"""Chat domain: entities and repository protocols for Log Chat."""

from logs_sentinel.domains.chat.entities import ChatMessage, ChatSession
from logs_sentinel.domains.chat.repositories import (
    ChatMessageRepository,
    ChatSessionRepository,
)

__all__ = [
    "ChatMessage",
    "ChatMessageRepository",
    "ChatSession",
    "ChatSessionRepository",
]
