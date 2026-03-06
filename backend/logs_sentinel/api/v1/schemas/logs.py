from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class LogListItem(BaseModel):
    id: int
    timestamp: datetime
    level: str
    message: str
    project_id: int
    project_name: str
    source: str
    ai_summary: str | None = None


class LogsListResponse(BaseModel):
    items: list[LogListItem]
    total: int


class RelatedIssueInfo(BaseModel):
    id: int
    title: str


class LogDetailEnrichment(BaseModel):
    model_name: str
    summary: str
    suspected_cause: str
    checklist: list[str]
    created_at: datetime


class LogDetailResponse(BaseModel):
    id: int
    timestamp: datetime
    level: str
    message: str
    exception_type: str | None
    stacktrace: str | None
    raw_json: dict[str, Any]
    project_id: int
    project_name: str
    source: str
    related_issue: RelatedIssueInfo | None = None
    enrichment: LogDetailEnrichment | None = None
