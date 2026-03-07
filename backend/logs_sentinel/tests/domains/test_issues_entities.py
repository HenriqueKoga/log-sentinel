"""Tests for issues domain: Issue, IssueSeverity, IssueStatus, compute_priority_score."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from logs_sentinel.domains.identity.entities import TenantId
from logs_sentinel.domains.ingestion.entities import ProjectId
from logs_sentinel.domains.issues.entities import (
    Issue,
    IssueId,
    IssueSeverity,
    IssueStatus,
    compute_priority_score,
)


def test_issue_severity_values() -> None:
    assert IssueSeverity.LOW.value == "low"
    assert IssueSeverity.MEDIUM.value == "medium"
    assert IssueSeverity.HIGH.value == "high"
    assert IssueSeverity.CRITICAL.value == "critical"


def test_issue_status_values() -> None:
    assert IssueStatus.OPEN.value == "open"
    assert IssueStatus.SNOOZED.value == "snoozed"
    assert IssueStatus.RESOLVED.value == "resolved"


def test_issue_update_on_occurrence() -> None:
    tenant_id = TenantId(1)
    project_id = ProjectId(1)
    first = datetime(2025, 1, 1, 12, 0, tzinfo=UTC)
    last = datetime(2025, 1, 1, 14, 0, tzinfo=UTC)
    issue = Issue(
        id=IssueId(1),
        tenant_id=tenant_id,
        project_id=project_id,
        fingerprint="fp1",
        title="Error",
        severity=IssueSeverity.HIGH,
        status=IssueStatus.OPEN,
        first_seen=first,
        last_seen=last,
        total_count=5,
        priority_score=1.0,
    )
    later = datetime(2025, 1, 1, 16, 0, tzinfo=UTC)
    issue.update_on_occurrence(later, increment=3)
    assert issue.last_seen == later
    assert issue.total_count == 8

    earlier = datetime(2025, 1, 1, 10, 0, tzinfo=UTC)
    issue.update_on_occurrence(earlier, increment=1)
    assert issue.last_seen == later  # unchanged
    assert issue.total_count == 9


def test_compute_priority_score() -> None:
    # severity weights: LOW=0.5, MEDIUM=1.0, HIGH=2.0, CRITICAL=3.0
    # score = severity_weight * log1p(count_last_hour) * spike_factor
    s_low = compute_priority_score(IssueSeverity.LOW, 10, 1.0)
    s_high = compute_priority_score(IssueSeverity.HIGH, 10, 1.0)
    assert s_high > s_low

    s_zero = compute_priority_score(IssueSeverity.MEDIUM, 0, 1.0)
    assert s_zero == 0.0

    s_spike = compute_priority_score(IssueSeverity.MEDIUM, 5, 2.0)
    s_no_spike = compute_priority_score(IssueSeverity.MEDIUM, 5, 1.0)
    assert s_spike == pytest.approx(2.0 * s_no_spike)
