from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from logs_sentinel.domains.ingestion.entities import LogEventId, ProjectId


@dataclass(frozen=True, slots=True)
class IssueFingerprint:
    """Key for issue lookup by project and fingerprint."""

    project_id: int
    fingerprint: str


@dataclass(slots=True)
class InsightSuggestion:
    """Domain entity representing a fix suggestion for an error cluster."""

    fingerprint: str
    title: str
    summary: str
    probable_cause: str
    suggested_fix: str
    code_snippet: str | None
    language: str | None
    confidence: float
    occurrences: int
    first_seen: datetime
    last_seen: datetime
    sample_event_id: int | None
    analyzed: bool = False


@dataclass(slots=True)
class SavedFixSuggestionAnalysis:
    """Persisted AI analysis for a fix suggestion (by tenant + project + fingerprint)."""

    fingerprint: str
    title: str
    summary: str
    probable_cause: str
    suggested_fix: str
    code_snippet: str | None
    language: str | None
    confidence: float


@dataclass(slots=True)
class ErrorLogEvent:
    """Lightweight view of a log event used for AI insights clustering."""

    id: LogEventId
    project_id: ProjectId
    message: str
    exception_type: str | None
    stacktrace: str | None
    received_at: datetime
    level: str


