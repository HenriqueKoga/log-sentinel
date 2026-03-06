from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from logs_sentinel.application.services.ai_insights_service import FixSuggestionsService
from logs_sentinel.domains.ai_insights.entities import ErrorLogEvent
from logs_sentinel.domains.ai_insights.fingerprinting import (
    compute_fingerprint,
    normalize_message,
    normalize_stacktrace,
)
from logs_sentinel.domains.ai_insights.heuristics import (
    confidence_from_occurrences,
    map_exception_to_heuristic,
)
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


def test_normalize_message_replaces_dynamic_parts() -> None:
    msg = "User 123 with id 456e7890-e89b-12d3-a456-426614174000 at /home/foo/file.py at 2026-03-05T10:00:00Z"
    norm = normalize_message(msg)
    assert "<NUMBER>" in norm
    assert "<UUID>" in norm
    assert "<PATH>" in norm
    assert "<TIMESTAMP>" in norm


def test_normalize_stacktrace_drops_line_numbers() -> None:
    raw = "File \"/app/main.py\", line 123, in <module>\n  File \"/app/mod.py\", line 45, in func"
    norm = normalize_stacktrace(raw)
    assert "line 123" not in norm
    assert "line 45" not in norm
    assert "/app/main.py" in norm
    assert "/app/mod.py" in norm


def test_compute_fingerprint_deterministic() -> None:
    fp1 = compute_fingerprint("ValueError", "stack", "message")
    fp2 = compute_fingerprint("ValueError", "stack", "message")
    assert fp1 == fp2


def test_confidence_boosts_with_occurrences() -> None:
    base = 0.6
    low = confidence_from_occurrences(base, 1)
    high = confidence_from_occurrences(base, 100)
    assert high > low
    assert high <= 1.0


@pytest.mark.asyncio
async def test_fix_suggestions_groups_by_fingerprint_and_uses_heuristics() -> None:
    now = datetime.now(UTC)
    rows = [
        {
            "id": 1,
            "message": "invalid literal for int() with base 10: 'foo'",
            "exception_type": "ValueError",
            "stacktrace": "File \"/app/main.py\", line 10, in func",
            "received_at": now - timedelta(minutes=5),
            "level": "error",
            "project_id": 1,
        },
        {
            "id": 2,
            "message": "invalid literal for int() with base 10: 'foo'",
            "exception_type": "ValueError",
            "stacktrace": "File \"/app/main.py\", line 20, in func",
            "received_at": now - timedelta(minutes=1),
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
    )

    assert len(suggestions) == 1
    s = suggestions[0]
    assert s.occurrences == 2
    assert "conversão" in s.title.lower()
    assert s.sample_event_id == 2


def test_heuristic_mapping_valueerror() -> None:
    title, summary, cause, fix, conf = map_exception_to_heuristic(
        "ValueError",
        "invalid literal",
        lang="pt-BR",
    )
    assert "conversão" in title.lower()
    assert conf >= 0.7

