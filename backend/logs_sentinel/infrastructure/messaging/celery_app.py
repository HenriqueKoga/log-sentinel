from __future__ import annotations

from celery import Celery

from logs_sentinel.infrastructure.settings.config import settings


def create_celery_app() -> Celery:
    """Create the Celery application used by workers and API."""

    app = Celery(
        "logs_sentinel",
        broker=settings.broker_url,
        backend=settings.celery_result_backend,
    )
    app.conf.update(
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone="UTC",
        enable_utc=True,
    )
    app.autodiscover_tasks(["logs_sentinel.workers.tasks"])
    return app


celery_app = create_celery_app()
