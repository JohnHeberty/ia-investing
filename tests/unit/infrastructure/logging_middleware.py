from __future__ import annotations

import pytest
import structlog
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from starlette.testclient import TestClient

from apps.api.middleware.logging import LoggingMiddleware


def _build_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(LoggingMiddleware)

    @app.get("/api/v1/ok")
    async def ok() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/v1/warn")
    async def warn() -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": "bad"})

    @app.get("/api/v1/error")
    async def error() -> JSONResponse:
        return JSONResponse(status_code=500, content={"detail": "boom"})

    @app.get("/api/v1/health")
    async def health() -> dict[str, str]:
        return {"status": "healthy"}

    @app.get("/api/v1/readiness")
    async def readiness() -> dict[str, str]:
        return {"status": "ready"}

    return app


@pytest.fixture()
def client() -> TestClient:
    return TestClient(_build_app(), raise_server_exceptions=False)


class TestLoggingMiddleware:
    def test_2xx_logs_at_info(self, client: TestClient) -> None:
        with structlog.testing.capture_logs() as logs:
            client.get("/api/v1/ok")

        assert len(logs) == 1
        assert logs[0]["log_level"] == "info"
        assert logs[0]["method"] == "GET"
        assert logs[0]["path"] == "/api/v1/ok"
        assert logs[0]["status_code"] == 200
        assert "duration_ms" in logs[0]

    def test_4xx_logs_at_warning(self, client: TestClient) -> None:
        with structlog.testing.capture_logs() as logs:
            client.get("/api/v1/warn")

        assert len(logs) == 1
        assert logs[0]["log_level"] == "warning"
        assert logs[0]["status_code"] == 400

    def test_5xx_logs_at_error(self, client: TestClient) -> None:
        with structlog.testing.capture_logs() as logs:
            client.get("/api/v1/error")

        assert len(logs) == 1
        assert logs[0]["log_level"] == "error"
        assert logs[0]["status_code"] == 500

    def test_health_excluded_from_logging(self, client: TestClient) -> None:
        with structlog.testing.capture_logs() as logs:
            client.get("/api/v1/health")

        assert len(logs) == 0

    def test_readiness_excluded_from_logging(self, client: TestClient) -> None:
        with structlog.testing.capture_logs() as logs:
            client.get("/api/v1/readiness")

        assert len(logs) == 0

    def test_log_includes_audit_context_fields(self, client: TestClient) -> None:
        with structlog.testing.capture_logs() as logs:
            client.get("/api/v1/ok")

        assert len(logs) == 1
        assert "request_id" in logs[0]
        assert "ip" in logs[0]
        assert "user_agent" in logs[0]
