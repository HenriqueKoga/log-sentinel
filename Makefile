PROJECT_ROOT := $(shell pwd)

.PHONY: dev stop logs backend-test backend-lint frontend-lint frontend-test migrate seed dev-frontend-local

dev:
	docker compose up -d

dev-frontend-local:
	cd frontend && npm install && npm run dev

stop:
	docker compose down

logs:
	docker compose logs -f backend-api backend-worker frontend

backend-test:
	cd backend && uv sync --all-extras && uv run python -m pytest logs_sentinel/tests -v

backend-test-cov:
	cd backend && uv sync --all-extras && uv run python -m pytest logs_sentinel/tests --cov=logs_sentinel --cov-report=term-missing --cov-fail-under=0

backend-lint:
	cd backend && uv run ruff check . --fix && uv run mypy .

frontend-lint:
	cd frontend && npm run lint

frontend-test:
	cd frontend && npm test -- --runInBand || npm run test

migrate:
	docker compose exec backend-api sh -c "cd /app && alembic upgrade head"

seed:
	docker compose exec backend-api sh -c "cd /app && python scripts/seed_dev_data.py"

