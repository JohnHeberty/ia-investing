from __future__ import annotations

import logging
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import structlog
import structlog.contextvars

from ia_investing.logging_config import get_log_context, setup_logging


def _make_settings(**overrides: Any) -> MagicMock:
    settings = MagicMock()
    settings.application.environment = overrides.get("environment", "development")
    settings.application.log_level = overrides.get("log_level", "DEBUG")
    settings.log.dir = overrides.get("log_dir", "/tmp/test-logs")
    settings.log.max_bytes = overrides.get("max_bytes", 1048576)
    settings.log.backup_count = overrides.get("backup_count", 3)
    return settings


class TestSetupLogging:
    def test_configures_structlog_without_error(self, tmp_path: Path) -> None:
        settings = _make_settings(log_dir=str(tmp_path))
        setup_logging(settings)

        root = logging.getLogger()
        assert any(
            isinstance(h, logging.StreamHandler) and h.stream is not None
            for h in root.handlers
        )

    def test_sets_correct_log_level(self, tmp_path: Path) -> None:
        settings = _make_settings(log_dir=str(tmp_path), log_level="WARNING")
        setup_logging(settings)

        assert logging.getLogger().level == logging.WARNING

    def test_creates_log_directory(self) -> None:
        log_dir = Path("/tmp/test-logging-config-create-dir")
        if log_dir.exists():
            import shutil
            shutil.rmtree(log_dir)
        settings = _make_settings(log_dir=str(log_dir))
        setup_logging(settings)

        assert log_dir.exists()
        import shutil
        shutil.rmtree(log_dir, ignore_errors=True)

    def test_removes_existing_handlers(self, tmp_path: Path) -> None:
        root = logging.getLogger()
        dummy = logging.Handler()
        root.addHandler(dummy)

        settings = _make_settings(log_dir=str(tmp_path))
        setup_logging(settings)

        assert dummy not in root.handlers

    def test_adds_rotating_file_handlers(self, tmp_path: Path) -> None:
        settings = _make_settings(log_dir=str(tmp_path))
        setup_logging(settings)

        root = logging.getLogger()
        rotating = [h for h in root.handlers if isinstance(h, logging.handlers.RotatingFileHandler)]
        assert len(rotating) == 2
        filenames = {Path(h.baseFilename).name for h in rotating}
        assert filenames == {"errors.log", "app.log"}

    def test_suppresses_uvicorn_access(self, tmp_path: Path) -> None:
        settings = _make_settings(log_dir=str(tmp_path))
        setup_logging(settings)

        assert logging.getLogger("uvicorn.access").level == logging.WARNING


class TestGetLogContext:
    def test_returns_dict_with_expected_keys(self) -> None:
        ctx = get_log_context()
        assert isinstance(ctx, dict)
        for key in ("request_id", "trace_id", "ip", "user_agent", "status_code", "duration_ms"):
            assert key in ctx

    def test_returns_none_for_unset_contextvars(self) -> None:
        structlog.contextvars.clear_contextvars()
        ctx = get_log_context()
        assert ctx["request_id"] is None
        assert ctx["ip"] is None

    def test_reads_bound_contextvars(self) -> None:
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id="test-123", ip="10.0.0.1")
        try:
            ctx = get_log_context()
            assert ctx["request_id"] == "test-123"
            assert ctx["ip"] == "10.0.0.1"
        finally:
            structlog.contextvars.clear_contextvars()

    def test_unbind_removes_key(self) -> None:
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id="abc")
        structlog.contextvars.unbind_contextvars("request_id")
        ctx = get_log_context()
        assert ctx["request_id"] is None
