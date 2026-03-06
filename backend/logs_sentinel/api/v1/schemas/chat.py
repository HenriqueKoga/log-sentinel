"""Schemas for Log Chat API."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class CreateSessionBody(BaseModel):
    project_id: int | None = None
    title: str | None = None


class SessionOut(BaseModel):
    id: int
    tenant_id: int
    project_id: int | None
    title: str
    created_at: datetime


class SessionsListResponse(BaseModel):
    items: list[SessionOut]


class MessageOut(BaseModel):
    id: int
    session_id: int
    role: str
    content: str
    created_at: datetime
    metadata_json: dict[str, Any] | None = None


class MessagesListResponse(BaseModel):
    items: list[MessageOut]


class SendMessageBody(BaseModel):
    content: str
