"""Domain entities for logs API (read model)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class LogListRow:
    """Single log row for list view."""

    id: int
    received_at: datetime
    level: str
    message: str
    project_id: int
    project_name: str
    raw_json: dict[str, Any]
    stacktrace: str | None
    exception_type: str | None


@dataclass(slots=True)
class LogDetailRow:
    """Single log for detail view."""

    id: int
    received_at: datetime
    level: str
    message: str
    exception_type: str | None
    stacktrace: str | None
    raw_json: dict[str, Any]
    project_id: int
    project_name: str


@dataclass(slots=True)
class LogEventForTenant:
    """Single log event loaded for a tenant (e.g. for issue creation, AI enrichment)."""

    id: int
    project_id: int
    message: str | None
    exception_type: str | None
    stacktrace: str | None
    level: str
    received_at: datetime


@dataclass(slots=True)
class RelatedIssueRow:
    """Related issue for a log (by fingerprint)."""

    id: int
    title: str


@dataclass(slots=True)
class EnrichmentRow:
    """AI enrichment for an issue."""

    model_name: str
    summary: str
    suspected_cause: str
    checklist: list[str]
    created_at: datetime


@dataclass(slots=True)
class RelatedIssueWithEnrichment:
    """Related issue and its latest AI enrichment (for logs UI)."""

    issue: RelatedIssueRow
    enrichment: EnrichmentRow | None
