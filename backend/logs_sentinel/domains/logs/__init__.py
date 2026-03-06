"""Logs domain (list/detail read model for logs API)."""

from logs_sentinel.domains.logs.entities import LogDetailRow, LogListRow
from logs_sentinel.domains.logs.repositories import LogsRepository

__all__ = ["LogDetailRow", "LogListRow", "LogsRepository"]
