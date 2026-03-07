"""Tests for ai_insights heuristics (map_exception_to_heuristic, confidence_from_occurrences)."""

from __future__ import annotations

from logs_sentinel.domains.ai_insights.heuristics import (
    confidence_from_occurrences,
    map_exception_to_heuristic,
)


def test_confidence_from_occurrences_caps_at_one() -> None:
    assert confidence_from_occurrences(0.9, 1000) <= 1.0


def test_confidence_from_occurrences_boost_with_more_occurrences() -> None:
    base = 0.6
    assert confidence_from_occurrences(base, 1) < confidence_from_occurrences(base, 100)


def test_confidence_from_occurrences_zero_occurrences() -> None:
    assert confidence_from_occurrences(0.7, 0) >= 0.7


# --- ValueError / invalid literal (pt-BR and en) ---
def test_heuristic_valueerror_pt_br() -> None:
    title, summary, cause, fix, conf = map_exception_to_heuristic(
        "ValueError", "invalid literal for int()", lang="pt-BR"
    )
    assert "conversão" in title.lower()
    assert conf == 0.8


def test_heuristic_valueerror_en() -> None:
    title, _, _, _, conf = map_exception_to_heuristic(
        "ValueError", "invalid literal", lang="en"
    )
    assert "value" in title.lower() or "conversion" in title.lower()
    assert conf == 0.8


# --- KeyError ---
def test_heuristic_keyerror_pt_br() -> None:
    title, _, _, _, conf = map_exception_to_heuristic(
        "KeyError", "foo", lang="pt-BR"
    )
    assert "campo" in title.lower() or "chave" in title.lower()
    assert conf == 0.8


def test_heuristic_keyerror_message_chave_nao_encontrada() -> None:
    title, _, _, _, _ = map_exception_to_heuristic(
        None, "chave não encontrada no dict", lang="pt-BR"
    )
    assert "campo" in title.lower() or "chave" in title.lower()


# --- ConnectionError ---
def test_heuristic_connection_pt_br() -> None:
    title, _, _, _, conf = map_exception_to_heuristic(
        "ConnectionError", "failed", lang="pt-BR"
    )
    assert "conexão" in title.lower() or "falha" in title.lower()
    assert conf == 0.75


def test_heuristic_connection_message_conexao_recusada() -> None:
    title, _, _, _, _ = map_exception_to_heuristic(
        None, "conexão recusada", lang="pt-BR"
    )
    assert "conexão" in title.lower() or "falha" in title.lower()


# --- Timeout ---
def test_heuristic_timeout_pt_br() -> None:
    title, _, _, _, conf = map_exception_to_heuristic(
        "TimeoutError", "tempo esgotado", lang="pt-BR"
    )
    assert "tempo" in title.lower() or "operação" in title.lower()
    assert conf == 0.75


def test_heuristic_timeout_en() -> None:
    title, _, _, _, _ = map_exception_to_heuristic(
        "TimeoutError", "timeout", lang="en"
    )
    assert "timeout" in title.lower() or "operation" in title.lower()


# --- IntegrityError ---
def test_heuristic_integrityerror_pt_br() -> None:
    title, _, _, _, conf = map_exception_to_heuristic(
        "IntegrityError", "unique constraint violated", lang="pt-BR"
    )
    assert "integridade" in title.lower() or "única" in title.lower()
    assert conf == 0.8


def test_heuristic_integrityerror_message_unique_constraint() -> None:
    title, _, _, _, _ = map_exception_to_heuristic(
        None, "unique constraint on column x", lang="en"
    )
    assert "integrity" in title.lower() or "unique" in title.lower()


# --- ValidationError / pydantic ---
def test_heuristic_validationerror_pt_br() -> None:
    title, _, _, _, conf = map_exception_to_heuristic(
        "ValidationError", "pydantic error", lang="pt-BR"
    )
    assert "validação" in title.lower()
    assert conf == 0.8


def test_heuristic_pydantic_in_message() -> None:
    title, _, _, _, _ = map_exception_to_heuristic(
        None, "pydantic validation failed", lang="en"
    )
    assert "validation" in title.lower() or "data" in title.lower()


# --- Fallback (application error) ---
def test_heuristic_fallback_pt_br() -> None:
    title, summary, cause, fix, conf = map_exception_to_heuristic(
        "SomeUnknownError", "something broke", lang="pt-BR"
    )
    assert "erro" in title.lower()
    assert conf == 0.6


def test_heuristic_fallback_en() -> None:
    title, _, _, _, conf = map_exception_to_heuristic(
        "CustomError", "unknown", lang="en"
    )
    assert "application" in title.lower() or "error" in title.lower()
    assert conf == 0.6


def test_heuristic_lang_fallback_to_en() -> None:
    """Non-pt language falls back to English."""
    title, _, _, _, _ = map_exception_to_heuristic(
        "ValueError", "invalid literal", lang="fr"
    )
    assert "value" in title.lower() or "conversion" in title.lower()


def test_heuristic_empty_lang_falls_back_to_en() -> None:
    """Empty lang is normalized; empty string yields is_ptbr False -> English."""
    title, _, _, _, _ = map_exception_to_heuristic(
        "ValueError", "invalid literal", lang=""
    )
    assert "value" in title.lower() or "conversion" in title.lower()
