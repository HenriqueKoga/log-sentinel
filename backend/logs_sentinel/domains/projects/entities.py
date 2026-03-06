"""Project entities."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import NewType

from logs_sentinel.domains.identity.entities import TenantId

ProjectId = NewType("ProjectId", int)


@dataclass(slots=True)
class Project:
    """Represents an application or service that sends logs."""

    id: ProjectId
    tenant_id: TenantId
    name: str
    created_at: datetime
