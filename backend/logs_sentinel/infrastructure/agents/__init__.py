"""Pydantic AI agents for enrichment, suggest issue, suggest fix, chat, and session titling."""

from __future__ import annotations

from logs_sentinel.infrastructure.agents.chat import ChatAgentDeps, create_chat_agent
from logs_sentinel.infrastructure.agents.chat_session_title import (
    ChatSessionTitleOutput,
    create_chat_session_title_agent,
)
from logs_sentinel.infrastructure.agents.schemas import (
    FixSuggestionOutput,
    IssueEnrichmentOutput,
    SuggestIssueOutput,
)

__all__ = [
    "ChatAgentDeps",
    "FixSuggestionOutput",
    "ChatSessionTitleOutput",
    "IssueEnrichmentOutput",
    "SuggestIssueOutput",
    "create_chat_agent",
    "create_chat_session_title_agent",
]
