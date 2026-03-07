"""Tests for utils.severity."""

from __future__ import annotations

from logs_sentinel.domains.issues.entities import IssueSeverity
from logs_sentinel.utils.severity import log_level_to_issue_severity


def test_critical_maps_to_critical() -> None:
    assert log_level_to_issue_severity("critical") == IssueSeverity.CRITICAL


def test_error_maps_to_high() -> None:
    assert log_level_to_issue_severity("error") == IssueSeverity.HIGH


def test_warning_maps_to_medium() -> None:
    assert log_level_to_issue_severity("warning") == IssueSeverity.MEDIUM


def test_info_maps_to_low() -> None:
    assert log_level_to_issue_severity("info") == IssueSeverity.LOW


def test_debug_maps_to_low() -> None:
    assert log_level_to_issue_severity("debug") == IssueSeverity.LOW


def test_case_insensitive() -> None:
    assert log_level_to_issue_severity("ERROR") == IssueSeverity.HIGH
    assert log_level_to_issue_severity("Critical") == IssueSeverity.CRITICAL


def test_none_or_empty_maps_to_low() -> None:
    assert log_level_to_issue_severity(None) == IssueSeverity.LOW
    assert log_level_to_issue_severity("") == IssueSeverity.LOW
