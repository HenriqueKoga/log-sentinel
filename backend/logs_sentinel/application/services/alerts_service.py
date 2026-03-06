from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Protocol, cast

from logs_sentinel.domains.alerts.entities import AlertEvent, AlertKind, AlertRule
from logs_sentinel.domains.alerts.repositories import (
    AlertEventRepository,
    AlertRuleRepository,
    NotificationChannelRepository,
)
from logs_sentinel.domains.identity.entities import TenantId
from logs_sentinel.domains.ingestion.entities import ProjectId
from logs_sentinel.domains.issues.entities import Issue, IssueId
from logs_sentinel.domains.issues.repositories import IssueOccurrencesRepository


class NotificationSender(Protocol):
    """Abstraction for sending alert notifications."""

    async def send_alert(self, tenant_id: TenantId, rule: AlertRule, issue: Issue) -> None: ...


class AlertsService:
    """Application service evaluating alert rules and recording events."""

    def __init__(
        self,
        rules_repo: AlertRuleRepository,
        events_repo: AlertEventRepository,
        channels_repo: NotificationChannelRepository,
        occurrences_repo: IssueOccurrencesRepository,
        sender: NotificationSender,
    ) -> None:
        self._rules = rules_repo
        self._events = events_repo
        self._channels = channels_repo
        self._occurrences = occurrences_repo
        self._sender = sender

    async def evaluate_rules_for_issue(
        self,
        tenant_id: TenantId,
        project_id: ProjectId,
        issue: Issue,
        now: datetime | None = None,
    ) -> Sequence[AlertEvent]:
        """Evaluate alert rules and create events for those that fire."""

        if now is None:
            now = datetime.now(tz=UTC)

        rules = await self._rules.list_rules(tenant_id=tenant_id, project_id=project_id)
        fired_events: list[AlertEvent] = []

        for rule in rules:
            if not rule.enabled:
                continue

            should_fire = await self._rule_fires(tenant_id, issue.id, rule, now)
            if not should_fire:
                continue

            payload = {
                "issue_id": int(issue.id),
                "rule_id": int(rule.id),
                "priority_score": issue.priority_score,
                "severity": issue.severity.value,
                "title": issue.title,
            }
            event = await self._events.create_event(
                tenant_id=tenant_id,
                issue_id=issue.id,
                rule_id=rule.id,
                triggered_at=now,
                payload_json=cast("dict[str, object]", payload),
            )
            fired_events.append(event)
            await self._sender.send_alert(tenant_id=tenant_id, rule=rule, issue=issue)

        return fired_events

    async def _rule_fires(
        self,
        tenant_id: TenantId,
        issue_id: IssueId,
        rule: AlertRule,
        now: datetime,
    ) -> bool:
        if rule.kind == AlertKind.COUNT_5M:
            since = now - timedelta(minutes=5)
            buckets = await self._occurrences.list_buckets(
                tenant_id=tenant_id,
                issue_id=issue_id,
                bucket_minutes=5,
                since=since,
                until=now,
            )
            count = sum(b.count for b in buckets)
            return count >= rule.threshold

        if rule.kind == AlertKind.SPIKE:
            # Simplified spike: if count in last 5m >= threshold
            since = now - timedelta(minutes=5)
            buckets = await self._occurrences.list_buckets(
                tenant_id=tenant_id,
                issue_id=issue_id,
                bucket_minutes=5,
                since=since,
                until=now,
            )
            count = sum(b.count for b in buckets)
            return count >= rule.threshold

        return False
