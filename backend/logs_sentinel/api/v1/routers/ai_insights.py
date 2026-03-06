from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Body, Depends, Header, HTTPException, Query, status

from logs_sentinel.api.v1.dependencies.auth import TenantContext, get_tenant_context
from logs_sentinel.api.v1.dependencies.services import (
    get_billing_service,
    get_fix_suggestions_service,
)
from logs_sentinel.api.v1.schemas.ai_insights import (
    AnalyzeFixSuggestionBody,
    FixSuggestionOut,
    FixSuggestionsResponse,
)
from logs_sentinel.application.services.ai_insights_service import FixSuggestionsService
from logs_sentinel.application.services.billing_service import BillingService
from logs_sentinel.domains.ai.entities import FixSuggestionResult
from logs_sentinel.domains.identity.entities import TenantId
from logs_sentinel.infrastructure.llm.null_client import NullLLMClient
from logs_sentinel.utils.lang import resolved_lang
from logs_sentinel.utils.prompts import build_suggest_fix_prompt

router = APIRouter(prefix="/ai-insights", tags=["ai-insights"])


@router.get("/fix-suggestions", response_model=FixSuggestionsResponse)
async def get_fix_suggestions(
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    service: Annotated[FixSuggestionsService, Depends(get_fix_suggestions_service)],
    project_id: Annotated[int | None, Query()] = None,
    from_: Annotated[datetime | None, Query(alias="from")] = None,
    to: Annotated[datetime | None, Query()] = None,
    lang: Annotated[str | None, Query(description="Language code such as 'pt-BR' or 'en'")] = None,
    accept_language: Annotated[str | None, Header(convert_underscores=False)] = None,
) -> FixSuggestionsResponse:
    tenant_id = int(ctx.tenant_id)
    lang_resolved = resolved_lang(lang, accept_language)
    suggestions = await service.get_suggestions(
        tenant_id=tenant_id,
        project_id=project_id,
        from_dt=from_,
        to_dt=to,
        lang=lang_resolved,
    )
    items = [
        FixSuggestionOut(
            fingerprint=s.fingerprint,
            title=s.title,
            summary=s.summary,
            probable_cause=s.probable_cause,
            suggested_fix=s.suggested_fix,
            code_snippet=s.code_snippet,
            language=s.language,
            confidence=s.confidence,
            occurrences=s.occurrences,
            first_seen=s.first_seen,
            last_seen=s.last_seen,
            sample_event_id=s.sample_event_id,
        )
        for s in suggestions
    ]
    return FixSuggestionsResponse(items=items)


@router.post("/fix-suggestions/analyze", response_model=FixSuggestionOut)
async def analyze_fix_suggestion(
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    service: Annotated[FixSuggestionsService, Depends(get_fix_suggestions_service)],
    billing: Annotated[BillingService, Depends(get_billing_service)],
    body: Annotated[AnalyzeFixSuggestionBody, Body()],
    from_: Annotated[datetime | None, Query(alias="from")] = None,
    to: Annotated[datetime | None, Query()] = None,
    lang: Annotated[str | None, Query(description="Language code such as 'pt-BR' or 'en'")] = None,
    accept_language: Annotated[str | None, Header(convert_underscores=False)] = None,
) -> FixSuggestionOut:
    tenant_id = int(ctx.tenant_id)
    lang_resolved = resolved_lang(lang, accept_language)

    events = await service.get_cluster_events(
        tenant_id=tenant_id,
        project_id=body.project_id,
        fingerprint=body.fingerprint,
        from_dt=from_,
        to_dt=to,
    )
    if not events:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cluster not found for the given fingerprint in the selected period.",
        )
    events_sorted = sorted(events, key=lambda e: e.received_at)
    sample_messages = [e.message or "" for e in events_sorted]
    stacktrace = events_sorted[-1].stacktrace if events_sorted else None

    use_llm = await billing.is_llm_enabled(TenantId(tenant_id))

    if use_llm:
        from logs_sentinel.infrastructure.agents.suggest_fix import create_suggest_fix_agent

        agent = create_suggest_fix_agent()
        prompt = build_suggest_fix_prompt(
            fingerprint=body.fingerprint,
            sample_messages=sample_messages,
            stacktrace=stacktrace,
            lang=lang_resolved,
        )
        result = await agent.run(prompt)
        out = result.output
        llm_suggestion: FixSuggestionResult = FixSuggestionResult(
            title=(out.title or "").strip(),
            summary=(out.summary or "").strip(),
            probable_cause=(out.probable_cause or "").strip(),
            suggested_fix=(out.suggested_fix or "").strip(),
            code_snippet=out.code_snippet,
            language=out.language or ("pt-BR" if lang_resolved.lower().startswith("pt") else "en"),
            confidence=float(out.confidence if out.confidence is not None else 0.7),
        )
    else:
        llm_suggestion = await NullLLMClient().suggest_fix(
            fingerprint=body.fingerprint,
            sample_messages=sample_messages,
            stacktrace=stacktrace,
            lang=lang_resolved,
        )

    suggestion = await service.build_suggestion_from_llm_result(
        tenant_id=tenant_id,
        project_id=body.project_id,
        fingerprint=body.fingerprint,
        events_sorted=events_sorted,
        llm_suggestion=llm_suggestion,
    )

    if use_llm:
        try:
            await billing.record_llm_usage(TenantId(tenant_id))
        except ValueError as e:
            if str(e) == "USAGE_LIMIT_EXCEEDED":
                raise HTTPException(
                    status_code=status.HTTP_402_PAYMENT_REQUIRED,
                    detail={"code": "USAGE_LIMIT_EXCEEDED"},
                ) from e
            raise

    return FixSuggestionOut(
        fingerprint=suggestion.fingerprint,
        title=suggestion.title,
        summary=suggestion.summary,
        probable_cause=suggestion.probable_cause,
        suggested_fix=suggestion.suggested_fix,
        code_snippet=suggestion.code_snippet,
        language=suggestion.language,
        confidence=suggestion.confidence,
        occurrences=suggestion.occurrences,
        first_seen=suggestion.first_seen,
        last_seen=suggestion.last_seen,
        sample_event_id=suggestion.sample_event_id,
    )

