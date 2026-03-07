"""Tests for utils.dateutils."""

from __future__ import annotations

from datetime import UTC, datetime

from logs_sentinel.utils.dateutils import normalize_ts, parse_dt, ts_to_str


def test_parse_dt_none_returns_none() -> None:
    assert parse_dt(None) is None


def test_parse_dt_empty_string_returns_none() -> None:
    assert parse_dt("") is None


def test_parse_dt_iso_with_z() -> None:
    dt = parse_dt("2025-03-03T14:30:00Z")
    assert dt is not None
    assert dt.tzinfo is not None
    assert dt.year == 2025
    assert dt.month == 3
    assert dt.day == 3
    assert dt.hour == 14
    assert dt.minute == 30


def test_parse_dt_naive_interpreted_as_utc() -> None:
    dt = parse_dt("2025-03-03T12:00:00")
    assert dt is not None
    assert dt.tzinfo == UTC


def test_parse_dt_invalid_returns_none() -> None:
    assert parse_dt("not-a-date") is None


def test_ts_to_str_datetime() -> None:
    dt = datetime(2025, 3, 3, 14, 30, tzinfo=UTC)
    assert ts_to_str(dt) == "14:30"


def test_ts_to_str_string_passthrough() -> None:
    assert ts_to_str("14:30") == "14:30"


def test_normalize_ts_datetime_unchanged() -> None:
    dt = datetime(2025, 3, 3, 14, 30, tzinfo=UTC)
    assert normalize_ts(dt) is dt


def test_normalize_ts_string_parsed() -> None:
    dt = normalize_ts("2025-03-03T14:30:00Z")
    assert dt.year == 2025
    assert dt.month == 3
    assert dt.hour == 14
    assert dt.minute == 30


def test_normalize_ts_invalid_type_raises() -> None:
    """Reachable only with wrong type (e.g. from DB driver); ensures unreachable branch is documented."""
    from typing import cast

    import pytest

    bad: datetime | str = cast(datetime | str, 123)
    with pytest.raises(AssertionError, match="unreachable"):
        normalize_ts(bad)
