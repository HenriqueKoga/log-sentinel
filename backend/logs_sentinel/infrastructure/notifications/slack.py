from __future__ import annotations

from typing import Any

import httpx

from logs_sentinel.application.services.alerts_service import NotificationSender
from logs_sentinel.domains.alerts.entities import AlertRule
from logs_sentinel.domains.identity.entities import TenantId
from logs_sentinel.domains.issues.entities import Issue
from logs_sentinel.infrastructure.db.models import NotificationChannelModel


class SlackWebhookSender(NotificationSender):
    """Notification sender that delivers alerts to Slack webhooks."""

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client or httpx.AsyncClient()

    async def send_alert(self, tenant_id: TenantId, rule: AlertRule, issue: Issue) -> None:
        # In a real system we would scope channels per rule; for the MVP we send
        # to all enabled Slack webhook channels for the tenant.
        from logs_sentinel.infrastructure.db.base import SessionFactory

        async with SessionFactory() as session:
            result = await session.execute(
                NotificationChannelModel.__table__.select().where(
                    NotificationChannelModel.tenant_id == int(tenant_id),
                    NotificationChannelModel.kind == "slack_webhook",
                    NotificationChannelModel.enabled.is_(True),
                )
            )
            rows = result.fetchall()

        for row in rows:
            model = NotificationChannelModel(**row._mapping)
            webhook_url = model.config_json.get("webhook_url")
            if not webhook_url:
                continue
            payload: dict[str, Any] = {
                "text": f"[LogSentinel] Alert '{rule.name}' fired for issue #{int(issue.id)} "
                f"({issue.severity.value}): {issue.title}",
            }
            try:
                await self._client.post(webhook_url, json=payload, timeout=5.0)
            except Exception:
                # For MVP we swallow errors; they will still be visible in logs.
                continue

