"""Celery tasks related to log ingestion."""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

from celery import shared_task

from logs_sentinel.application.services.issue_service import IssueService, NewOccurrenceInput
from logs_sentinel.domains.identity.entities import TenantId
from logs_sentinel.domains.ingestion.entities import ProjectId
from logs_sentinel.domains.issues.entities import IssueSeverity
from logs_sentinel.infrastructure.db.base import SessionFactory
from logs_sentinel.infrastructure.db.repositories.issues import (
    IssueOccurrencesRepositorySQLAlchemy,
    IssueRepositorySQLAlchemy,
)


@shared_task(name="logs_sentinel.workers.tasks.process_ingest_batch")  # type: ignore[untyped-decorator]
def process_ingest_batch(payload: dict[str, Any]) -> None:
    """Celery task: process an ingestion batch into issues and buckets."""

    async def _run() -> None:
        async with SessionFactory() as session:
            for event in payload["events"]:
                repo = IssueRepositorySQLAlchemy(session)
                buckets_repo = IssueOccurrencesRepositorySQLAlchemy(session)
                service = IssueService(repo, buckets_repo)
                occurred_at = datetime.fromisoformat(event["received_at"])
                input_data = NewOccurrenceInput(
                    message=event["message"],
                    exception_type=event.get("exception_type"),
                    stacktrace=event.get("stacktrace"),
                    severity=IssueSeverity.ERROR,
                    occurred_at=occurred_at,
                )
                await service.record_occurrence(
                    tenant_id=TenantId(event["tenant_id"]),
                    project_id=ProjectId(event["project_id"]),
                    input=input_data,
                )
            await session.commit()

    asyncio.run(_run())

