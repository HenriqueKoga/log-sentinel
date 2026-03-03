from __future__ import annotations

from asyncio import TaskGroup
from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from logs_sentinel.domains.ai.entities import IssueEnrichment, IssueEnrichmentId, LLMClientProtocol
from logs_sentinel.domains.identity.entities import TenantId
from logs_sentinel.domains.issues.entities import IssueId
from logs_sentinel.infrastructure.db.models import IssueEnrichmentModel, LogEventModel


class AIEnrichmentService:
    """Application service orchestrating AI enrichment for issues."""

    def __init__(
        self,
        session: AsyncSession,
        llm_client: LLMClientProtocol,
    ) -> None:
        self._session = session
        self._llm = llm_client

    async def get_latest_enrichment(
        self,
        tenant_id: TenantId,
        issue_id: IssueId,
    ) -> IssueEnrichment | None:
        stmt = (
            select(IssueEnrichmentModel)
            .where(
                IssueEnrichmentModel.tenant_id == int(tenant_id),
                IssueEnrichmentModel.issue_id == int(issue_id),
            )
            .order_by(IssueEnrichmentModel.created_at.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return None
        model: IssueEnrichmentModel = row
        return IssueEnrichment(
            id=IssueEnrichmentId(model.id),
            tenant_id=TenantId(model.tenant_id),
            issue_id=IssueId(model.issue_id),
            model_name=model.model_name,
            summary=model.summary,
            suspected_cause=model.suspected_cause,
            checklist_json=model.checklist_json,
            created_at=model.created_at,
        )

    async def enrich_issue(
        self,
        tenant_id: TenantId,
        issue_id: IssueId,
    ) -> IssueEnrichment:
        """Generate and persist a new enrichment for the given issue."""

        now = datetime.now(tz=UTC)

        async def _fetch_events() -> Sequence[dict[str, object]]:
            stmt = (
                select(LogEventModel)
                .where(
                    LogEventModel.tenant_id == int(tenant_id),
                    # Filter by project via join on issues if needed later.
                )
                .order_by(LogEventModel.received_at.desc())
                .limit(50)
            )
            result = await self._session.execute(stmt)
            events: list[dict[str, object]] = []
            for row in result.scalars().all():
                ev: LogEventModel = row
                events.append(
                    {
                        "received_at": ev.received_at.isoformat(),
                        "level": ev.level,
                        "message": ev.message,
                        "exception_type": ev.exception_type or "",
                    }
                )
            return events

        async with TaskGroup() as tg:
            events_task = tg.create_task(_fetch_events())

        events = events_task.result()
        enrichment = await self._llm.enrich_issue(events)

        model = IssueEnrichmentModel(
            tenant_id=int(tenant_id),
            issue_id=int(issue_id),
            model_name=enrichment.model_name,
            summary=enrichment.summary,
            suspected_cause=enrichment.suspected_cause,
            checklist_json=enrichment.checklist_json,
            created_at=now,
        )
        self._session.add(model)
        await self._session.flush()

        return IssueEnrichment(
            id=IssueEnrichmentId(model.id),
            tenant_id=TenantId(model.tenant_id),
            issue_id=IssueId(model.issue_id),
            model_name=model.model_name,
            summary=model.summary,
            suspected_cause=model.suspected_cause,
            checklist_json=model.checklist_json,
            created_at=model.created_at,
        )

