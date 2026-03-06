from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from math import log1p
from typing import NewType

from logs_sentinel.domains.identity.entities import TenantId
from logs_sentinel.domains.ingestion.entities import ProjectId

IssueId = NewType("IssueId", int)
IssueOccurrenceId = NewType("IssueOccurrenceId", int)


class IssueSeverity(StrEnum):
    """Severity levels for issues."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class IssueStatus(StrEnum):
    """Lifecycle state of an issue."""

    OPEN = "open"
    SNOOZED = "snoozed"
    RESOLVED = "resolved"


@dataclass(slots=True)
class Issue:
    """Aggregate root representing a grouped error/issue."""

    id: IssueId
    tenant_id: TenantId
    project_id: ProjectId
    fingerprint: str
    title: str
    severity: IssueSeverity
    status: IssueStatus
    first_seen: datetime
    last_seen: datetime
    total_count: int
    priority_score: float
    snoozed_until: datetime | None = None

    def update_on_occurrence(self, occurred_at: datetime, increment: int) -> None:
        """Update aggregate state when a new occurrence is recorded."""

        self.last_seen = max(self.last_seen, occurred_at)
        self.total_count += increment


@dataclass(slots=True)
class IssueOccurrenceBucket:
    """Time-bucketed counts for an issue, used for spike detection."""

    id: IssueOccurrenceId
    tenant_id: TenantId
    issue_id: IssueId
    bucket_start: datetime
    bucket_minutes: int
    count: int


def compute_priority_score(
    severity: IssueSeverity,
    count_last_hour: int,
    spike_factor: float,
) -> float:
    """Compute issue priority score based on severity and recent activity."""

    severity_weight_map: dict[IssueSeverity, float] = {
        IssueSeverity.LOW: 0.5,
        IssueSeverity.MEDIUM: 1.0,
        IssueSeverity.HIGH: 2.0,
        IssueSeverity.CRITICAL: 3.0,
    }
    severity_weight = severity_weight_map[severity]
    return severity_weight * log1p(count_last_hour) * spike_factor
