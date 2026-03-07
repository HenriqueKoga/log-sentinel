"""Tests for FixSuggestionsService (get_suggestions, get_cluster_events, build_suggestion_from_llm_result)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from logs_sentinel.application.services.ai_insights_service import FixSuggestionsService
from logs_sentinel.domains.ai.entities import FixSuggestionResult
from logs_sentinel.domains.ai_insights.entities import ErrorLogEvent
from logs_sentinel.domains.ingestion.entities import LogEventId, ProjectId
from logs_sentinel.domains.logs.repositories import LogSearchRepository


class InMemoryLogSearch(LogSearchRepository):
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows

    async def recent_errors(
        self,
        *,
        tenant_id: Any,
        project_id: Any,
        from_dt: Any,
        to_dt: Any,
        limit: int,
    ) -> list[ErrorLogEvent]:
        events: list[ErrorLogEvent] = []
        for row in list(self._rows)[:limit]:
            events.append(
                ErrorLogEvent(
                    id=LogEventId(row["id"]),
                    project_id=ProjectId(row["project_id"]),
                    message=row["message"],
                    exception_type=row["exception_type"],
                    stacktrace=row["stacktrace"],
                    received_at=row["received_at"],
                    level=row["level"],
                )
            )
        return events

    async def get_event_by_id(
        self,
        *,
        tenant_id: Any,
        event_id: int,
        project_id: Any | None = None,
    ) -> ErrorLogEvent | None:
        for row in self._rows:
            if row.get("id") == event_id:
                return ErrorLogEvent(
                    id=LogEventId(row["id"]),
                    project_id=ProjectId(row["project_id"]),
                    message=row["message"],
                    exception_type=row["exception_type"],
                    stacktrace=row["stacktrace"],
                    received_at=row["received_at"],
                    level=row["level"],
                )
        return None


def _make_rows(
    count: int,
    exc: str = "ValueError",
    msg: str = "invalid literal",
    same_stack: bool = True,
) -> list[dict[str, Any]]:
    """same_stack=True: same stacktrace for all rows so they form one cluster."""
    now = datetime.now(UTC)
    stack = "File \"/app/main.py\", line 10, in func" if same_stack else None
    return [
        {
            "id": i + 1,
            "message": msg,
            "exception_type": exc,
            "stacktrace": stack if same_stack else f"File \"/app/main.py\", line {i}, in func",
            "received_at": now - timedelta(minutes=count - i),
            "level": "error",
            "project_id": 1,
        }
        for i in range(count)
    ]


@pytest.mark.asyncio
async def test_get_suggestions_groups_by_fingerprint_and_uses_heuristics() -> None:
    now = datetime.now(UTC)
    rows = _make_rows(2)
    service = FixSuggestionsService(log_search=InMemoryLogSearch(rows))

    suggestions = await service.get_suggestions(
        tenant_id=1,
        project_id=1,
        from_dt=now - timedelta(hours=1),
        to_dt=now,
    )

    assert len(suggestions) == 1
    s = suggestions[0]
    assert s.occurrences == 2
    assert "conversão" in s.title.lower() or "value" in s.title.lower()
    assert s.sample_event_id == 2
    assert s.analyzed is False


@pytest.mark.asyncio
async def test_get_suggestions_sort_by_occurrences_desc() -> None:
    now = datetime.now(UTC)
    # Two clusters: one with 2 events (same stack), one with 1 (different exception + stack)
    rows = _make_rows(2, same_stack=True) + [
        {
            "id": 3,
            "message": "KeyError: 'x'",
            "exception_type": "KeyError",
            "stacktrace": "File \"/app/other.py\", line 1, in other",
            "received_at": now - timedelta(minutes=10),
            "level": "error",
            "project_id": 1,
        },
    ]
    service = FixSuggestionsService(log_search=InMemoryLogSearch(rows))

    suggestions = await service.get_suggestions(
        tenant_id=1,
        project_id=1,
        from_dt=now - timedelta(hours=1),
        to_dt=now,
        sort_by="occurrences",
        order="desc",
    )

    assert len(suggestions) == 2
    assert suggestions[0].occurrences >= suggestions[1].occurrences


@pytest.mark.asyncio
async def test_get_suggestions_sort_by_confidence_asc() -> None:
    now = datetime.now(UTC)
    rows = _make_rows(1, exc="ValueError", same_stack=True) + [
        {
            "id": 2,
            "message": "something unknown",
            "exception_type": "CustomError",
            "stacktrace": "File \"/app/other.py\", line 1, in other",
            "received_at": now - timedelta(minutes=5),
            "level": "error",
            "project_id": 1,
        },
    ]
    service = FixSuggestionsService(log_search=InMemoryLogSearch(rows))

    suggestions = await service.get_suggestions(
        tenant_id=1,
        project_id=1,
        from_dt=now - timedelta(hours=1),
        to_dt=now,
        sort_by="confidence",
        order="asc",
    )

    assert len(suggestions) == 2
    assert suggestions[0].confidence <= suggestions[1].confidence


@pytest.mark.asyncio
async def test_get_suggestions_sort_by_title() -> None:
    now = datetime.now(UTC)
    rows = _make_rows(1, exc="KeyError", msg="key x", same_stack=True) + [
        {
            "id": 2,
            "message": "invalid",
            "exception_type": "ValueError",
            "stacktrace": "File \"/app/b.py\", line 1, in b",
            "received_at": now - timedelta(minutes=5),
            "level": "error",
            "project_id": 1,
        },
    ]
    service = FixSuggestionsService(log_search=InMemoryLogSearch(rows))

    suggestions = await service.get_suggestions(
        tenant_id=1,
        project_id=1,
        from_dt=now - timedelta(hours=1),
        to_dt=now,
        sort_by="title",
        order="asc",
    )

    assert len(suggestions) == 2
    assert suggestions[0].title.lower() <= suggestions[1].title.lower()


@pytest.mark.asyncio
async def test_get_suggestions_sort_by_last_seen() -> None:
    now = datetime.now(UTC)
    rows = _make_rows(2)
    service = FixSuggestionsService(log_search=InMemoryLogSearch(rows))

    suggestions = await service.get_suggestions(
        tenant_id=1,
        project_id=1,
        from_dt=now - timedelta(hours=1),
        to_dt=now,
        sort_by="last_seen",
        order="desc",
    )

    assert len(suggestions) == 1
    assert suggestions[0].last_seen >= suggestions[0].first_seen


@pytest.mark.asyncio
async def test_get_suggestions_sort_by_first_seen() -> None:
    now = datetime.now(UTC)
    rows = _make_rows(1)
    service = FixSuggestionsService(log_search=InMemoryLogSearch(rows))

    suggestions = await service.get_suggestions(
        tenant_id=1,
        project_id=1,
        from_dt=now - timedelta(hours=1),
        to_dt=now,
        sort_by="first_seen",
        order="asc",
    )

    assert len(suggestions) == 1


@pytest.mark.asyncio
async def test_get_suggestions_unknown_sort_by_defaults_to_occurrences() -> None:
    now = datetime.now(UTC)
    rows = _make_rows(1)
    service = FixSuggestionsService(log_search=InMemoryLogSearch(rows))

    suggestions = await service.get_suggestions(
        tenant_id=1,
        project_id=1,
        from_dt=now - timedelta(hours=1),
        to_dt=now,
        sort_by="unknown_field",
        order="desc",
    )

    assert len(suggestions) == 1


@pytest.mark.asyncio
async def test_get_cluster_events_returns_events_for_fingerprint() -> None:
    now = datetime.now(UTC)
    rows = _make_rows(2, same_stack=True)
    service = FixSuggestionsService(log_search=InMemoryLogSearch(rows))
    suggestions = await service.get_suggestions(
        tenant_id=1, project_id=1, from_dt=now - timedelta(hours=1), to_dt=now
    )
    fp = suggestions[0].fingerprint

    events = await service.get_cluster_events(
        tenant_id=1,
        project_id=1,
        fingerprint=fp,
        from_dt=now - timedelta(hours=1),
        to_dt=now,
    )

    assert events is not None
    assert len(events) == 2


@pytest.mark.asyncio
async def test_get_cluster_events_returns_none_for_unknown_fingerprint() -> None:
    now = datetime.now(UTC)
    service = FixSuggestionsService(log_search=InMemoryLogSearch([]))

    events = await service.get_cluster_events(
        tenant_id=1,
        project_id=1,
        fingerprint="nonexistent-fp",
        from_dt=now - timedelta(hours=1),
        to_dt=now,
    )

    assert events is None


@pytest.mark.asyncio
async def test_build_suggestion_from_llm_result() -> None:
    now = datetime.now(UTC)
    rows = _make_rows(2)
    service = FixSuggestionsService(log_search=InMemoryLogSearch(rows))
    suggestions = await service.get_suggestions(
        tenant_id=1, project_id=1, from_dt=now - timedelta(hours=1), to_dt=now
    )
    fp = suggestions[0].fingerprint
    events = await service.get_cluster_events(
        tenant_id=1,
        project_id=1,
        fingerprint=fp,
        from_dt=now - timedelta(hours=1),
        to_dt=now,
    )
    assert events is not None

    llm = FixSuggestionResult(
        title="Custom title",
        summary="Summary",
        probable_cause="Cause",
        suggested_fix="Fix",
        code_snippet="print(1)",
        language="en",
        confidence=0.85,
    )

    suggestion = await service.build_suggestion_from_llm_result(
        tenant_id=1,
        project_id=1,
        fingerprint=fp,
        events_sorted=events,
        llm_suggestion=llm,
    )

    assert suggestion.title == "Custom title"
    assert suggestion.summary == "Summary"
    assert suggestion.code_snippet == "print(1)"
    assert suggestion.confidence == 0.85
    assert suggestion.occurrences == len(events)
    assert suggestion.analyzed is True
