"""Pydantic AI agent for structured fix suggestion (title, summary, cause, fix, etc.)."""

from __future__ import annotations

from pydantic_ai import Agent

from logs_sentinel.infrastructure.agents.schemas import FixSuggestionOutput


def create_suggest_fix_agent(model: str = "gpt-4o-mini") -> Agent[None, FixSuggestionOutput]:
    """Create agent that produces structured fix suggestion (uses API key from settings)."""
    from pydantic_ai.models.openai import OpenAIChatModel

    openai_model = OpenAIChatModel(model)
    agent = Agent(
        openai_model,
        output_type=FixSuggestionOutput,
        system_prompt=(
            "You are an experienced software engineer and observability expert. "
            "Given an error cluster (same fingerprint) with example messages and optionally a stack trace, "
            "produce a structured fix suggestion: title, summary, probable_cause, suggested_fix, "
            "code_snippet (optional or null), language, confidence (0-1). "
            "Respond in the language indicated in the user message (e.g. pt-BR or en)."
        ),
    )
    return agent
