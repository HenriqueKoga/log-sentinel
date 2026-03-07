from __future__ import annotations

from collections import defaultdict
from datetime import datetime

from logs_sentinel.domains.ai.entities import FixSuggestionResult
from logs_sentinel.domains.ai_insights.entities import ErrorLogEvent, InsightSuggestion
from logs_sentinel.domains.ai_insights.fingerprinting import compute_fingerprint
from logs_sentinel.domains.ai_insights.heuristics import (
    confidence_from_occurrences,
    map_exception_to_heuristic,
)
from logs_sentinel.domains.ai_insights.repositories import FixSuggestionAnalysisRepository
from logs_sentinel.domains.identity.entities import TenantId
from logs_sentinel.domains.ingestion.entities import ProjectId
from logs_sentinel.domains.logs.repositories import LogSearchRepository


class FixSuggestionsService:
    """Application service that groups logs and produces fix suggestions (heuristic listing + optional stored AI)."""

    def __init__(
        self,
        log_search: LogSearchRepository,
        analysis_repo: FixSuggestionAnalysisRepository | None = None,
    ) -> None:
        self._log_search = log_search
        self._analysis_repo = analysis_repo

    async def get_suggestions(
        self,
        *,
        tenant_id: int,
        project_id: int | None,
        from_dt: datetime | None,
        to_dt: datetime | None,
        limit_clusters: int = 100,
        lang: str = "pt-BR",
        sort_by: str = "occurrences",
        order: str = "desc",
    ) -> list[InsightSuggestion]:
        """List fix suggestions using heuristics only (no LLM)."""
        rows = await self._log_search.recent_errors(
            tenant_id=TenantId(tenant_id),
            project_id=ProjectId(project_id) if project_id is not None else None,
            from_dt=from_dt,
            to_dt=to_dt,
            limit=1000,
        )

        clusters: dict[str, list[ErrorLogEvent]] = defaultdict(list)
        for row in rows:
            fp = compute_fingerprint(
                row.exception_type,
                row.stacktrace,
                row.message or "",
            )
            clusters[fp].append(row)

        suggestions: list[InsightSuggestion] = []
        for fingerprint, events in list(clusters.items())[:limit_clusters]:
            events_sorted = sorted(events, key=lambda e: e.received_at)
            first = events_sorted[0]
            last = events_sorted[-1]
            message = last.message or ""
            exc = last.exception_type or ""

            base_title, base_summary, base_cause, base_fix, base_conf = map_exception_to_heuristic(
                exc,
                message,
                lang=lang,
            )
            confidence = confidence_from_occurrences(base_conf, len(events_sorted))

            suggestions.append(
                InsightSuggestion(
                    fingerprint=fingerprint,
                    title=base_title,
                    summary=base_summary,
                    probable_cause=base_cause,
                    suggested_fix=base_fix,
                    code_snippet=None,
                    language=None,
                    confidence=confidence,
                    occurrences=len(events_sorted),
                    first_seen=first.received_at,
                    last_seen=last.received_at,
                    sample_event_id=int(last.id),
                )
            )

        if self._analysis_repo and suggestions:
            saved = await self._analysis_repo.get_for_fingerprints(
                tenant_id=tenant_id,
                project_id=project_id,
                fingerprints=[s.fingerprint for s in suggestions],
            )
            if saved:
                merged: list[InsightSuggestion] = []
                for s in suggestions:
                    st = saved.get(s.fingerprint)
                    if st is not None:
                        merged.append(
                            InsightSuggestion(
                                fingerprint=s.fingerprint,
                                title=st.title,
                                summary=st.summary,
                                probable_cause=st.probable_cause,
                                suggested_fix=st.suggested_fix,
                                code_snippet=st.code_snippet,
                                language=st.language,
                                confidence=st.confidence,
                                occurrences=s.occurrences,
                                first_seen=s.first_seen,
                                last_seen=s.last_seen,
                                sample_event_id=s.sample_event_id,
                                analyzed=True,
                            )
                        )
                    else:
                        merged.append(s)
                suggestions = merged

        reverse = order.lower() == "desc"
        if sort_by == "occurrences":
            suggestions.sort(key=lambda s: s.occurrences, reverse=reverse)
        elif sort_by == "confidence":
            suggestions.sort(key=lambda s: s.confidence, reverse=reverse)
        elif sort_by == "title":
            suggestions.sort(key=lambda s: s.title.lower(), reverse=reverse)
        elif sort_by == "first_seen":
            suggestions.sort(key=lambda s: s.first_seen, reverse=reverse)
        elif sort_by == "last_seen":
            suggestions.sort(key=lambda s: s.last_seen, reverse=reverse)
        else:
            suggestions.sort(key=lambda s: s.occurrences, reverse=reverse)

        return suggestions

    async def get_cluster_events(
        self,
        *,
        tenant_id: int,
        project_id: int | None,
        fingerprint: str,
        from_dt: datetime | None,
        to_dt: datetime | None,
    ) -> list[ErrorLogEvent] | None:
        """Return events for the given fingerprint cluster, or None if not found."""
        rows = await self._log_search.recent_errors(
            tenant_id=TenantId(tenant_id),
            project_id=ProjectId(project_id) if project_id is not None else None,
            from_dt=from_dt,
            to_dt=to_dt,
            limit=1000,
        )
        clusters: dict[str, list[ErrorLogEvent]] = defaultdict(list)
        for row in rows:
            fp = compute_fingerprint(
                row.exception_type,
                row.stacktrace,
                row.message or "",
            )
            clusters[fp].append(row)
        return clusters.get(fingerprint)

    async def build_suggestion_from_llm_result(
        self,
        *,
        tenant_id: int,
        project_id: int | None,
        fingerprint: str,
        events_sorted: list[ErrorLogEvent],
        llm_suggestion: FixSuggestionResult,
    ) -> InsightSuggestion:
        """Build and optionally persist InsightSuggestion from cluster events and LLM result."""
        first = events_sorted[0]
        last = events_sorted[-1]
        suggestion = InsightSuggestion(
            fingerprint=fingerprint,
            title=llm_suggestion.title,
            summary=llm_suggestion.summary,
            probable_cause=llm_suggestion.probable_cause,
            suggested_fix=llm_suggestion.suggested_fix,
            code_snippet=llm_suggestion.code_snippet,
            language=llm_suggestion.language,
            confidence=llm_suggestion.confidence,
            occurrences=len(events_sorted),
            first_seen=first.received_at,
            last_seen=last.received_at,
            sample_event_id=int(last.id),
            analyzed=True,
        )
        if self._analysis_repo:
            await self._analysis_repo.upsert(
                tenant_id=tenant_id,
                project_id=project_id,
                fingerprint=fingerprint,
                title=suggestion.title,
                summary=suggestion.summary,
                probable_cause=suggestion.probable_cause,
                suggested_fix=suggestion.suggested_fix,
                code_snippet=suggestion.code_snippet,
                language=suggestion.language,
                confidence=suggestion.confidence,
            )
        return suggestion

