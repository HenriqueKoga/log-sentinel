"""Celery-based ingest queue implementation."""

from __future__ import annotations

from typing import Any

from logs_sentinel.infrastructure.messaging.celery_app import celery_app


class CeleryIngestQueue:
    """Enqueues ingest batches to Celery for async processing."""

    async def enqueue_batch(
        self, tenant_id: Any, project_id: Any, token_id: Any, events: Any
    ) -> str:
        result = celery_app.send_task(
            "logs_sentinel.workers.tasks.process_ingest_batch",
            args=[
                {
                    "tenant_id": int(tenant_id),
                    "project_id": int(project_id),
                    "token_id": int(token_id),
                    "events": events,
                }
            ],
        )
        return str(result.id)
