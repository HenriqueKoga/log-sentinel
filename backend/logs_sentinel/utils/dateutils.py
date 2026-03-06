"""Date/time parsing utilities."""

from __future__ import annotations

from datetime import datetime


def parse_dt(s: str | None) -> datetime | None:
    """Parse ISO datetime string (supports Z suffix). Returns None if empty or invalid."""
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def ts_to_str(ts: datetime | str) -> str:
    """Format timestamp as HH:MM string. Accepts datetime or str (e.g. from DB)."""
    if hasattr(ts, "strftime"):
        return ts.strftime("%H:%M")
    return str(ts)
