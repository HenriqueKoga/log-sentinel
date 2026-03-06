"""Pydantic AI agent for suggesting issue title and severity from context."""

from __future__ import annotations

from pydantic_ai import Agent

from logs_sentinel.infrastructure.agents.schemas import SuggestIssueOutput


def create_suggest_issue_agent(model: str = "gpt-4o-mini") -> Agent[None, SuggestIssueOutput]:
    """Create agent that suggests issue title and severity (uses API key from settings)."""
    from pydantic_ai.models.openai import OpenAIChatModel

    openai_model = OpenAIChatModel(model)
    agent = Agent(
        openai_model,
        output_type=SuggestIssueOutput,
        system_prompt=(
            "You are an assistant for engineers triaging issues. Given error or issue context, "
            "respond with a short issue title (max 200 chars) and severity: one of low, medium, high, critical."
        ),
    )
    return agent
