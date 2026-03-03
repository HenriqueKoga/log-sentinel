from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from logs_sentinel.api.v1.schemas.ingest import IngestBatchRequest, IngestBatchResponse
from logs_sentinel.application.services.ingestion_service import (
    IngestBatchResult,
    IngestEventInput,
    IngestionService,
)
from logs_sentinel.domains.ingestion.entities import LogEventId
from logs_sentinel.domains.ingestion.repositories import IngestTokenRepository, LogEventRepository
from logs_sentinel.infrastructure.cache.redis_rate_limiter import (
    RedisRateLimiter,
    create_redis_client,
)
from logs_sentinel.infrastructure.db.base import get_session
from logs_sentinel.infrastructure.db.models import IngestTokenModel, LogEventModel
from logs_sentinel.infrastructure.messaging.celery_app import celery_app
from logs_sentinel.infrastructure.settings.config import settings

router = APIRouter(prefix="/ingest", tags=["ingest"])


class LogEventRepositorySQLAlchemy(LogEventRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_many(self, events: Any) -> list[LogEventId]:
        models = [LogEventModel(**event) for event in events]
        self._session.add_all(models)
        await self._session.flush()
        return [LogEventId(m.id) for m in models]


class IngestTokenRepositorySQLAlchemy(IngestTokenRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_tokens(self, tenant_id: Any, project_id: Any) -> Any:
        raise NotImplementedError

    async def create_token(self, tenant_id: Any, project_id: Any, token_hash: str) -> Any:
        raise NotImplementedError

    async def revoke_token(self, tenant_id: Any, token_id: Any) -> None:
        raise NotImplementedError

    async def get_by_token_hash(self, token_hash: str) -> Any:
        result = await self._session.execute(
            IngestTokenModel.__table__.select().where(IngestTokenModel.token_hash == token_hash)
        )
        row = result.first()
        if row is None:
            return None
        model: IngestTokenModel = IngestTokenModel(**row._mapping)
        from logs_sentinel.domains.identity.entities import TenantId
        from logs_sentinel.domains.ingestion.entities import IngestToken, IngestTokenId, ProjectId

        return IngestToken(
            id=IngestTokenId(model.id),
            tenant_id=TenantId(model.tenant_id),
            project_id=ProjectId(model.project_id),
            token_hash=model.token_hash,
            last_used_at=model.last_used_at,
            revoked_at=model.revoked_at,
        )

    async def touch_last_used(self, token_id: Any) -> None:
        model = await self._session.get(IngestTokenModel, token_id)
        if model is None:
            return
        import datetime as _dt

        model.last_used_at = _dt.datetime.now(tz=_dt.UTC)
        await self._session.flush()


class CeleryIngestQueue:
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


async def get_ingestion_service(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> IngestionService:
    redis_client = create_redis_client(settings.redis_url)
    rate_limiter = RedisRateLimiter(redis_client)
    token_repo = IngestTokenRepositorySQLAlchemy(session)
    log_repo = LogEventRepositorySQLAlchemy(session)
    queue = CeleryIngestQueue()
    return IngestionService(
        token_repo=token_repo,
        log_repo=log_repo,
        rate_limiter=rate_limiter,
        queue=queue,
    )


@router.post("", response_model=IngestBatchResponse, status_code=status.HTTP_202_ACCEPTED)
async def ingest(
    payload: IngestBatchRequest,
    service: Annotated[IngestionService, Depends(get_ingestion_service)],
    x_project_token: str | None = Header(default=None, alias="X-Project-Token"),
) -> IngestBatchResponse:
    if not x_project_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "INGEST_MISSING_TOKEN"},
        )

    try:
        token = await service.resolve_token(x_project_token)
        events = [
            IngestEventInput(
                level=e.level,
                message=e.message,
                exception_type=e.exception_type,
                stacktrace=e.stacktrace,
                raw=e.context or {},
            )
            for e in payload.events
        ]
        result: IngestBatchResult = await service.ingest_batch(token, events)
    except ValueError as exc:
        code = str(exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": code},
        ) from None

    return IngestBatchResponse(batch_id=result.batch_id, accepted_count=result.accepted_count)

