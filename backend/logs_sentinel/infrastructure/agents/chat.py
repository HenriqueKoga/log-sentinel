"""Pydantic AI agent for Log Chat: tools (search_logs, top_errors, error_details) + streaming."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from pydantic_ai import Agent, RunContext

from logs_sentinel.application.ports.chat_tools import ChatToolsPort
from logs_sentinel.utils.dateutils import parse_dt


@dataclass
class ChatAgentDeps:
    """Dependencies for the chat agent (tenant/project + tools port + optional history)."""

    tenant_id: int
    project_id: int | None
    tools: ChatToolsPort
    history_text: str = ""
    lang: str = "pt-BR"


def _get_system_prompt(ctx: RunContext[ChatAgentDeps]) -> str:
    base = (
        "You are a helpful SRE assistant. You have access to tools to search logs, "
        "get top errors, and get error details. Use them when the user asks about logs or errors. "
    )
    lang = (ctx.deps.lang or "pt-BR").lower()
    base += "Respond in pt-BR." if lang.startswith("pt") else "Respond in English."
    if ctx.deps.history_text:
        base += "\n\nPrevious conversation:\n" + ctx.deps.history_text
    return base


def create_chat_agent(model: str = "gpt-4o-mini") -> Agent[ChatAgentDeps, str]:
    """Create the Log Chat agent with tools (uses OpenAI API key from settings)."""
    from pydantic_ai.models.openai import OpenAIChatModel

    openai_model = OpenAIChatModel(model)
    agent = Agent(
        openai_model,
        deps_type=ChatAgentDeps,
        instructions=_get_system_prompt,
    )

    @agent.tool
    async def search_logs(
        ctx: RunContext[ChatAgentDeps],
        project_id: int | None = None,
        from_dt: str | None = None,
        to_dt: str | None = None,
        limit: int = 50,
    ) -> str:
        """Search recent error/critical logs. Use from_dt and to_dt as ISO datetime strings, or omit for last 24h."""
        now = datetime.now(UTC)
        default_from = now - timedelta(hours=24)
        from_dt_parsed = parse_dt(from_dt) or default_from
        to_dt_parsed = parse_dt(to_dt) or now
        proj_id = project_id if project_id is not None else ctx.deps.project_id
        result = await ctx.deps.tools.search_logs(
            tenant_id=ctx.deps.tenant_id,
            project_id=proj_id,
            from_dt=from_dt_parsed,
            to_dt=to_dt_parsed,
            limit=limit,
        )
        return str(result)

    @agent.tool
    async def top_errors(
        ctx: RunContext[ChatAgentDeps],
        from_dt: str | None = None,
        to_dt: str | None = None,
        limit: int = 20,
    ) -> str:
        """Get top error clusters by fingerprint (count, sample message)."""
        now = datetime.now(UTC)
        default_from = now - timedelta(hours=24)
        from_dt_parsed = parse_dt(from_dt) or default_from
        to_dt_parsed = parse_dt(to_dt) or now
        result = await ctx.deps.tools.top_errors(
            tenant_id=ctx.deps.tenant_id,
            project_id=ctx.deps.project_id,
            from_dt=from_dt_parsed,
            to_dt=to_dt_parsed,
            limit=limit,
        )
        return str(result)

    @agent.tool
    async def error_details(ctx: RunContext[ChatAgentDeps], event_id: int) -> str:
        """Get full details of a single log event by its ID."""
        result = await ctx.deps.tools.error_details(
            tenant_id=ctx.deps.tenant_id,
            event_id=event_id,
            project_id=ctx.deps.project_id,
        )
        return str(result) if result else "Event not found."

    return agent

