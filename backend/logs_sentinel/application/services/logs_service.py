"""Application service for logs list and detail API."""

from __future__ import annotations

from datetime import datetime

from logs_sentinel.api.v1.schemas.logs import (
    LogDetailEnrichment,
    LogDetailResponse,
    LogListItem,
    LogsListResponse,
    RelatedIssueInfo,
)
from logs_sentinel.domains.ai_insights.entities import IssueFingerprint
from logs_sentinel.domains.ai_insights.repositories import IssueEnrichmentLookupRepository
from logs_sentinel.domains.ingestion.normalization import compute_fingerprint, normalize_message
from logs_sentinel.domains.logs.repositories import LogsRepository

AI_SUMMARY_MAX_LEN = 120


def _log_fingerprint(message: str, exception_type: str | None, stacktrace: str | None) -> str:
    normalized = normalize_message(message or "")
    frames = stacktrace.splitlines() if stacktrace else None
    return compute_fingerprint(
        normalized_message=normalized,
        exception_type=exception_type,
        stack_frames=frames,
    )


def _source_from_raw_json(raw_json: dict[str, object]) -> str:
    return str(raw_json.get("source") or raw_json.get("service") or "-")


class LogsService:
    """Service for logs list and detail operations."""

    def __init__(
        self,
        logs_repo: LogsRepository,
        enrichment_lookup_repo: IssueEnrichmentLookupRepository,
    ) -> None:
        self._repo = logs_repo
        self._enrichment_lookup = enrichment_lookup_repo

    async def list_logs(
        self,
        *,
        tenant_id: int,
        project_id: int | None,
        level: list[str] | None,
        q: str | None,
        from_dt: datetime | None,
        to_dt: datetime | None,
        page: int,
        page_size: int,
        without_issue: bool,
    ) -> LogsListResponse:
        limit = page_size
        offset = (page - 1) * page_size

        existing_issue_keys: set[IssueFingerprint] = set()
        if without_issue:
            existing_issue_keys = await self._enrichment_lookup.get_issue_fingerprints(tenant_id)

        enrichment_map = await self._enrichment_lookup.get_enrichment_map(tenant_id)

        fetch_limit = min(500, page_size * 20) if without_issue else limit
        fetch_offset = 0 if without_issue else offset

        rows, total = await self._repo.list_logs(
            tenant_id=tenant_id,
            project_id=project_id,
            level=level,
            q=q,
            from_dt=from_dt,
            to_dt=to_dt,
            limit=fetch_limit,
            offset=fetch_offset,
        )

        items: list[LogListItem] = []
        for row in rows:
            fp = _log_fingerprint(row.message, row.exception_type, row.stacktrace)
            if without_issue:
                if IssueFingerprint(row.project_id, fp) in existing_issue_keys:
                    continue
                if len(items) >= page_size:
                    break

            raw_json = row.raw_json if isinstance(row.raw_json, dict) else {}
            source = _source_from_raw_json(raw_json)

            raw_ai = enrichment_map.get(IssueFingerprint(row.project_id, fp))
            ai_summary = None
            if raw_ai:
                ai_summary = (
                    raw_ai[:AI_SUMMARY_MAX_LEN] + "…"
                    if len(raw_ai) > AI_SUMMARY_MAX_LEN
                    else raw_ai
                )

            items.append(
                LogListItem(
                    id=row.id,
                    timestamp=row.received_at,
                    level=row.level,
                    message=row.message or "",
                    project_id=row.project_id,
                    project_name=row.project_name or "",
                    source=source,
                    ai_summary=ai_summary,
                )
            )

        if without_issue:
            total = len(items)
        return LogsListResponse(items=items, total=total)

    async def get_log_detail(self, log_id: int, tenant_id: int) -> LogDetailResponse | None:
        row = await self._repo.get_log_detail(log_id, tenant_id)
        if row is None:
            return None

        raw_json = row.raw_json if isinstance(row.raw_json, dict) else {}
        source = _source_from_raw_json(raw_json)

        fingerprint = _log_fingerprint(row.message, row.exception_type, row.stacktrace)
        related = await self._enrichment_lookup.get_related_issue_and_enrichment(
            tenant_id, row.project_id, fingerprint
        )

        related_issue: RelatedIssueInfo | None = None
        enrichment: LogDetailEnrichment | None = None
        if related is not None:
            related_issue = RelatedIssueInfo(id=related.issue.id, title=related.issue.title)
            if related.enrichment is not None:
                enrich_row = related.enrichment
                enrichment = LogDetailEnrichment(
                    model_name=enrich_row.model_name,
                    summary=enrich_row.summary,
                    suspected_cause=enrich_row.suspected_cause,
                    checklist=enrich_row.checklist,
                    created_at=enrich_row.created_at,
                )

        return LogDetailResponse(
            id=row.id,
            timestamp=row.received_at,
            level=row.level,
            message=row.message or "",
            exception_type=row.exception_type,
            stacktrace=row.stacktrace,
            raw_json=raw_json,
            project_id=row.project_id,
            project_name=row.project_name or "",
            source=source,
            related_issue=related_issue,
            enrichment=enrichment,
        )
