from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import Counter, Histogram, generate_latest
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from logs_sentinel.infrastructure.settings.config import settings

logger = structlog.get_logger(__name__)

REQUEST_COUNT = Counter("http_requests_total", "Total HTTP requests", ["method", "path", "status"])
REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds", "HTTP request latency (seconds)", ["method", "path"]
)


class MetricsMiddleware(BaseHTTPMiddleware):
    """Basic Prometheus metrics middleware."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        method = request.method
        path = request.url.path
        with REQUEST_LATENCY.labels(method=method, path=path).time():
            response = await call_next(request)
        REQUEST_COUNT.labels(method=method, path=path, status=response.status_code).inc()
        return response


async def metrics_endpoint() -> Response:
    """Expose Prometheus metrics."""
    content: bytes = generate_latest()
    return Response(content=content, media_type="text/plain; version=0.0.4")


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Lifespan hook for startup/shutdown."""

    logger.info("logs_sentinel.startup", environment=settings.environment)
    try:
        yield
    finally:
        logger.info("logs_sentinel.shutdown")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application instance."""

    app = FastAPI(
        title="LogSentinel API",
        version="0.1.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )

    app.add_middleware(MetricsMiddleware)

    # CORS for frontend SPA. In local/dev allow any origin so preflight (OPTIONS) never returns 400.
    if settings.environment in ("local", "dev"):
        cors_origins: list[str] = ["*"]
        allow_credentials = False
    else:
        cors_origins = [str(o) for o in settings.frontend_dev_origins]
        if settings.frontend_origin:
            origin_str = str(settings.frontend_origin)
            if origin_str not in cors_origins:
                cors_origins.append(origin_str)
        allow_credentials = True

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
        allow_credentials=allow_credentials,
    )

    from logs_sentinel.api.v1.routers import (
        ai_insights,
        alerts,
        auth,
        billing,
        chat,
        ingest,
        issues,
        logs,
        metrics,
        projects,
    )

    app.include_router(auth.router, prefix="/api/v1")
    app.include_router(projects.router, prefix="/api/v1")
    app.include_router(issues.router, prefix="/api/v1")
    app.include_router(alerts.router, prefix="/api/v1")
    app.include_router(billing.router, prefix="/api/v1")
    app.include_router(ingest.router, prefix="/api/v1")
    app.include_router(logs.router, prefix="/api/v1")
    app.include_router(metrics.router, prefix="/api/v1")
    app.include_router(ai_insights.router, prefix="/api/v1")
    app.include_router(chat.router, prefix="/api/v1")

    @app.get("/metrics")
    async def serve_metrics() -> Response:
        return await metrics_endpoint()

    @app.get("/health", tags=["internal"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
