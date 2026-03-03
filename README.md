## LogSentinel - Intelligent Log Monitoring

LogSentinel is a multi-tenant SaaS for intelligent log monitoring, built with a FastAPI backend and a React + TypeScript frontend. It provides log ingestion, issue aggregation, alerting, and optional AI enrichment.

### Architecture overview

See `docs/architecture.md` for the diagram and bounded context description.

Key components:

- **Backend**: FastAPI, Pydantic v2, SQLAlchemy 2, Alembic, Celery, Redis, RabbitMQ, Postgres.
- **Frontend**: React, TypeScript, React Router, TanStack Query, MUI, Recharts, react-i18next.
- **Multi-tenancy**: `tenant_id` on tables, repositories scoped by tenant, `TenantContext` from JWT.
- **AI enrichment**: feature-flagged LLM adapter with a `NullLLM` implementation when disabled.

### Running locally

Prerequisites: Docker, Docker Compose, Node 20, Python 3.14 (only if running services directly).

Using Docker:

```bash
docker compose build
docker compose up -d
```

Services:

- API: `http://localhost:8000`
- Frontend: `http://localhost:5173`

CLI shortcuts:

```bash
make dev        # docker compose up -d
make migrate    # run Alembic migrations
make seed       # seed tenant/user/project/token
make backend-test
make backend-lint
make frontend-lint
make frontend-test
```

### Ingestion flow

1. Client sends batched logs to `POST /api/v1/ingest` with `X-Project-Token`.
2. FastAPI validates payload, enforces per-token rate limit via Redis, and enqueues batch to RabbitMQ via Celery.
3. Worker normalizes messages, computes fingerprints, upserts `Issue` aggregates, updates time-buckets in `issue_occurrences`, recalculates priority, and evaluates alert rules.
4. Alerts trigger Slack webhook notifications via async tasks; AI enrichment jobs are scheduled when enabled.

Sample request:

```bash
curl -X POST http://localhost:8000/api/v1/ingest \
  -H "Content-Type: application/json" \
  -H "X-Project-Token: dev-token-change-me" \
  -d '{"events":[{"level":"error","message":"Unhandled exception","exception_type":"ValueError","stacktrace":"...","context":{"path":"/api"}}]}'
```

### Multi-tenancy enforcement

- Every tenant-scoped table includes `tenant_id`.
- JWT access tokens contain `tenant_id`, `user_id`, and `role`.
- FastAPI dependencies resolve a `TenantContext` and all repositories require a `tenant_id` argument.
- Queries are always filtered by `tenant_id` to avoid cross-tenant leakage.

### LLM enrichment feature flag

Backend settings (see `backend/logs_sentinel/infrastructure/settings/config.py`):

- `LOGS_SENTINEL_ENABLE_LLM_ENRICHMENT=false` (default).
- When disabled, a `NullLLMClient` is used and the system behaves correctly without AI.
- To integrate a real provider, implement `LLMClientProtocol` and wire it based on configuration (e.g., OpenAI key).

### Extension points

- **Payments/plans**: plan checks live in the application layer; integrating Stripe or another PSP would plug into those policies.
- **Notification channels**: add new channel types in the Alerts domain and create infrastructure adapters (e.g., email, PagerDuty).
- **LLM providers**: implement additional LLM clients and select via configuration.

### Coding standards and commands

- Backend:
  - Type hints required; `mypy` in strict mode.
  - `ruff` for lint and format: `cd backend && uv run ruff check . && uv run ruff format .`
  - Tests: `cd backend && uv run pytest`
- Frontend:
  - ESLint + Prettier: `cd frontend && npm run lint`
  - Typecheck: `npm run typecheck`
  - Tests: `npm test` or `npm run test`

