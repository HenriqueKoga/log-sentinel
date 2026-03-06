"""Repository protocol for AI enrichment data."""

from __future__ import annotations

from typing import Protocol

from logs_sentinel.domains.ai.entities import IssueEnrichment
from logs_sentinel.domains.identity.entities import TenantId
from logs_sentinel.domains.issues.entities import IssueId


class IssueEnrichmentRepository(Protocol):
    """Repository for loading and persisting issue enrichment data."""

    async def get_latest_enrichment(
        self, tenant_id: TenantId, issue_id: IssueId
    ) -> IssueEnrichment | None:
        """Return the most recent enrichment for the issue, or None."""
        ...

    async def persist_enrichment(
        self,
        tenant_id: TenantId,
        issue_id: IssueId,
        *,
        model_name: str,
        summary: str,
        suspected_cause: str,
        checklist_json: list[str],
    ) -> IssueEnrichment:
        """Persist enrichment data for an issue and return the created IssueEnrichment."""
        ...
