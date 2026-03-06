from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from logs_sentinel.application.services.alerts_service import AlertsService, NotificationSender
from logs_sentinel.domains.alerts.entities import (
    AlertEvent,
    AlertKind,
    AlertRule,
    AlertRuleId,
    NotificationChannel,
    NotificationChannelId,
    NotificationChannelKind,
)
from logs_sentinel.domains.alerts.repositories import (
    AlertEventRepository,
    AlertRuleRepository,
    NotificationChannelRepository,
)
from logs_sentinel.domains.identity.entities import TenantId
from logs_sentinel.domains.ingestion.entities import ProjectId
from logs_sentinel.domains.issues.entities import (
    Issue,
    IssueId,
    IssueOccurrenceBucket,
    IssueOccurrenceId,
    IssueSeverity,
    IssueStatus,
)
from logs_sentinel.domains.issues.repositories import IssueOccurrencesRepository


class InMemoryRuleRepo(AlertRuleRepository):
    def __init__(self, rules: list[AlertRule]) -> None:
        self._rules = rules

    async def list_rules(
        self, tenant_id: TenantId, project_id: ProjectId | None
    ) -> list[AlertRule]:
        return [r for r in self._rules if r.tenant_id == tenant_id and r.project_id == project_id]

    async def create_rule(
        self,
        tenant_id: TenantId,
        project_id: ProjectId,
        name: str,
        kind: str,
        threshold: float,
    ) -> AlertRule:
        raise NotImplementedError

    async def get_rule(self, tenant_id: TenantId, rule_id: AlertRuleId) -> AlertRule | None:
        raise NotImplementedError


class InMemoryEventRepo(AlertEventRepository):
    def __init__(self) -> None:
        self.events: list[AlertEvent] = []

    async def create_event(
        self,
        tenant_id: TenantId,
        issue_id: IssueId,
        rule_id: AlertRuleId,
        triggered_at: datetime,
        payload_json: dict[str, object],
    ) -> AlertEvent:
        event = AlertEvent(
            id=len(self.events) + 1,  # type: ignore[arg-type]
            tenant_id=tenant_id,
            issue_id=issue_id,
            rule_id=rule_id,
            triggered_at=triggered_at,
            payload_json=payload_json,
        )
        self.events.append(event)
        return event

    async def list_events(
        self,
        tenant_id: TenantId,
        since: datetime | None,
        limit: int = 50,
    ) -> list[AlertEvent]:
        return self.events


class InMemoryChannelRepo(NotificationChannelRepository):
    async def list_channels(self, tenant_id: TenantId) -> list[NotificationChannel]:
        return [
            NotificationChannel(
                id=NotificationChannelId(1),
                tenant_id=tenant_id,
                kind=NotificationChannelKind.SLACK_WEBHOOK,
                config_json={"webhook_url": "https://hooks.slack.test"},
                enabled=True,
            )
        ]


class InMemoryOccurrencesRepo(IssueOccurrencesRepository):
    def __init__(self) -> None:
        self._buckets: list[IssueOccurrenceBucket] = []

    async def upsert_bucket(
        self,
        tenant_id: TenantId,
        issue_id: IssueId,
        bucket_start: datetime,
        bucket_minutes: int,
        increment: int,
    ) -> None:
        raise NotImplementedError

    async def list_buckets(
        self,
        tenant_id: TenantId,
        issue_id: IssueId,
        bucket_minutes: int,
        since: datetime,
        until: datetime,
    ) -> list[IssueOccurrenceBucket]:
        return [
            b
            for b in self._buckets
            if b.tenant_id == tenant_id
            and b.issue_id == issue_id
            and b.bucket_minutes == bucket_minutes
            and since <= b.bucket_start <= until
        ]

    def seed_bucket(
        self,
        tenant_id: TenantId,
        issue_id: IssueId,
        bucket_start: datetime,
        bucket_minutes: int,
        count: int,
    ) -> None:
        self._buckets.append(
            IssueOccurrenceBucket(
                id=IssueOccurrenceId(len(self._buckets) + 1),
                tenant_id=tenant_id,
                issue_id=issue_id,
                bucket_start=bucket_start,
                bucket_minutes=bucket_minutes,
                count=count,
            )
        )


class DummySender(NotificationSender):
    def __init__(self) -> None:
        self.sent: list[dict[str, Any]] = []

    async def send_alert(self, tenant_id: TenantId, rule: AlertRule, issue: Issue) -> None:
        self.sent.append({"tenant_id": tenant_id, "rule": rule, "issue": issue})


@pytest.mark.asyncio
async def test_alert_evaluation_fires_when_threshold_met() -> None:
    tenant_id = TenantId(1)
    project_id = ProjectId(1)
    issue = Issue(
        id=IssueId(1),
        tenant_id=tenant_id,
        project_id=project_id,
        fingerprint="fp",
        title="Error",
        severity=IssueSeverity.HIGH,
        status=IssueStatus.OPEN,
        first_seen=datetime.now(tz=UTC),
        last_seen=datetime.now(tz=UTC),
        total_count=10,
        priority_score=5.0,
    )

    rule = AlertRule(
        id=AlertRuleId(1),
        tenant_id=tenant_id,
        project_id=project_id,
        name="High errors in 5m",
        kind=AlertKind.COUNT_5M,
        threshold=5,
        enabled=True,
    )

    rules_repo = InMemoryRuleRepo([rule])
    events_repo = InMemoryEventRepo()
    channels_repo = InMemoryChannelRepo()
    occurrences_repo = InMemoryOccurrencesRepo()
    sender = DummySender()

    now = datetime.now(tz=UTC)
    occurrences_repo.seed_bucket(
        tenant_id=tenant_id,
        issue_id=issue.id,
        bucket_start=now - timedelta(minutes=1),
        bucket_minutes=5,
        count=6,
    )

    service = AlertsService(
        rules_repo=rules_repo,
        events_repo=events_repo,
        channels_repo=channels_repo,
        occurrences_repo=occurrences_repo,
        sender=sender,
    )

    events = await service.evaluate_rules_for_issue(
        tenant_id=tenant_id,
        project_id=project_id,
        issue=issue,
        now=now,
    )

    assert len(events) == 1
    assert len(events_repo.events) == 1
    assert len(sender.sent) == 1
