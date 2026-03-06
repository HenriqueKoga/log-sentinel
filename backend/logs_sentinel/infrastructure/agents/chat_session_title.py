"""Pydantic AI agent for generating short, human-friendly chat session titles."""

from __future__ import annotations

from pydantic_ai import Agent

from logs_sentinel.infrastructure.agents.schemas import ChatSessionTitleOutput

__all__ = ["ChatSessionTitleOutput", "create_chat_session_title_agent"]


def create_chat_session_title_agent(model: str = "gpt-4o-mini") -> Agent[None, ChatSessionTitleOutput]:
    """Create agent that suggests a concise title for a chat session."""
    from pydantic_ai.models.openai import OpenAIChatModel

    openai_model = OpenAIChatModel(model)
    agent = Agent(
        openai_model,
        output_type=ChatSessionTitleOutput,
        system_prompt=(
            "You are an assistant that writes very short, meaningful titles for log analysis chat sessions.\n"
            "- Input: the first user message and possibly a brief description of the context.\n"
            "- Output: a single concise title (ideally under 80 characters), without quotes, emojis, or markdown.\n"
            "- The title should be in the same language as the input (pt-BR or en).\n"
        ),
    )
    return agent

