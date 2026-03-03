from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any, NewType

from logs_sentinel.domains.identity.entities import TenantId

ProjectId = NewType("ProjectId", int)
IngestTokenId = NewType("IngestTokenId", int)
LogEventId = NewType("LogEventId", int)


class LogLevel(StrEnum):
    """Log severity levels supported by ingestion."""

    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass(slots=True)
class Project:
    """Represents an application or service that sends logs."""

    id: ProjectId
    tenant_id: TenantId
    name: str
    created_at: datetime


@dataclass(slots=True)
class IngestToken:
    """Token used to authenticate ingestion requests for a project."""

    id: IngestTokenId
    tenant_id: TenantId
    project_id: ProjectId
    token_hash: str
    last_used_at: datetime | None
    revoked_at: datetime | None

    @property
    def is_active(self) -> bool:
        return self.revoked_at is None


@dataclass(slots=True)
class LogEvent:
    """Raw log event as ingested before processing."""

    id: LogEventId
    tenant_id: TenantId
    project_id: ProjectId
    received_at: datetime
    level: LogLevel
    message: str
    exception_type: str | None
    stacktrace: str | None
    raw_json: dict[str, Any]

