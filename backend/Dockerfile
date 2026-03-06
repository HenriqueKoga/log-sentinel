FROM python:3.14.2-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends build-essential curl && \
    curl -LsSf https://astral.sh/uv/install.sh | sh && \
    rm -rf /var/lib/apt/lists/*
ENV PATH="/root/.local/bin:$PATH"

ENV UV_PYTHON_DOWNLOADS=0

COPY pyproject.toml uv.lock README.md alembic.ini ./
COPY alembic ./alembic
COPY logs_sentinel ./logs_sentinel
COPY scripts ./scripts

RUN uv sync --no-dev

FROM python:3.14.2-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY --from=builder /app /app

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

CMD ["uvicorn", "logs_sentinel.main:app", "--host", "0.0.0.0", "--port", "8000"]

