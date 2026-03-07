"""Tests for ingestion normalization (normalize_message, compute_fingerprint)."""

from __future__ import annotations

from logs_sentinel.domains.ingestion.normalization import (
    compute_fingerprint,
    normalize_message,
)


def test_normalize_message_replaces_dynamic_parts() -> None:
    msg = "User 123 emailed foo@example.com at 2024-01-01T12:34:56Z path /tmp/file.txt id 550e8400-e29b-41d4-a716-446655440000"
    out = normalize_message(msg)
    assert "<NUMBER>" in out
    assert "<EMAIL>" in out
    assert "<TIMESTAMP>" in out
    assert "<PATH>" in out
    assert "<UUID>" in out


def test_compute_fingerprint_stable_for_equivalent_messages() -> None:
    m1 = normalize_message("Error for user 1")
    m2 = normalize_message("Error for user 2")
    fp1 = compute_fingerprint(m1, exception_type="ValueError", stack_frames=["a", "b"])
    fp2 = compute_fingerprint(m2, exception_type="ValueError", stack_frames=["a", "b"])
    assert fp1 == fp2


def test_compute_fingerprint_different_exception_type() -> None:
    m = normalize_message("Error")
    fp1 = compute_fingerprint(m, exception_type="ValueError", stack_frames=None)
    fp2 = compute_fingerprint(m, exception_type="TypeError", stack_frames=None)
    assert fp1 != fp2


def test_compute_fingerprint_none_stack_frames() -> None:
    m = normalize_message("Error")
    fp = compute_fingerprint(m, exception_type="E", stack_frames=None)
    assert isinstance(fp, str) and len(fp) > 0


def test_compute_fingerprint_empty_exception_type() -> None:
    m = normalize_message("Error")
    fp = compute_fingerprint(m, exception_type=None, stack_frames=["a"])
    assert isinstance(fp, str) and len(fp) > 0
