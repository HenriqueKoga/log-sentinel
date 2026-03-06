from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class AnalyzeFixSuggestionBody(BaseModel):
    fingerprint: str
    project_id: int | None = None


class FixSuggestionOut(BaseModel):
    fingerprint: str
    title: str
    summary: str
    probable_cause: str
    suggested_fix: str
    code_snippet: str | None = None
    language: str | None = None
    confidence: float
    occurrences: int
    first_seen: datetime
    last_seen: datetime
    sample_event_id: int | None = None


class FixSuggestionsResponse(BaseModel):
    items: list[FixSuggestionOut]

