from __future__ import annotations

from pydantic import BaseModel


class TimeSeriesPoint(BaseModel):
    ts: str
    value: float


class DashboardMetricsResponse(BaseModel):
    log_volume: list[TimeSeriesPoint]
    error_rate: list[TimeSeriesPoint]
