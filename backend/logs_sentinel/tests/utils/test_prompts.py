"""Tests for utils.prompts."""

from __future__ import annotations

from logs_sentinel.utils.prompts import build_suggest_fix_prompt


def test_build_suggest_fix_prompt_includes_fingerprint() -> None:
    out = build_suggest_fix_prompt(
        fingerprint="abc123",
        sample_messages=[],
        stacktrace=None,
        lang="en",
    )
    assert "abc123" in out
    assert "Fingerprint" in out


def test_build_suggest_fix_prompt_includes_sample_messages() -> None:
    out = build_suggest_fix_prompt(
        fingerprint="fp",
        sample_messages=["error one", "error two"],
        stacktrace=None,
        lang="en",
    )
    assert "error one" in out
    assert "error two" in out
    assert "Sample messages" in out


def test_build_suggest_fix_prompt_includes_stacktrace() -> None:
    out = build_suggest_fix_prompt(
        fingerprint="fp",
        sample_messages=[],
        stacktrace="File \"x.py\", line 1",
        lang="en",
    )
    assert "x.py" in out
    assert "Stacktrace" in out


def test_build_suggest_fix_prompt_lang_pt() -> None:
    out = build_suggest_fix_prompt(
        fingerprint="fp",
        sample_messages=[],
        stacktrace=None,
        lang="pt-BR",
    )
    assert "pt-BR" in out


def test_build_suggest_fix_prompt_lang_en() -> None:
    out = build_suggest_fix_prompt(
        fingerprint="fp",
        sample_messages=[],
        stacktrace=None,
        lang="en",
    )
    assert "en" in out


def test_build_suggest_fix_prompt_truncates_stacktrace() -> None:
    long_stack = "x" * 5000
    out = build_suggest_fix_prompt(
        fingerprint="fp",
        sample_messages=[],
        stacktrace=long_stack,
        lang="en",
    )
    assert len(out) < 5000 + 200
