from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from logs_sentinel.domains.ai.entities import (
    FixSuggestionResult,
    IssueEnrichment,
    IssueEnrichmentId,
    LLMClientProtocol,
    SuggestIssueResult,
)
from logs_sentinel.domains.identity.entities import TenantId
from logs_sentinel.domains.issues.entities import IssueId


class NullLLMClient(LLMClientProtocol):
    """No-op LLM client used when enrichment is disabled."""

    async def enrich_issue(self, events: Sequence[dict[str, object]]) -> IssueEnrichment:
        """Return a placeholder enrichment that contains no sensitive information."""

        # For the null client, we do not know tenant or issue ids; the caller is expected
        # to persist the enrichment with correct identifiers if needed.
        return IssueEnrichment(
            id=IssueEnrichmentId(-1),  # placeholder, will be replaced by persistence layer
            tenant_id=TenantId(-1),
            issue_id=IssueId(-1),
            model_name="null-llm",
            summary="LLM enrichment is disabled.",
            suspected_cause="Enable LLM enrichment to see AI-generated analysis.",
            checklist_json=[
                "Check recent deployments.",
                "Inspect related logs around the spike.",
                "Verify configuration and environment variables.",
            ],
            created_at=datetime.now(tz=UTC),
        )

    async def suggest_issue(self, context: str) -> SuggestIssueResult:
        """Return a placeholder suggestion when LLM is disabled."""
        return SuggestIssueResult(
            title=context[:200].strip() or "Manual issue",
            severity="medium",
        )

    async def suggest_fix(
        self,
        *,
        fingerprint: str,
        sample_messages: Sequence[str],
        stacktrace: str | None,
        lang: str = "pt-BR",
    ) -> FixSuggestionResult:
        """Return a deterministic placeholder fix suggestion when LLM is disabled."""

        title = "LLM desabilitado" if lang.startswith("pt") else "LLM disabled"
        summary = (
            "A análise automática via LLM está desabilitada para este tenant."
            if lang.startswith("pt")
            else "Automatic LLM-based analysis is disabled for this tenant."
        )
        cause = (
            "Habilite o LLM nas configurações de billing para ver sugestões geradas por IA."
            if lang.startswith("pt")
            else "Enable LLM in billing settings to see AI-generated suggestions."
        )
        fix = (
            "Revise manualmente os logs e, se necessário, habilite o LLM."
            if lang.startswith("pt")
            else "Manually review the logs and enable LLM if needed."
        )
        return FixSuggestionResult(
            title=title,
            summary=summary,
            probable_cause=cause,
            suggested_fix=fix,
            code_snippet=None,
            language=lang,
            confidence=0.5,
        )

    async def chat_with_tools(
        self,
        messages: Sequence[dict[str, Any]],
        tools: Sequence[dict[str, Any]],
        lang: str = "pt-BR",
    ) -> tuple[str, list[dict[str, Any]]]:
        """Return placeholder when LLM is disabled."""
        msg = (
            "O chat com IA está desativado. Habilite o LLM no plano para usar esta função."
            if (lang or "").lower().startswith("pt")
            else "AI chat is disabled. Enable LLM in your plan to use this feature."
        )
        return (msg, [])
