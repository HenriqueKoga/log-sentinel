"""Dependency factories for application services and agents (used by routers)."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from logs_sentinel.application.services.ai_insights_service import FixSuggestionsService
from logs_sentinel.application.services.ai_service import AIEnrichmentService
from logs_sentinel.application.services.billing_service import BillingService
from logs_sentinel.application.services.chat_service import ChatService
from logs_sentinel.application.services.chat_tools_service import ChatToolsService
from logs_sentinel.application.services.ingestion_service import IngestionService
from logs_sentinel.application.services.issue_service import IssueService
from logs_sentinel.application.services.logs_service import LogsService
from logs_sentinel.application.services.metrics_service import MetricsService
from logs_sentinel.application.services.projects_service import ProjectsService
from logs_sentinel.domains.issues.repositories import IssueOccurrencesRepository, IssueRepository
from logs_sentinel.infrastructure.agents.chat import create_chat_agent
from logs_sentinel.infrastructure.agents.chat_session_title import create_chat_session_title_agent
from logs_sentinel.infrastructure.cache.redis_rate_limiter import (
    RedisRateLimiter,
    create_redis_client,
)
from logs_sentinel.infrastructure.db.base import get_session
from logs_sentinel.infrastructure.db.repositories.ai_enrichment import (
    IssueEnrichmentLookupRepositorySQLAlchemy,
    IssueEnrichmentRepositorySQLAlchemy,
)
from logs_sentinel.infrastructure.db.repositories.ai_insights import (
    FixSuggestionAnalysisRepositorySQLAlchemy,
)
from logs_sentinel.infrastructure.db.repositories.billing import (
    CreditPolicyRepositorySQLAlchemy,
    LlmModelRepositorySQLAlchemy,
    LlmUsageRepositorySQLAlchemy,
    TenantPlanRepositorySQLAlchemy,
    UsageCounterRepositorySQLAlchemy,
)
from logs_sentinel.infrastructure.db.repositories.chat import (
    ChatMessageRepositorySQLAlchemy,
    ChatSessionRepositorySQLAlchemy,
)
from logs_sentinel.infrastructure.db.repositories.ingest_tokens import (
    IngestTokenRepositorySQLAlchemy,
)
from logs_sentinel.infrastructure.db.repositories.issues import (
    IssueOccurrencesRepositorySQLAlchemy,
    IssueRepositorySQLAlchemy,
)
from logs_sentinel.infrastructure.db.repositories.logs import (
    LogSearchRepositorySQLAlchemy,
    LogsRepositorySQLAlchemy,
)
from logs_sentinel.infrastructure.db.repositories.metrics import MetricsRepositorySQLAlchemy
from logs_sentinel.infrastructure.db.repositories.projects import (
    ProjectRepositorySQLAlchemy,
)
from logs_sentinel.infrastructure.messaging.celery_ingest_queue import CeleryIngestQueue
from logs_sentinel.infrastructure.settings.config import settings


async def get_billing_service(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> BillingService:
    return BillingService(
        plans_repo=TenantPlanRepositorySQLAlchemy(session),
        usage_repo=UsageCounterRepositorySQLAlchemy(session),
        llm_model_repo=LlmModelRepositorySQLAlchemy(session),
        llm_usage_repo=LlmUsageRepositorySQLAlchemy(session),
        credit_policy_repo=CreditPolicyRepositorySQLAlchemy(session),
    )


async def get_issue_service(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> IssueService:
    issue_repo: IssueRepository = IssueRepositorySQLAlchemy(session)
    buckets_repo: IssueOccurrencesRepository = IssueOccurrencesRepositorySQLAlchemy(session)
    project_repo = ProjectRepositorySQLAlchemy(session)
    return IssueService(
        issue_repo=issue_repo,
        buckets_repo=buckets_repo,
        project_repo=project_repo,
    )


async def get_ai_service(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AIEnrichmentService:
    enrichment_repo = IssueEnrichmentRepositorySQLAlchemy(session)
    logs_repo = LogsRepositorySQLAlchemy(session)
    issue_repo = IssueRepositorySQLAlchemy(session)
    return AIEnrichmentService(
        enrichment_repo=enrichment_repo,
        logs_repo=logs_repo,
        issue_repo=issue_repo,
    )


async def get_logs_service(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> LogsService:
    logs_repo = LogsRepositorySQLAlchemy(session)
    enrichment_lookup_repo = IssueEnrichmentLookupRepositorySQLAlchemy(session)
    return LogsService(
        logs_repo=logs_repo,
        enrichment_lookup_repo=enrichment_lookup_repo,
    )


async def get_metrics_service(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> MetricsService:
    metrics_repo = MetricsRepositorySQLAlchemy(session)
    return MetricsService(metrics_repo=metrics_repo)


async def get_projects_service(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ProjectsService:
    project_repo = ProjectRepositorySQLAlchemy(session)
    token_repo = IngestTokenRepositorySQLAlchemy(session)
    return ProjectsService(project_repo=project_repo, token_repo=token_repo)


async def get_ingestion_service(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> IngestionService:
    redis_client = create_redis_client(settings.redis_url)
    rate_limiter = RedisRateLimiter(redis_client)
    token_repo = IngestTokenRepositorySQLAlchemy(session)
    log_repo = LogsRepositorySQLAlchemy(session)
    queue = CeleryIngestQueue()
    billing = BillingService(
        plans_repo=TenantPlanRepositorySQLAlchemy(session),
        usage_repo=UsageCounterRepositorySQLAlchemy(session),
    )
    return IngestionService(
        token_repo=token_repo,
        log_repo=log_repo,
        rate_limiter=rate_limiter,
        queue=queue,
        usage_checker=billing,
    )


async def get_fix_suggestions_service(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> FixSuggestionsService:
    log_search_repo = LogSearchRepositorySQLAlchemy(session)
    analysis_repo = FixSuggestionAnalysisRepositorySQLAlchemy(session)
    return FixSuggestionsService(log_search=log_search_repo, analysis_repo=analysis_repo)


async def get_chat_service(
    session: Annotated[AsyncSession, Depends(get_session)],
    billing_service: Annotated[BillingService, Depends(get_billing_service)],
) -> ChatService:
    session_repo = ChatSessionRepositorySQLAlchemy(session)
    message_repo = ChatMessageRepositorySQLAlchemy(session)
    log_search_repo = LogSearchRepositorySQLAlchemy(session)
    tools_service = ChatToolsService(log_search=log_search_repo)

    return ChatService(
        session_repo=session_repo,
        message_repo=message_repo,
        tools_service=tools_service,
        agent=create_chat_agent(),
        billing_service=billing_service,
        title_agent=create_chat_session_title_agent(),
    )
