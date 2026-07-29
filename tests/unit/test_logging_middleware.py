from __future__ import annotations

import logging
from unittest.mock import MagicMock, patch

import pytest
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
    @patch("apps.api.middleware.logging.logging.getLogger")
    def test_2xx_logs_at_info(self, mock_get_logger: MagicMock, client: TestClient) -> None:
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger

        client.get("/api/v1/ok")

        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args
        assert call_args[0][0] == "request"
        assert call_args[1]["status_code"] == 200
        assert call_args[1]["method"] == "GET"
        assert call_args[1]["path"] == "/api/v1/ok"
        assert "duration_ms" in call_args[1]

    @patch("apps.api.middleware.logging.logging.getLogger")
    def test_4xx_logs_at_warning(self, mock_get_logger: MagicMock, client: TestClient) -> None:
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger

        client.get("/api/v1/warn")

        mock_logger.warning.assert_called_once()
        call_args = mock_logger.warning.call_args
        assert call_args[1]["status_code"] == 400

    @patch("apps.api.middleware.logging.logging.getLogger")
    def test_5xx_logs_at_error(self, mock_get_logger: MagicMock, client: TestClient) -> None:
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger

        client.get("/api/v1/error")

        mock_logger.error.assert_called_once()
        call_args = mock_logger.error.call_args
        assert call_args[1]["status_code"] == 500

    @patch("apps.api.middleware.logging.logging.getLogger")
    def test_health_excluded_from_logging(self, mock_get_logger: MagicMock, client: TestClient) -> None:
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger

        client.get("/api/v1/health")

        mock_logger.info.assert_not_called()
        mock_logger.warning.assert_not_called()
        mock_logger.error.assert_not_called()

    @patch("apps.api.middleware.logging.logging.getLogger")
    def test_readiness_excluded_from_logging(self, mock_get_logger: MagicMock, client: TestClient) -> None:
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger

        client.get("/api/v1/readiness")

        mock_logger.info.assert_not_called()
        mock_logger.warning.assert_not_called()
        mock_logger.error.assert_not_called()

    @patch("apps.api.middleware.logging.logging.getLogger")
    def test_log_includes_audit_context_fields(self, mock_get_logger: MagicMock, client: TestClient) -> None:
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger

        client.get("/api/v1/ok")

        call_kwargs = mock_logger.info.call_args[1]
        assert "request_id" in call_kwargs
        assert "ip" in call_kwargs
        assert "user_agent" in call_kwargs
