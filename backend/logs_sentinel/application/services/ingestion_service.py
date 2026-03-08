from __future__ import annotations

from asyncio import TaskGroup
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol

from logs_sentinel.domains.identity.entities import TenantId
from logs_sentinel.domains.ingestion.entities import (
    IngestToken,
    LogEvent,
    LogEventId,
    LogLevel,
    ProjectId,
    hash_ingest_token,
)
from logs_sentinel.domains.ingestion.normalization import (
    NormalizedLog,
    compute_fingerprint,
    normalize_message,
)
from logs_sentinel.domains.ingestion.repositories import IngestTokenRepository
from logs_sentinel.domains.logs.repositories import LogsRepository


@dataclass(slots=True)
class IngestEventInput:
    """Single event within an ingestion batch."""

    level: str
    message: str
    exception_type: str | None
    stacktrace: str | None
    raw: dict[str, Any]


@dataclass(slots=True)
class IngestBatchResult:
    """Result of an accepted ingestion batch."""

    batch_id: str
    accepted_count: int


class RateLimiter(Protocol):
    """Rate limiter abstraction for ingestion."""

    async def check_and_increment(self, key: str, limit: int, window_seconds: int) -> bool:
        """
        Return True when under limit and increment usage, False when rate-limited.
        """


class IngestQueue(Protocol):
    """Abstraction over messaging system used to enqueue ingestion batches."""

    async def enqueue_batch(
        self,
        tenant_id: TenantId,
        project_id: ProjectId,
        token_id: int,
        events: Sequence[dict[str, Any]],
    ) -> str:
        """
        Enqueue a batch of events for background processing and return a batch id.
        """


class IngestionService:
    """Application service for validating and enqueuing ingestion batches."""

    def __init__(
        self,
        token_repo: IngestTokenRepository,
        log_repo: LogsRepository,
        rate_limiter: RateLimiter,
        queue: IngestQueue,
        per_token_limit_per_minute: int = 5_000,
        usage_checker: Any | None = None,
    ) -> None:
        self._token_repo = token_repo
        self._log_repo = log_repo
        self._rate_limiter = rate_limiter
        self._queue = queue
        self._per_token_limit_per_minute = per_token_limit_per_minute
        self._usage_checker = usage_checker

    async def resolve_token(self, token_value: str) -> IngestToken:
        hashed = hash_ingest_token(token_value)
        token = await self._token_repo.get_by_token_hash(hashed)
        if not token or not token.is_active:
            raise ValueError("INGEST_INVALID_TOKEN")
        await self._token_repo.touch_last_used(token.id)
        return token

    async def ingest_batch(
        self,
        token: IngestToken,
        events: Sequence[IngestEventInput],
    ) -> IngestBatchResult:
        """Validate payload, enforce rate limits, and enqueue background processing."""

        if not events:
            raise ValueError("INGEST_EMPTY_BATCH")

        if self._usage_checker is not None:
            await self._usage_checker.increment_events(
                tenant_id=token.tenant_id,
                events=len(events),
            )

        rl_key = f"ingest:{int(token.id)}"
        allowed = await self._rate_limiter.check_and_increment(
            rl_key,
            limit=self._per_token_limit_per_minute,
            window_seconds=60,
        )
        if not allowed:
            raise ValueError("INGEST_RATE_LIMITED")

        now = datetime.now(tz=UTC)
        async with TaskGroup() as tg:
            tasks = [tg.create_task(self._normalize_for_validation(event)) for event in events]
        _ = [task.result() for task in tasks]

        raw_events: list[dict[str, Any]] = []
        events_for_db: list[LogEvent] = []
        for event in events:
            raw_events.append(
                {
                    "tenant_id": int(token.tenant_id),
                    "project_id": int(token.project_id),
                    "received_at": now.isoformat(),
                    "level": event.level,
                    "message": event.message,
                    "exception_type": event.exception_type,
                    "stacktrace": event.stacktrace,
                    "raw_json": event.raw,
                }
            )
            events_for_db.append(
                LogEvent(
                    id=LogEventId(0),
                    tenant_id=token.tenant_id,
                    project_id=token.project_id,
                    received_at=now,
                    level=LogLevel(event.level),
                    message=event.message,
                    exception_type=event.exception_type,
                    stacktrace=event.stacktrace,
                    raw_json=event.raw,
                )
            )

        await self._log_repo.create_many(events_for_db)

        batch_id = await self._queue.enqueue_batch(
            tenant_id=token.tenant_id,
            project_id=token.project_id,
            token_id=int(token.id),
            events=raw_events,
        )

        return IngestBatchResult(batch_id=batch_id, accepted_count=len(events))

    async def _normalize_for_validation(self, event: IngestEventInput) -> NormalizedLog:
        try:
            level = LogLevel(event.level)
        except ValueError as exc:
            raise ValueError("INGEST_INVALID_LEVEL") from exc

        if not event.message:
            raise ValueError("INGEST_EMPTY_MESSAGE")

        normalized_message = normalize_message(event.message)
        frames: list[str] | None = None
        if event.stacktrace:
            frames = event.stacktrace.splitlines()

        fingerprint = compute_fingerprint(
            normalized_message=normalized_message,
            exception_type=event.exception_type,
            stack_frames=frames,
        )

        # The level is validated but not used to compute fingerprint here.
        _ = level
        return NormalizedLog(normalized_message=normalized_message, fingerprint=fingerprint)
