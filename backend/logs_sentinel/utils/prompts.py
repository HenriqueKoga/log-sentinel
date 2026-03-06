"""Prompt building helpers for agents."""

from __future__ import annotations


def build_suggest_fix_prompt(
    *,
    fingerprint: str,
    sample_messages: list[str],
    stacktrace: str | None,
    lang: str,
) -> str:
    """Build prompt text for the suggest-fix agent from fingerprint, messages and stacktrace."""
    lines = [f"Fingerprint: {fingerprint}"]
    if sample_messages:
        lines.append("Sample messages:\n" + "\n".join(sample_messages[:10]))
    if stacktrace:
        lines.append("Stacktrace (snippet):\n" + (stacktrace[:4000] or ""))
    system_lang = "pt-BR" if (lang or "").lower().startswith("pt") else "en"
    lines.append(f"Preferred language code: {system_lang}")
    return "\n\n".join(lines)
