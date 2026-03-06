"""Port for chat tools (search_logs, top_errors, error_details). Used by the chat agent."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol


class ChatToolsPort(Protocol):
    """Port for tools used by the Log Chat agent. Implemented by ChatToolsService."""

    async def search_logs(
        self,
        *,
        tenant_id: int,
        project_id: int | None,
        from_dt: datetime | None,
        to_dt: datetime | None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Return recent error log events as JSON-serializable dicts."""
        ...

    async def top_errors(
        self,
        *,
        tenant_id: int,
        project_id: int | None,
        from_dt: datetime | None,
        to_dt: datetime | None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Return top error clusters by fingerprint (count, sample_message, last_seen)."""
        ...

    async def error_details(
        self,
        *,
        tenant_id: int,
        event_id: int,
        project_id: int | None = None,
    ) -> dict[str, Any] | None:
        """Return a single log event by id (tenant-scoped)."""
        ...
