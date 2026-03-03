from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class IngestEvent(BaseModel):
    level: str = Field(..., max_length=32)
    message: str
    exception_type: str | None = None
    stacktrace: str | None = None
    context: dict[str, Any] | None = None


class IngestBatchRequest(BaseModel):
    events: list[IngestEvent]


class IngestBatchResponse(BaseModel):
    batch_id: str
    accepted_count: int

