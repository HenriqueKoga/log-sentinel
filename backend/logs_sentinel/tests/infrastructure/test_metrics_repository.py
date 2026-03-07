"""Tests for MetricsRepositorySQLAlchemy (dialect-aware _bucket_exprs and series)."""

from __future__ import annotations

from unittest.mock import MagicMock

from logs_sentinel.infrastructure.db.repositories.metrics import MetricsRepositorySQLAlchemy


def test_bucket_exprs_postgresql_branch() -> None:
    """_bucket_exprs uses PostgreSQL expressions when dialect is postgresql."""
    mock_bind = MagicMock()
    mock_bind.dialect.name = "postgresql"
    mock_session = MagicMock()
    mock_session.get_bind.return_value = mock_bind
    repo = MetricsRepositorySQLAlchemy(mock_session)
    bucket_epoch, ts_expr = repo._bucket_exprs(3600)
    assert bucket_epoch is not None
    assert ts_expr is not None