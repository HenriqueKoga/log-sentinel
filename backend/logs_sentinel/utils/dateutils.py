"""Date/time parsing utilities."""

from __future__ import annotations

from datetime import UTC, datetime


def parse_dt(s: str | None) -> datetime | None:
    """Parse ISO datetime string (supports Z suffix). Always returns UTC-aware datetime.
    Strings without timezone (e.g. '2025-03-03') are interpreted as UTC."""
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt
    except (ValueError, TypeError):
        return None


def normalize_ts(ts: datetime | str) -> datetime:
    """Normalize ts to datetime. SQLite may return string; PostgreSQL returns datetime."""
    if isinstance(ts, datetime):
        return ts
    if isinstance(ts, str):
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    raise AssertionError("unreachable")


def ts_to_str(ts: datetime | str) -> str:
    """Format timestamp as HH:MM string. Accepts datetime or str (e.g. from DB)."""
    if hasattr(ts, "strftime"):
        return ts.strftime("%H:%M")
    return str(ts)
