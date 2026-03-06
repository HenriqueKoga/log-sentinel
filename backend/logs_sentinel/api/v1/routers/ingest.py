from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status

from logs_sentinel.api.v1.dependencies.services import get_ingestion_service
from logs_sentinel.api.v1.schemas.ingest import IngestBatchRequest, IngestBatchResponse
from logs_sentinel.application.services.ingestion_service import (
    IngestBatchResult,
    IngestEventInput,
    IngestionService,
)

router = APIRouter(prefix="/ingest", tags=["ingest"])


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
