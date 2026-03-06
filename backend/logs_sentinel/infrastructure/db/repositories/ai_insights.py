"""SQLAlchemy implementation of fix suggestion analysis repository."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from logs_sentinel.domains.ai_insights.entities import SavedFixSuggestionAnalysis
from logs_sentinel.domains.ai_insights.repositories import FixSuggestionAnalysisRepository
from logs_sentinel.infrastructure.db.models import FixSuggestionAnalysisModel


class FixSuggestionAnalysisRepositorySQLAlchemy(FixSuggestionAnalysisRepository):
    """SQLAlchemy implementation for persisting and loading AI fix suggestion analyses."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert(
        self,
        *,
        tenant_id: int,
        project_id: int | None,
        fingerprint: str,
        title: str,
        summary: str,
        probable_cause: str,
        suggested_fix: str,
        code_snippet: str | None,
        language: str | None,
        confidence: float,
    ) -> None:
        now = datetime.now(UTC)
        stmt = select(FixSuggestionAnalysisModel).where(
            FixSuggestionAnalysisModel.tenant_id == tenant_id,
            FixSuggestionAnalysisModel.fingerprint == fingerprint,
            (FixSuggestionAnalysisModel.project_id == project_id)
            if project_id is not None
            else FixSuggestionAnalysisModel.project_id.is_(None),
        )
        result = await self._session.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing:
            existing.title = title
            existing.summary = summary
            existing.probable_cause = probable_cause
            existing.suggested_fix = suggested_fix
            existing.code_snippet = code_snippet
            existing.language = language
            existing.confidence = confidence
            existing.updated_at = now
        else:
            self._session.add(
                FixSuggestionAnalysisModel(
                    tenant_id=tenant_id,
                    project_id=project_id,
                    fingerprint=fingerprint,
                    title=title,
                    summary=summary,
                    probable_cause=probable_cause,
                    suggested_fix=suggested_fix,
                    code_snippet=code_snippet,
                    language=language,
                    confidence=confidence,
                    updated_at=now,
                )
            )

    async def get_for_fingerprints(
        self,
        *,
        tenant_id: int,
        project_id: int | None,
        fingerprints: Sequence[str],
    ) -> dict[str, SavedFixSuggestionAnalysis]:
        if not fingerprints:
            return {}
        cond = or_(
            FixSuggestionAnalysisModel.project_id == project_id,
            FixSuggestionAnalysisModel.project_id.is_(None),
        )
        stmt = select(FixSuggestionAnalysisModel).where(
            FixSuggestionAnalysisModel.tenant_id == tenant_id,
            FixSuggestionAnalysisModel.fingerprint.in_(fingerprints),
            cond,
        )
        result = await self._session.execute(stmt)
        rows = list(result.scalars().all())

        project_specific = [m for m in rows if m.project_id == project_id]
        global_ = [m for m in rows if m.project_id is None]
        out: dict[str, SavedFixSuggestionAnalysis] = {}
        for m in project_specific:
            out[m.fingerprint] = SavedFixSuggestionAnalysis(
                fingerprint=m.fingerprint,
                title=m.title,
                summary=m.summary,
                probable_cause=m.probable_cause,
                suggested_fix=m.suggested_fix,
                code_snippet=m.code_snippet,
                language=m.language,
                confidence=m.confidence,
            )
        for m in global_:
            if m.fingerprint not in out:
                out[m.fingerprint] = SavedFixSuggestionAnalysis(
                fingerprint=m.fingerprint,
                title=m.title,
                summary=m.summary,
                probable_cause=m.probable_cause,
                suggested_fix=m.suggested_fix,
                code_snippet=m.code_snippet,
                language=m.language,
                confidence=m.confidence,
            )
        return out
