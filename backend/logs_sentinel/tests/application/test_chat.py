"""Tests for Log Chat: session CRUD, tool routing."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from logs_sentinel.domains.chat.entities import ChatSession


@pytest.mark.asyncio
async def test_chat_session_repo_create_and_list() -> None:
    from logs_sentinel.domains.chat.repositories import ChatSessionRepository

    class InMemoryChatSessionRepo(ChatSessionRepository):
        def __init__(self) -> None:
            self._sessions: list[ChatSession] = []
            self._next_id = 1

        async def create(
            self,
            *,
            tenant_id: int,
            user_id: int,
            project_id: int | None,
            title: str = "",
        ) -> ChatSession:
            now = datetime.now(UTC)
            s = ChatSession(
                id=self._next_id,
                tenant_id=tenant_id,
                user_id=user_id,
                project_id=project_id,
                title=title,
                created_at=now,
            )
            self._next_id += 1
            self._sessions.append(s)
            return s

        async def list_sessions(
            self,
            *,
            tenant_id: int,
            user_id: int,
            project_id: int | None,
            limit: int = 50,
        ) -> list[ChatSession]:
            out = [
                s
                for s in self._sessions
                if s.tenant_id == tenant_id and s.user_id == user_id
            ]
            if project_id is not None:
                out = [s for s in out if s.project_id == project_id]
            out.sort(key=lambda x: x.created_at, reverse=True)
            return out[:limit]

        async def get_by_id(
            self, session_id: int, tenant_id: int, user_id: int
        ) -> ChatSession | None:
            for s in self._sessions:
                if (
                    s.id == session_id
                    and s.tenant_id == tenant_id
                    and s.user_id == user_id
                ):
                    return s
            return None

        async def update_title(
            self,
            *,
            session_id: int,
            tenant_id: int,
            user_id: int,
            title: str,
        ) -> bool:
            for i, s in enumerate(self._sessions):
                if (
                    s.id == session_id
                    and s.tenant_id == tenant_id
                    and s.user_id == user_id
                ):
                    self._sessions[i] = ChatSession(
                        id=s.id,
                        tenant_id=s.tenant_id,
                        user_id=s.user_id,
                        project_id=s.project_id,
                        title=title,
                        created_at=s.created_at,
                    )
                    return True
            return False

        async def delete(
            self,
            *,
            session_id: int,
            tenant_id: int,
            user_id: int,
        ) -> bool:
            for i, s in enumerate(self._sessions):
                if (
                    s.id == session_id
                    and s.tenant_id == tenant_id
                    and s.user_id == user_id
                ):
                    self._sessions.pop(i)
                    return True
            return False

    repo = InMemoryChatSessionRepo()
    s1 = await repo.create(tenant_id=1, user_id=100, project_id=10, title="Chat 1")
    assert s1.id == 1
    assert s1.tenant_id == 1
    assert s1.user_id == 100
    assert s1.project_id == 10
    assert s1.title == "Chat 1"

    s2 = await repo.create(tenant_id=1, user_id=100, project_id=None, title="Chat 2")
    assert s2.id == 2

    sessions = await repo.list_sessions(tenant_id=1, user_id=100, project_id=None)
    assert len(sessions) == 2
    assert sessions[0].id == 2

    sessions_proj = await repo.list_sessions(
        tenant_id=1, user_id=100, project_id=10
    )
    assert len(sessions_proj) == 1
    assert sessions_proj[0].id == 1

    got = await repo.get_by_id(1, 1, 100)
    assert got is not None and got.title == "Chat 1"
    wrong_user = await repo.get_by_id(1, 1, 999)
    assert wrong_user is None
    wrong_tenant = await repo.get_by_id(1, 2, 100)
    assert wrong_tenant is None


@pytest.mark.asyncio
async def test_chat_tools_search_logs_and_top_errors() -> None:
    from logs_sentinel.application.services.chat_tools_service import ChatToolsService
    from logs_sentinel.domains.ai_insights.entities import ErrorLogEvent
    from logs_sentinel.domains.ingestion.entities import LogEventId, ProjectId
    from logs_sentinel.domains.logs.repositories import LogSearchRepository

    now = datetime.now(UTC)
    rows = [
        {
            "id": 1,
            "project_id": 1,
            "message": "ValueError: invalid",
            "exception_type": "ValueError",
            "stacktrace": "line 1",
            "received_at": now - timedelta(minutes=5),
            "level": "error",
        },
        {
            "id": 2,
            "project_id": 1,
            "message": "ValueError: invalid",
            "exception_type": "ValueError",
            "stacktrace": "line 1",
            "received_at": now - timedelta(minutes=1),
            "level": "error",
        },
    ]

    class InMemoryLogSearch(LogSearchRepository):
        def __init__(self, data: list[dict[str, Any]]) -> None:
            self._data = data

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
            for r in self._data[:limit]:
                events.append(
                    ErrorLogEvent(
                        id=LogEventId(r["id"]),
                        project_id=ProjectId(r["project_id"]),
                        message=r["message"],
                        exception_type=r["exception_type"],
                        stacktrace=r["stacktrace"],
                        received_at=r["received_at"],
                        level=r["level"],
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
            for r in self._data:
                if r.get("id") == event_id:
                    return ErrorLogEvent(
                        id=LogEventId(r["id"]),
                        project_id=ProjectId(r["project_id"]),
                        message=r["message"],
                        exception_type=r["exception_type"],
                        stacktrace=r["stacktrace"],
                        received_at=r["received_at"],
                        level=r["level"],
                    )
            return None

    log_search = InMemoryLogSearch(rows)
    tools = ChatToolsService(log_search=log_search)

    search_result = await tools.search_logs(
        tenant_id=1,
        project_id=1,
        from_dt=now - timedelta(hours=1),
        to_dt=now,
        limit=10,
    )
    assert len(search_result) == 2
    assert search_result[0]["message"] == "ValueError: invalid"

    top_result = await tools.top_errors(
        tenant_id=1,
        project_id=1,
        from_dt=now - timedelta(hours=1),
        to_dt=now,
        limit=5,
    )
    assert len(top_result) >= 1
    assert "fingerprint" in top_result[0]
    assert "count" in top_result[0]
    assert top_result[0]["count"] == 2
