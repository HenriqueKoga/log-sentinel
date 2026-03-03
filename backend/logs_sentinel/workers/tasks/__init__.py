"""Celery tasks package.

Re-exports tasks from submodules so Celery can refer to
``logs_sentinel.workers.tasks.<task_name>``.
"""

from .ingest import process_ingest_batch as process_ingest_batch

