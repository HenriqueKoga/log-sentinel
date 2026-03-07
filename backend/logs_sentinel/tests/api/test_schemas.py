"""Tests for API request/response schemas."""

from __future__ import annotations

from datetime import UTC, datetime

from logs_sentinel.api.v1.schemas.ingest import IngestBatchRequest, IngestBatchResponse, IngestEvent
from logs_sentinel.api.v1.schemas.logs import LogListItem, LogsListResponse
from logs_sentinel.api.v1.schemas.metrics import DashboardMetricsResponse, TimeSeriesPoint


def test_log_list_item_validation() -> None:
    item = LogListItem(
        id=1,
        timestamp=datetime.now(UTC),
        level="error",
        message="msg",
        project_id=1,
        project_name="Backend",
        source="api",
    )
    assert item.level == "error"
    assert item.project_name == "Backend"


def test_logs_list_response_validation() -> None:
    resp = LogsListResponse(items=[], total=0)
    assert resp.total == 0
    assert resp.items == []


def test_time_series_point() -> None:
    p = TimeSeriesPoint(ts="10:00", value=100.5)
    assert p.ts == "10:00"
    assert p.value == 100.5


def test_dashboard_metrics_response() -> None:
    resp = DashboardMetricsResponse(log_volume=[], error_rate=[])
    assert resp.log_volume == []
    assert resp.error_rate == []


def test_ingest_event_accepts_context() -> None:
    ev = IngestEvent(
        level="info",
        message="test",
        exception_type=None,
        stacktrace=None,
        context={"service": "api"},
    )
    assert ev.context == {"service": "api"}


def test_ingest_batch_request_response() -> None:
    req = IngestBatchRequest(events=[IngestEvent(level="error", message="x")])
    assert len(req.events) == 1
    assert req.events[0].level == "error"
    resp = IngestBatchResponse(batch_id="b1", accepted_count=1)
    assert resp.batch_id == "b1"
    assert resp.accepted_count == 1
