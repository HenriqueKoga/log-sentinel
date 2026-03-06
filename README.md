# LogSentinel

Multi-tenant SaaS for intelligent log monitoring: ingestion, issue aggregation, alerting, and optional AI enrichment. FastAPI backend and React + TypeScript frontend.

---

## Architecture

High-level overview (details and bounded contexts in [`docs/architecture.md`](docs/architecture.md)):

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
       PostgreSQL          Redis                 RabbitMQ
       issues, logs,       rate limit,           async ingestion,
       alerts, tenants    refresh tokens         alerts, enrichment
              |                 |
              +-----------------+
                     | Celery Workers |
                     | ingestion,     |
                     | alerts, AI     |
                     +----------------+
```

- **Backend:** FastAPI, Pydantic v2, SQLAlchemy 2, Alembic, Celery, Redis, RabbitMQ, PostgreSQL.
- **Frontend:** React, TypeScript, React Router, TanStack Query, MUI, Recharts, react-i18next.
- **Multi-tenancy:** `tenant_id` on tables, tenant-scoped repositories, `TenantContext` from JWT.
- **Domain contexts:** Identity (tenants, users, RBAC), Ingestion (projects, tokens, logs, fingerprinting), Issues (grouping, prioritization), Alerts (rules, channels such as Slack), AI (enrichment behind a feature flag).

---

## How to use

### Prerequisites

- Docker and Docker Compose  
- Node 20 (only if running the frontend on the host)  
- Python 3.14 (only if running the backend on the host)

### Run the project

```bash
docker compose build
docker compose up -d
```

### Log ingestion

Send a batch to the API:

```bash
curl -X POST http://localhost:8000/api/v1/ingest \
  -H "Content-Type: application/json" \
  -H "X-Project-Token: dev-token-change-me" \
  -d '{"events":[{"level":"error","message":"Unhandled exception","exception_type":"ValueError","stacktrace":"...","context":{"path":"/api"}}]}'
```

Flow: payload validation → per-token rate limit (Redis) → enqueue to RabbitMQ (Celery). The worker normalizes messages, computes fingerprints, updates issue aggregates, and evaluates alert rules (e.g. Slack).
