PROJECT_ROOT := $(shell pwd)

.PHONY: dev stop logs backend-test backend-lint frontend-lint frontend-test migrate seed

dev:
	docker compose up -d

stop:
	docker compose down

logs:
	docker compose logs -f backend-api backend-worker frontend

backend-test:
	cd backend && uv run pytest

backend-lint:
	cd backend && uv run ruff check . --fix && uv run mypy .

frontend-lint:
	cd frontend && npm run lint

frontend-test:
	cd frontend && npm test -- --runInBand || npm run test

migrate:
	docker compose exec backend-api sh -c "cd /app && uv run alembic upgrade head"

seed:
	docker compose exec backend-api sh -c "cd /app && uv run python scripts/seed_dev_data.py"

