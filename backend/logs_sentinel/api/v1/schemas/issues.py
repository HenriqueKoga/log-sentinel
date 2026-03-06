from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class IssueSeverityEnum(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class IssueStatusEnum(StrEnum):
    OPEN = "open"
    SNOOZED = "snoozed"
    RESOLVED = "resolved"


class IssueListItem(BaseModel):
    id: int
    project_id: int
    title: str
    severity: IssueSeverityEnum
    status: IssueStatusEnum
    last_seen: datetime
    total_count: int
    priority_score: float


class IssuesAggregates(BaseModel):
    total: int
    by_severity: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)


class IssuesListResponse(BaseModel):
    items: list[IssueListItem]
    aggregates: IssuesAggregates


class IssueDetailSample(BaseModel):
    received_at: datetime
    level: str
    message: str
    exception_type: str | None = None
    stacktrace: str | None = None


class IssueEnrichmentResponse(BaseModel):
    model_name: str
    summary: str
    suspected_cause: str
    checklist: list[str]
    created_at: datetime


class IssueDetailResponse(BaseModel):
    id: int
    project_id: int
    title: str
    severity: IssueSeverityEnum
    status: IssueStatusEnum
    first_seen: datetime
    last_seen: datetime
    total_count: int
    priority_score: float
    snoozed_until: datetime | None = None
    samples: list[IssueDetailSample]
    enrichment: IssueEnrichmentResponse | None = None


class IssueOccurrencesPoint(BaseModel):
    bucket_start: datetime
    count: int


class IssueOccurrencesResponse(BaseModel):
    points: list[IssueOccurrencesPoint]


class SnoozeRequest(BaseModel):
    duration_minutes: int = Field(gt=0, le=7 * 24 * 60)


class CreateIssueRequest(BaseModel):
    project_id: int
    title: str = Field(min_length=1, max_length=255)
    severity: IssueSeverityEnum


class CreateIssueFromLogRequest(BaseModel):
    log_id: int


class SuggestIssueRequest(BaseModel):
    context: str = Field(min_length=1, max_length=10000)


class SuggestIssueResponse(BaseModel):
    title: str
    severity: IssueSeverityEnum


class EnrichIssueRequest(BaseModel):
    """Optional: when provided, only this log is sent to the LLM (e.g. user requested analysis from log detail)."""

    log_id: int | None = None


class EnrichIssueResponse(BaseModel):
    enrichment: IssueEnrichmentResponse
