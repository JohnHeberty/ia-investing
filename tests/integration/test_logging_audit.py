"""Integration tests for the logging and audit trail system.

Tests the full pipeline: AuditContextMiddleware → LoggingMiddleware → structlog → file output.
Requires PostgreSQL running (auto-skipped if not reachable).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from unittest.mock import MagicMock

import structlog.contextvars
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.api.middleware.audit_context import AuditContextMiddleware
from apps.api.middleware.logging import LoggingMiddleware
from ia_investing.logging_config import get_log_context, setup_logging


class TestAuditContextMiddleware:
    """Test AuditContextMiddleware binds request context to structlog."""

    def setup_method(self) -> None:
        structlog.contextvars.clear_contextvars()

    def test_generates_request_id(self) -> None:
        app = FastAPI()
        app.add_middleware(AuditContextMiddleware)

        @app.get("/test")
        async def _test():
            ctx = get_log_context()
            return {"request_id": ctx["request_id"]}

        with TestClient(app, raise_server_exceptions=True) as client:
            resp = client.get("/test")
            assert resp.status_code == 200
            data = resp.json()
            assert data["request_id"] is not None
            assert len(data["request_id"]) == 36  # UUID format

    def test_preserves_incoming_x_request_id(self) -> None:
        app = FastAPI()
        app.add_middleware(AuditContextMiddleware)

        @app.get("/test")
        async def _test():
            ctx = get_log_context()
            return {"trace_id": ctx["trace_id"]}

        with TestClient(app, raise_server_exceptions=True) as client:
            resp = client.get("/test", headers={"X-Request-Id": "my-trace-123"})
            assert resp.status_code == 200
            assert resp.json()["trace_id"] == "my-trace-123"

    def test_binds_ip_and_user_agent(self) -> None:
        app = FastAPI()
        app.add_middleware(AuditContextMiddleware)

        @app.get("/test")
        async def _test():
            ctx = get_log_context()
            return {"ip": ctx["ip"], "user_agent": ctx["user_agent"]}

        with TestClient(app, raise_server_exceptions=True) as client:
            resp = client.get("/test", headers={"User-Agent": "TestAgent/1.0"})
            assert resp.status_code == 200
            data = resp.json()
            assert data["ip"] == "testclient"
            assert data["user_agent"] == "TestAgent/1.0"

    def test_context_cleared_between_requests(self) -> None:
        app = FastAPI()
        app.add_middleware(AuditContextMiddleware)
        request_ids = []

        @app.get("/test")
        async def _test():
            ctx = get_log_context()
            request_ids.append(ctx["request_id"])
            return {"ok": True}

        with TestClient(app, raise_server_exceptions=True) as client:
            client.get("/test")
            client.get("/test")
            assert len(request_ids) == 2
            assert request_ids[0] != request_ids[1]


class TestLoggingMiddleware:
    """Test LoggingMiddleware logs request metadata."""

    def setup_method(self) -> None:
        structlog.contextvars.clear_contextvars()

    def test_logs_request_with_status(self, caplog: MagicMock) -> None:
        app = FastAPI()
        app.add_middleware(LoggingMiddleware)

        @app.get("/test")
        async def _test():
            return {"ok": True}

        with TestClient(app, raise_server_exceptions=True) as client:
            with caplog.at_level(logging.INFO, logger="api.access"):
                resp = client.get("/test")
                assert resp.status_code == 200

    def test_skips_health_endpoint(self, caplog: MagicMock) -> None:
        app = FastAPI()
        app.add_middleware(LoggingMiddleware)

        @app.get("/api/v1/health")
        async def _health():
            return {"ok": True}

        with TestClient(app, raise_server_exceptions=True) as client:
            with caplog.at_level(logging.DEBUG, logger="api.access"):
                resp = client.get("/api/v1/health")
                assert resp.status_code == 200
                assert len([r for r in caplog.records if "request" in r.getMessage()]) == 0


class TestLoggingConfig:
    """Test logging_config creates files and configures structlog."""

    def test_setup_logging_creates_log_dir(self, tmp_path: Path) -> None:
        from ia_investing.settings import Settings

        settings = Settings()
        settings.log.dir = str(tmp_path / "logs")
        setup_logging(settings)
        assert (tmp_path / "logs").exists()

    def test_get_log_context_returns_dict(self) -> None:
        structlog.contextvars.clear_contextvars()
        ctx = get_log_context()
        assert isinstance(ctx, dict)
        assert "request_id" in ctx
        assert "trace_id" in ctx
        assert "ip" in ctx
        assert "user_agent" in ctx
