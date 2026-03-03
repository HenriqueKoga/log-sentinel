FROM python:3.14.2-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_DEFAULT_TIMEOUT=100

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends build-essential && \
    pip install --no-cache-dir uv && \
    apt-get purge -y build-essential && apt-get autoremove -y && rm -rf /var/lib/apt/lists/*

# copy project config, migrations, source, and scripts into the image
COPY pyproject.toml README.md alembic.ini ./
COPY alembic ./alembic
COPY logs_sentinel ./logs_sentinel
COPY scripts ./scripts

RUN uv sync

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "logs_sentinel.main:app", "--host", "0.0.0.0", "--port", "8000"]

