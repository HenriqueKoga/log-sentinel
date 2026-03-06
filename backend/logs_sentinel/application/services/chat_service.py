"""Orchestrates Log Chat: sessions, messages, Pydantic AI agent with tools (streaming)."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any

from logs_sentinel.application.services.chat_tools_service import ChatToolsService
from logs_sentinel.domains.chat.entities import ChatMessage, ChatSession
from logs_sentinel.domains.chat.repositories import (
    ChatMessageRepository,
    ChatSessionRepository,
)
from logs_sentinel.infrastructure.agents.chat import ChatAgentDeps

if TYPE_CHECKING:
    from pydantic_ai import Agent


class ChatService:
    """Log Chat orchestration: sessions, messages, Pydantic AI agent with tools (streaming)."""

    def __init__(
        self,
        session_repo: ChatSessionRepository,
        message_repo: ChatMessageRepository,
        tools_service: ChatToolsService,
        agent: Agent[ChatAgentDeps, str],
        billing_service: Any | None,
        title_agent: Any | None = None,
    ) -> None:
        self._session_repo = session_repo
        self._message_repo = message_repo
        self._tools = tools_service
        self._agent = agent
        self._billing = billing_service
        self._title_agent = title_agent

    async def create_session(
        self,
        *,
        tenant_id: int,
        user_id: int,
        project_id: int | None,
        title: str = "",
    ) -> ChatSession:
        return await self._session_repo.create(
            tenant_id=tenant_id,
            user_id=user_id,
            project_id=project_id,
            title=title or "",
        )

    async def list_sessions(
        self,
        *,
        tenant_id: int,
        user_id: int,
        project_id: int | None,
        limit: int = 50,
    ) -> list[ChatSession]:
        return list(
            await self._session_repo.list_sessions(
                tenant_id=tenant_id,
                user_id=user_id,
                project_id=project_id,
                limit=limit,
            )
        )

    async def get_session(
        self, session_id: int, tenant_id: int, user_id: int
    ) -> ChatSession | None:
        return await self._session_repo.get_by_id(
            session_id=session_id, tenant_id=tenant_id, user_id=user_id
        )

    async def delete_session(
        self, session_id: int, tenant_id: int, user_id: int
    ) -> bool:
        return await self._session_repo.delete(
            session_id=session_id, tenant_id=tenant_id, user_id=user_id
        )

    async def get_messages(
        self, session_id: int, tenant_id: int, user_id: int
    ) -> list[ChatMessage]:
        return list(
            await self._message_repo.get_messages(
                session_id=session_id, tenant_id=tenant_id, user_id=user_id
            )
        )

    async def send_message(
        self,
        session_id: int,
        tenant_id: int,
        user_id: int,
        project_id: int | None,
        content: str,
        lang: str = "pt-BR",
        stream: bool = False,
    ) -> ChatMessage | AsyncIterator[str]:
        session = await self._session_repo.get_by_id(session_id, tenant_id, user_id)
        if session is None:
            raise ValueError("SESSION_NOT_FOUND")
        await self._message_repo.add_message(
            session_id=session_id,
            role="user",
            content=content,
        )
        return await self._reply_with_llm(
            session=session,
            project_id=project_id,
            content=content,
            lang=lang,
            stream=stream,
        )

    async def _reply_with_llm(
        self,
        session: ChatSession,
        project_id: int | None,
        content: str,
        lang: str,
        stream: bool,
    ) -> ChatMessage | AsyncIterator[str]:
        history = await self._message_repo.get_messages(
            session_id=session.id,
            tenant_id=session.tenant_id,
            user_id=session.user_id,
        )
        history_lines: list[str] = []
        for m in history:
            if m.role == "user":
                history_lines.append(f"User: {m.content}")
            elif m.role == "assistant":
                history_lines.append(f"Assistant: {m.content}")
        history_text = "\n".join(history_lines) if history_lines else ""

        deps = ChatAgentDeps(
            tenant_id=session.tenant_id,
            project_id=project_id,
            tools=self._tools,
            history_text=history_text,
            lang=lang,
        )

        if stream:
            return self._stream_agent_reply(session, content, deps)
        return await self._run_agent_and_persist(session, content, deps)

    async def _run_agent_and_persist(
        self,
        session: ChatSession,
        content: str,
        deps: ChatAgentDeps,
    ) -> ChatMessage:
        result = await self._agent.run(content, deps=deps)
        full_content = (result.output or "").strip() or "Não consegui gerar uma resposta."
        if self._billing:
            from logs_sentinel.domains.identity.entities import TenantId
            await self._billing.record_llm_usage(TenantId(session.tenant_id))
        msg = await self._message_repo.add_message(
            session_id=session.id,
            role="assistant",
            content=full_content,
        )
        await self._maybe_update_session_title(session, content)
        return msg

    async def _stream_agent_reply(
        self,
        session: ChatSession,
        content: str,
        deps: ChatAgentDeps,
    ) -> AsyncIterator[str]:
        full_content_parts: list[str] = []
        async with self._agent.run_stream(content, deps=deps) as streamed:
            try:
                async for chunk in streamed.stream_text(delta=True):
                    full_content_parts.append(chunk)
                    yield f"data: {json.dumps({'delta': chunk})}\n\n"
            except Exception:
                pass
        full_content = "".join(full_content_parts).strip() or "Não consegui gerar uma resposta."
        if self._billing:
            from logs_sentinel.domains.identity.entities import TenantId
            await self._billing.record_llm_usage(TenantId(session.tenant_id))
        assistant_msg = await self._message_repo.add_message(
            session_id=session.id,
            role="assistant",
            content=full_content,
        )
        await self._maybe_update_session_title(session, content)
        yield f"data: {json.dumps({'done': True, 'message_id': assistant_msg.id})}\n\n"

    async def _maybe_update_session_title(
        self, session: ChatSession, first_user_message: str
    ) -> None:
        """If session has no title and title agent is available, generate and persist one."""
        if not session.title.strip() and self._title_agent is not None:
            try:
                result = await self._title_agent.run(first_user_message)
                if result.output and result.output.title.strip():
                    await self._session_repo.update_title(
                        session_id=session.id,
                        tenant_id=session.tenant_id,
                        user_id=session.user_id,
                        title=result.output.title.strip(),
                    )
                    if self._billing:
                        from logs_sentinel.domains.identity.entities import TenantId
                        await self._billing.record_llm_usage(TenantId(session.tenant_id))
            except Exception:
                pass
