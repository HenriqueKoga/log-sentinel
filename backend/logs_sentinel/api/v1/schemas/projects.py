from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ProjectCreateRequest(BaseModel):
    name: str = Field(..., max_length=255)


class ProjectResponse(BaseModel):
    id: int
    name: str
    created_at: datetime


class IngestTokenResponse(BaseModel):
    id: int
    token: str
    last_used_at: datetime | None
    revoked_at: datetime | None

