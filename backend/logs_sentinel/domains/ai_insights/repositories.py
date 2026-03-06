from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Protocol

from logs_sentinel.domains.ai_insights.entities import (
    IssueFingerprint,
    SavedFixSuggestionAnalysis,
)
from logs_sentinel.domains.logs.entities import RelatedIssueWithEnrichment


class IssueEnrichmentLookupRepository(Protocol):
    """Repository for looking up issue fingerprints and enrichments (logs UI)."""

    async def get_issue_fingerprints(self, tenant_id: int) -> set[IssueFingerprint]:
        """Return set of (project_id, fingerprint) for existing issues."""

    async def get_enrichment_map(
        self, tenant_id: int
    ) -> dict[IssueFingerprint, str]:
        """Return map (project_id, fingerprint) -> latest summary."""

    async def get_related_issue_and_enrichment(
        self, tenant_id: int, project_id: int, fingerprint: str
    ) -> RelatedIssueWithEnrichment | None:
        """Return related issue and its latest enrichment, or None."""


class FixSuggestionAnalysisRepository(Protocol):
    """Repository for persisting and loading AI-analyzed fix suggestions."""

    async def upsert(
        self,
        *,
        tenant_id: int,
        project_id: int | None,
        fingerprint: str,
        title: str,
        summary: str,
        probable_cause: str,
        suggested_fix: str,
        code_snippet: str | None,
        language: str | None,
        confidence: float,
    ) -> None:
        """Insert or update the stored analysis for this tenant/project/fingerprint."""

    async def get_for_fingerprints(
        self,
        *,
        tenant_id: int,
        project_id: int | None,
        fingerprints: Sequence[str],
    ) -> dict[str, SavedFixSuggestionAnalysis]:
        """Return stored analyses for the given fingerprints (tenant + project or project=all)."""

