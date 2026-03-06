"""SQLAlchemy implementation of IssueEnrichmentRepository and issue enrichment read model."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from logs_sentinel.domains.ai.entities import IssueEnrichment, IssueEnrichmentId
from logs_sentinel.domains.ai_insights.entities import IssueFingerprint
from logs_sentinel.domains.identity.entities import TenantId
from logs_sentinel.domains.issues.entities import IssueId
from logs_sentinel.domains.logs.entities import (
    EnrichmentRow,
    RelatedIssueRow,
    RelatedIssueWithEnrichment,
)
from logs_sentinel.infrastructure.db.models import IssueEnrichmentModel, IssueModel


class IssueEnrichmentRepositorySQLAlchemy:
    """IssueEnrichmentRepository implementation using SQLAlchemy."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_latest_enrichment(
        self, tenant_id: TenantId, issue_id: IssueId
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

    async def persist_enrichment(
        self,
        tenant_id: TenantId,
        issue_id: IssueId,
        *,
        model_name: str,
        summary: str,
        suspected_cause: str,
        checklist_json: list[str],
    ) -> IssueEnrichment:
        now = datetime.now(tz=UTC)
        model = IssueEnrichmentModel(
            tenant_id=int(tenant_id),
            issue_id=int(issue_id),
            model_name=model_name,
            summary=summary,
            suspected_cause=suspected_cause,
            checklist_json=checklist_json,
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


class IssueEnrichmentLookupRepositorySQLAlchemy:
    """Repository for looking up issue fingerprints and enrichments (logs UI)."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_issue_fingerprints(self, tenant_id: int) -> set[IssueFingerprint]:
        stmt = select(IssueModel.project_id, IssueModel.fingerprint).where(
            IssueModel.tenant_id == tenant_id
        )
        result = await self._session.execute(stmt)
        return {
            IssueFingerprint(project_id=int(r.project_id), fingerprint=r.fingerprint)
            for r in result.all()
        }

    async def get_enrichment_map(self, tenant_id: int) -> dict[IssueFingerprint, str]:
        stmt = (
            select(IssueModel.project_id, IssueModel.fingerprint, IssueEnrichmentModel.summary)
            .join(
                IssueEnrichmentModel,
                (IssueEnrichmentModel.issue_id == IssueModel.id)
                & (IssueEnrichmentModel.tenant_id == IssueModel.tenant_id),
            )
            .where(IssueModel.tenant_id == tenant_id)
            .order_by(IssueEnrichmentModel.created_at.desc())
        )
        result = await self._session.execute(stmt)
        out: dict[IssueFingerprint, str] = {}
        for pid, fp, summary in result.all():
            key = IssueFingerprint(project_id=int(pid), fingerprint=fp)
            if key not in out:
                out[key] = summary or ""
        return out

    async def get_related_issue_and_enrichment(
        self, tenant_id: int, project_id: int, fingerprint: str
    ) -> RelatedIssueWithEnrichment | None:
        issue_stmt = select(IssueModel).where(
            IssueModel.tenant_id == tenant_id,
            IssueModel.project_id == project_id,
            IssueModel.fingerprint == fingerprint,
        )
        issue_result = await self._session.execute(issue_stmt)
        issue_row = issue_result.scalar_one_or_none()
        if issue_row is None:
            return None
        related = RelatedIssueRow(id=issue_row.id, title=issue_row.title)
        enrich_stmt = (
            select(IssueEnrichmentModel)
            .where(
                IssueEnrichmentModel.tenant_id == tenant_id,
                IssueEnrichmentModel.issue_id == issue_row.id,
            )
            .order_by(IssueEnrichmentModel.created_at.desc())
            .limit(1)
        )
        enrich_result = await self._session.execute(enrich_stmt)
        enrich_model = enrich_result.scalar_one_or_none()
        enrichment = None
        if enrich_model is not None:
            enrichment = EnrichmentRow(
                model_name=enrich_model.model_name,
                summary=enrich_model.summary,
                suspected_cause=enrich_model.suspected_cause,
                checklist=enrich_model.checklist_json or [],
                created_at=enrich_model.created_at,
            )
        return RelatedIssueWithEnrichment(issue=related, enrichment=enrichment)
