"""Language/locale resolution utilities."""

from __future__ import annotations


def resolved_lang(
    lang: str | None,
    accept_language: str | None,
) -> str:
    """Resolve language: query param wins, then first Accept-Language value, default pt-BR."""
    return (lang or "").strip() or (accept_language or "").split(",")[0].strip() or "pt-BR"
