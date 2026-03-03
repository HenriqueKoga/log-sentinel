from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

from logs_sentinel.domains.ai.entities import IssueEnrichment, IssueEnrichmentId, LLMClientProtocol
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

