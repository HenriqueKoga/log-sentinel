from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import NewType

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


class LLMClientProtocol:
    """Protocol for LLM enrichment clients."""

    async def enrich_issue(self, events: Sequence[dict[str, object]]) -> IssueEnrichment:
        """Generate an enrichment summary from recent events."""

        raise NotImplementedError

