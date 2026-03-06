from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any, NewType

from logs_sentinel.domains.identity.entities import TenantId
from logs_sentinel.domains.issues.entities import IssueId

IssueEnrichmentId = NewType("IssueEnrichmentId", int)


@dataclass(slots=True)
class IssueEnrichment:
    """AI-generated enrichment for an issue."""

    id: IssueEnrichmentId
    tenant_id: TenantId
    issue_id: IssueId
    model_name: str
    summary: str
    suspected_cause: str
    checklist_json: list[str]
    created_at: datetime


@dataclass(slots=True)
class SuggestIssueResult:
    """AI-suggested title and severity for a new issue from context."""

    title: str
    severity: str


@dataclass(slots=True)
class FixSuggestionResult:
    """LLM-produced fix suggestion for an error cluster."""

    title: str
    summary: str
    probable_cause: str
    suggested_fix: str
    code_snippet: str | None
    language: str | None
    confidence: float


class LLMClientProtocol:
    """Protocol for LLM enrichment clients."""

    async def enrich_issue(self, events: Sequence[dict[str, object]]) -> IssueEnrichment:
        """Generate an enrichment summary from recent events."""

        raise NotImplementedError

    async def suggest_issue(self, context: str) -> SuggestIssueResult:
        """Suggest issue title and severity from a text context (e.g. error message)."""

        raise NotImplementedError

    async def suggest_fix(
        self,
        *,
        fingerprint: str,
        sample_messages: Sequence[str],
        stacktrace: str | None,
        lang: str = "pt-BR",
    ) -> FixSuggestionResult:
        """Suggest fix information for an error cluster."""

        raise NotImplementedError

    async def chat_with_tools(
        self,
        messages: Sequence[dict[str, Any]],
        tools: Sequence[dict[str, Any]],
        lang: str = "pt-BR",
    ) -> tuple[str, list[dict[str, Any]]]:
        """Chat completion with optional tool calls. Returns (content, tool_calls)."""

        raise NotImplementedError
