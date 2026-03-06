"""Pydantic AI agent for issue enrichment (summary, suspected_cause, checklist)."""

from __future__ import annotations

from collections.abc import Sequence

from pydantic_ai import Agent

from logs_sentinel.domains.logs.entities import LogEventForTenant
from logs_sentinel.infrastructure.agents.schemas import IssueEnrichmentOutput


def events_to_prompt(events: Sequence[LogEventForTenant]) -> str:
    """Build a single prompt string from log events for the enrichment agent."""
    lines: list[str] = []
    for ev in events:
        line = f"[{ev.received_at.isoformat()}] {ev.level} {ev.message or ''}"
        if ev.exception_type:
            line += f" ({ev.exception_type})"
        lines.append(line)
    return "\n".join(lines[-20:])


def create_issue_enrichment_agent(model: str = "gpt-4o-mini") -> Agent[None, IssueEnrichmentOutput]:
    """Create agent that produces structured issue enrichment (uses API key from settings)."""
    from pydantic_ai.models.openai import OpenAIChatModel

    openai_model = OpenAIChatModel(model)
    agent = Agent(
        openai_model,
        output_type=IssueEnrichmentOutput,
        system_prompt=(
            "You are a senior SRE assistant. Given recent error events, produce a JSON object with: "
            "summary (2-3 sentence summary of what is happening), suspected_cause (most likely root cause in one sentence), "
            "checklist (3-6 concrete steps to investigate or fix the issue)."
        ),
    )
    return agent
