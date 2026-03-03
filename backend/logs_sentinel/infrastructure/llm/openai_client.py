from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

import httpx

from logs_sentinel.domains.ai.entities import IssueEnrichment, IssueEnrichmentId, LLMClientProtocol
from logs_sentinel.domains.identity.entities import TenantId
from logs_sentinel.domains.issues.entities import IssueId
from logs_sentinel.infrastructure.settings.config import settings


class OpenAILLMClient(LLMClientProtocol):
    """LLM client backed by OpenAI's chat completion API."""

    def __init__(self, api_key: str | None = None, model: str = "gpt-4o-mini") -> None:
        self._api_key = api_key or settings.openai_api_key
        self._model = model
        self._client = httpx.AsyncClient(
            base_url="https://api.openai.com/v1",
            headers={"Authorization": f"Bearer {self._api_key}"},
        )

    async def enrich_issue(self, events: Sequence[dict[str, object]]) -> IssueEnrichment:
        """Call OpenAI to generate an enrichment summary from recent events."""

        # Build a compact textual representation of events.
        lines: list[str] = []
        for ev in events:
            line = f"[{ev.get('received_at')}] {ev.get('level')} {ev.get('message')}"
            if ev.get("exception_type"):
                line += f" ({ev.get('exception_type')})"
            lines.append(line)
        joined = "\n".join(lines[-20:])

        prompt = (
            "You are an assistant helping engineers triage production issues.\n"
            "Given the following recent error events, produce:\n"
            "1) A 2-3 sentence summary of what is happening.\n"
            "2) The most likely root cause in one sentence.\n"
            "3) A short checklist (3-6 items) of concrete steps to investigate or fix.\n\n"
            "Events:\n"
            f"{joined}\n"
        )

        response = await self._client.post(
            "/chat/completions",
            json={
                "model": self._model,
                "messages": [
                    {"role": "system", "content": "You are a senior SRE assistant."},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.2,
            },
            timeout=15.0,
        )
        response.raise_for_status()
        data = response.json()
        content: str = data["choices"][0]["message"]["content"]

        # For simplicity, treat the whole content as summary and derive a basic checklist.
        summary = content.strip()
        suspected_cause = "See summary for suspected root cause based on the AI analysis."
        checklist = [
            "Inspect recent deployments around the time of the spike.",
            "Review application logs for correlated errors.",
            "Check configuration and feature flags recently changed.",
        ]

        return IssueEnrichment(
            id=IssueEnrichmentId(-1),
            tenant_id=TenantId(-1),
            issue_id=IssueId(-1),
            model_name=self._model,
            summary=summary,
            suspected_cause=suspected_cause,
            checklist_json=checklist,
            created_at=datetime.now(tz=UTC),
        )

