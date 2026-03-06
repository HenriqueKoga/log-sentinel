"""Tests for ingestion domain entities and helpers."""

from __future__ import annotations

from logs_sentinel.domains.ingestion.entities import (
    LogLevel,
    hash_ingest_token,
)


def test_log_level_values() -> None:
    assert LogLevel.DEBUG.value == "debug"
    assert LogLevel.INFO.value == "info"
    assert LogLevel.WARNING.value == "warning"
    assert LogLevel.ERROR.value == "error"
    assert LogLevel.CRITICAL.value == "critical"


def test_log_level_from_string() -> None:
    assert LogLevel("error") == LogLevel.ERROR
    assert LogLevel("info") == LogLevel.INFO


def test_hash_ingest_token_deterministic() -> None:
    raw = "my-secret"
    assert hash_ingest_token(raw) == hash_ingest_token(raw)


def test_hash_ingest_token_hex_length() -> None:
    h = hash_ingest_token("x")
    assert len(h) == 64
    assert all(c in "0123456789abcdef" for c in h)
