"""Log Chat API router."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated, cast

from fastapi import APIRouter, Body, Depends, Header, HTTPException, Query, Response, status
from fastapi.responses import JSONResponse, StreamingResponse

from logs_sentinel.api.v1.dependencies.auth import TenantContext, get_tenant_context
from logs_sentinel.api.v1.dependencies.services import get_billing_service, get_chat_service
from logs_sentinel.api.v1.schemas.chat import (
    CreateSessionBody,
    MessageOut,
    MessagesListResponse,
    SendMessageBody,
    SessionOut,
    SessionsListResponse,
)
from logs_sentinel.application.services.billing_service import BillingService
from logs_sentinel.application.services.chat_service import ChatService
from logs_sentinel.domains.chat.entities import ChatMessage
from logs_sentinel.domains.identity.entities import TenantId
from logs_sentinel.utils.lang import resolved_lang

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/sessions", response_model=SessionOut)
async def create_chat_session(
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    service: Annotated[ChatService, Depends(get_chat_service)],
    billing: Annotated[BillingService, Depends(get_billing_service)],
    body: Annotated[CreateSessionBody, Body()],
) -> SessionOut:
    if not await billing.is_llm_enabled(ctx.tenant_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "LLM_DISABLED", "message": "Chat requires LLM to be enabled in your plan."},
        )
    tenant_id = int(ctx.tenant_id)
    user_id = int(ctx.user_id)
    session = await service.create_session(
        tenant_id=tenant_id,
        user_id=user_id,
        project_id=body.project_id,
        title=body.title or "",
    )
    return SessionOut(
        id=session.id,
        tenant_id=session.tenant_id,
        project_id=session.project_id,
        title=session.title,
        created_at=session.created_at,
    )


@router.get("/sessions", response_model=SessionsListResponse)
async def list_chat_sessions(
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    service: Annotated[ChatService, Depends(get_chat_service)],
    billing: Annotated[BillingService, Depends(get_billing_service)],
    project_id: Annotated[int | None, Query()] = None,
) -> SessionsListResponse:
    if not await billing.is_llm_enabled(ctx.tenant_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "LLM_DISABLED", "message": "Chat requires LLM to be enabled in your plan."},
        )
    tenant_id = int(ctx.tenant_id)
    user_id = int(ctx.user_id)
    sessions = await service.list_sessions(
        tenant_id=tenant_id,
        user_id=user_id,
        project_id=project_id,
    )
    return SessionsListResponse(
        items=[
            SessionOut(
                id=s.id,
                tenant_id=s.tenant_id,
                project_id=s.project_id,
                title=s.title,
                created_at=s.created_at,
            )
            for s in sessions
        ]
    )


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_chat_session(
    session_id: int,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    service: Annotated[ChatService, Depends(get_chat_service)],
    billing: Annotated[BillingService, Depends(get_billing_service)],
) -> None:
    if not await billing.is_llm_enabled(ctx.tenant_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "LLM_DISABLED", "message": "Chat requires LLM to be enabled in your plan."},
        )
    tenant_id = int(ctx.tenant_id)
    user_id = int(ctx.user_id)
    deleted = await service.delete_session(
        session_id=session_id,
        tenant_id=tenant_id,
        user_id=user_id,
    )
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "CHAT_SESSION_NOT_FOUND"},
        )


@router.get("/sessions/{session_id}/messages", response_model=MessagesListResponse)
async def get_chat_messages(
    session_id: int,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    service: Annotated[ChatService, Depends(get_chat_service)],
    billing: Annotated[BillingService, Depends(get_billing_service)],
) -> MessagesListResponse:
    if not await billing.is_llm_enabled(ctx.tenant_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "LLM_DISABLED", "message": "Chat requires LLM to be enabled in your plan."},
        )
    tenant_id = int(ctx.tenant_id)
    user_id = int(ctx.user_id)
    messages = await service.get_messages(
        session_id=session_id, tenant_id=tenant_id, user_id=user_id
    )
    return MessagesListResponse(
        items=[
            MessageOut(
                id=m.id,
                session_id=m.session_id,
                role=m.role,
                content=m.content,
                created_at=m.created_at,
                metadata_json=m.metadata_json,
            )
            for m in messages
        ]
    )


@router.post("/sessions/{session_id}/messages")
async def post_chat_message(
    session_id: int,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    service: Annotated[ChatService, Depends(get_chat_service)],
    billing: Annotated[BillingService, Depends(get_billing_service)],
    body: Annotated[SendMessageBody, Body()],
    stream: Annotated[bool, Query()] = False,
    lang: Annotated[str | None, Query()] = None,
    accept_language: Annotated[str | None, Header(convert_underscores=False)] = None,
) -> Response:
    if not await billing.is_llm_enabled(ctx.tenant_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "LLM_DISABLED", "message": "Chat requires LLM to be enabled in your plan."},
        )
    tenant_id = int(ctx.tenant_id)
    user_id = int(ctx.user_id)
    chat_session = await service.get_session(session_id, tenant_id, user_id)
    if chat_session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "CHAT_SESSION_NOT_FOUND"},
        )
    if await billing.would_exceed_llm_limit(TenantId(ctx.tenant_id)):
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={"code": "USAGE_LIMIT_EXCEEDED", "message": "Credit limit reached. Upgrade or wait for the next period."},
        )
    lang_resolved = resolved_lang(lang, accept_language)
    try:
        result = await service.send_message(
            session_id=session_id,
            tenant_id=tenant_id,
            user_id=user_id,
            project_id=chat_session.project_id,
            content=body.content,
            lang=lang_resolved,
            stream=stream,
        )
    except ValueError as e:
        if str(e) == "SESSION_NOT_FOUND":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "CHAT_SESSION_NOT_FOUND"},
            ) from e
        if str(e) == "USAGE_LIMIT_EXCEEDED":
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail={"code": "USAGE_LIMIT_EXCEEDED", "message": "Credit limit reached."},
            ) from e
        raise
    if stream:
        return StreamingResponse(
            cast(AsyncIterator[str], result),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )
    msg = cast(ChatMessage, result)
    msg_out = MessageOut(
        id=msg.id,
        session_id=msg.session_id,
        role=msg.role,
        content=msg.content,
        created_at=msg.created_at,
        metadata_json=msg.metadata_json,
    )
    return JSONResponse(content=msg_out.model_dump(mode="json"))
