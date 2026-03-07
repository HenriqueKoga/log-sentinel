"""Tests for ai_insights fingerprinting (normalize_message, normalize_stacktrace, compute_fingerprint)."""

from __future__ import annotations

from logs_sentinel.domains.ai_insights.fingerprinting import (
    compute_fingerprint,
    normalize_message,
    normalize_stacktrace,
)


def test_normalize_message_replaces_dynamic_parts() -> None:
    msg = "User 123 with id 456e7890-e89b-12d3-a456-426614174000 at /home/foo/file.py at 2026-03-05T10:00:00Z"
    norm = normalize_message(msg)
    assert "<NUMBER>" in norm
    assert "<UUID>" in norm
    assert "<PATH>" in norm
    assert "<TIMESTAMP>" in norm


def test_normalize_stacktrace_drops_line_numbers() -> None:
    raw = "File \"/app/main.py\", line 123, in <module>\n  File \"/app/mod.py\", line 45, in func"
    norm = normalize_stacktrace(raw)
    assert "line 123" not in norm
    assert "line 45" not in norm
    assert "/app/main.py" in norm
    assert "/app/mod.py" in norm


def test_normalize_stacktrace_empty_string() -> None:
    assert normalize_stacktrace("") == ""


def test_compute_fingerprint_deterministic() -> None:
    fp1 = compute_fingerprint("ValueError", "stack", "message")
    fp2 = compute_fingerprint("ValueError", "stack", "message")
    assert fp1 == fp2


def test_compute_fingerprint_different_inputs_different_output() -> None:
    fp1 = compute_fingerprint("ValueError", "stack1", "msg1")
    fp2 = compute_fingerprint("TypeError", "stack2", "msg2")
    assert fp1 != fp2


def test_compute_fingerprint_returns_non_empty_string() -> None:
    fp = compute_fingerprint("E", "s", "m")
    assert isinstance(fp, str)
    assert len(fp) > 0
