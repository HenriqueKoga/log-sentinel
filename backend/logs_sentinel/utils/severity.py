"""Severity and log-level mapping utilities."""

from __future__ import annotations

from logs_sentinel.domains.issues.entities import IssueSeverity


def log_level_to_issue_severity(level: str | None) -> IssueSeverity:
    """Map log level string to issue severity."""
    level_lower = (level or "").lower()
    if level_lower == "critical":
        return IssueSeverity.CRITICAL
    if level_lower == "error":
        return IssueSeverity.HIGH
    if level_lower == "warning":
        return IssueSeverity.MEDIUM
    return IssueSeverity.LOW
