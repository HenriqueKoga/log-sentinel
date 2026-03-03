# LogSentinel Architecture

```text
                       +----------------------+
                       |      Frontend        |
                       |  React + MUI + i18n  |
                       +-----------+----------+
                                   |
                           HTTPS / JSON
                                   |
                        +----------v-----------+
                        |      FastAPI API    |
                        |  DDD / Clean Arch   |
                        +----------+----------+
                                   |
                 +-----------------+---------------------+
                 |                 |                     |
          PostgreSQL          Redis (cache)        RabbitMQ (broker)
          issues, logs,       rate limit,          async ingestion,
          alerts, tenants     refresh tokens       alerts, enrichment

                 +-----------------+
                 | Celery Workers  |
                 | ingestion,      |
                 | alerts, AI      |
                 +-----------------+
```

Bounded contexts:

- **Identity**: tenants, users, memberships, RBAC.
- **Ingestion**: projects, tokens, raw log events, normalization, fingerprinting.
- **Issues**: grouping, prioritization, spike detection.
- **Alerts**: rules, channels (Slack), alert events.
- **AI**: enrichment results behind a feature-flagged LLM adapter.

