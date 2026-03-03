#!/usr/bin/env bash
set -euo pipefail

echo "Waiting for postgres..."
until pg_isready -h postgres -U logs_sentinel >/dev/null 2>&1; do
  sleep 2
done

echo "Running migrations..."
cd /app/backend
uv run alembic upgrade head

echo "Seeding dev data..."
uv run python ../scripts/seed_dev_data.py

echo "DB init complete."

