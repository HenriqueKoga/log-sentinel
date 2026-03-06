"""Domain entities for metrics (dashboard)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class TimeSeriesBucket:
    """Single bucket for time series (ts, value)."""

    ts: datetime | str
    value: float
