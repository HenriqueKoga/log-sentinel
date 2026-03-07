"""Tests for utils.lang."""

from __future__ import annotations

from logs_sentinel.utils.lang import resolved_lang


def test_resolved_lang_query_wins() -> None:
    assert resolved_lang("en", "pt-BR,en;q=0.9") == "en"


def test_resolved_lang_accept_language_used_when_lang_empty() -> None:
    assert resolved_lang("", "pt-BR") == "pt-BR"


def test_resolved_lang_accept_language_first_value() -> None:
    assert resolved_lang(None, "en-US,en;q=0.9,pt;q=0.8") == "en-US"


def test_resolved_lang_default_pt_br() -> None:
    assert resolved_lang(None, None) == "pt-BR"


def test_resolved_lang_strips_whitespace() -> None:
    assert resolved_lang("  en  ", None) == "en"
