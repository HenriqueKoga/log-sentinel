"""Tests for NullLLMClient (placeholder when LLM is disabled)."""

from __future__ import annotations

import pytest

from logs_sentinel.infrastructure.llm.null_client import NullLLMClient


@pytest.mark.asyncio
async def test_suggest_fix_returns_placeholder_en() -> None:
    client = NullLLMClient()
    result = await client.suggest_fix(
        fingerprint="fp1",
        sample_messages=["Error message"],
        stacktrace="line 1",
        lang="en",
    )
    assert result.title == "LLM disabled"
    assert "disabled" in result.summary.lower()
    assert result.confidence == 0.5
    assert result.code_snippet is None


@pytest.mark.asyncio
async def test_suggest_fix_returns_placeholder_pt() -> None:
    client = NullLLMClient()
    result = await client.suggest_fix(
        fingerprint="fp1",
        sample_messages=[],
        stacktrace=None,
        lang="pt-BR",
    )
    assert result.title == "LLM desabilitado"
    assert "desabilitada" in result.summary.lower() or "desabilitado" in result.title.lower()


@pytest.mark.asyncio
async def test_enrich_issue_returns_placeholder() -> None:
    client = NullLLMClient()
    result = await client.enrich_issue([{"message": "error"}])
    assert result.model_name == "null-llm"
    assert "disabled" in result.summary.lower() or "LLM" in result.summary
    assert len(result.checklist_json) >= 1


@pytest.mark.asyncio
async def test_suggest_issue_returns_placeholder() -> None:
    client = NullLLMClient()
    result = await client.suggest_issue("Some context")
    assert result.title == "Some context" or "Manual" in result.title
    assert result.severity == "medium"


@pytest.mark.asyncio
async def test_chat_with_tools_returns_placeholder() -> None:
    client = NullLLMClient()
    msg, tools_calls = await client.chat_with_tools([], [], lang="en")
    assert "disabled" in msg.lower() or "AI chat" in msg
    assert tools_calls == []
