"""Pydantic output schemas for Pydantic AI agents (structured outputs)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class IssueEnrichmentOutput(BaseModel):
    """Structured output for issue enrichment agent."""

    summary: str = Field(description="2-3 sentence summary of what is happening")
    suspected_cause: str = Field(description="Most likely root cause in one sentence")
    checklist: list[str] = Field(
        default_factory=list,
        description="3-6 concrete steps to investigate or fix the issue",
    )


SeverityKind = Literal["low", "medium", "high", "critical"]


class SuggestIssueOutput(BaseModel):
    """Structured output for suggest issue title/severity agent."""

    title: str = Field(description="Short issue title, max 200 chars")
    severity: SeverityKind = Field(
        description="One of: low, medium, high, critical",
    )


class FixSuggestionOutput(BaseModel):
    """Structured output for fix suggestion agent."""

    title: str = Field(description="Short, direct title for the problem")
    summary: str = Field(description="2-3 sentence explanation of what is happening")
    probable_cause: str = Field(description="Best-guess root cause")
    suggested_fix: str = Field(description="Concrete steps to fix it")
    code_snippet: str | None = Field(default=None, description="Useful code example or null")
    language: str | None = Field(default=None, description="Language of the text, e.g. pt-BR or en")
    confidence: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Confidence score between 0 and 1",
    )


class ChatSessionTitleOutput(BaseModel):
    """Structured output for chat session title agent."""

    title: str = Field(
        description="Very short title for the chat session (max ~80 characters).",
    )
