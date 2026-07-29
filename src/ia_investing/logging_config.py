from __future__ import annotations

import logging
import logging.config
import sys
from pathlib import Path
from typing import Any

import structlog
from structlog.processors import (
    CallsiteParameter,
    CallsiteParameterAdder,
    JSONRenderer,
    TimeStamper,
)
from structlog.stdlib import (
    LoggerFactory,
    PositionalArgumentsFormatter,
    StackInfoRenderer,
    add_log_level,
    add_logger_name,
    filter_by_level,
)

from ia_investing.settings import Settings


def setup_logging(settings: Settings) -> None:
    is_prod = settings.application.environment == "production"
    log_dir = Path(settings.log.dir)
    log_dir.mkdir(parents=True, exist_ok=True)

    log_level = getattr(logging, settings.application.log_level)

    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        filter_by_level,
        add_logger_name,
        add_log_level,
        PositionalArgumentsFormatter(),
        TimeStamper(fmt="iso"),
        StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        CallsiteParameterAdder({CallsiteParameter.FILENAME, CallsiteParameter.FUNC_NAME, CallsiteParameter.LINENO}),
    ]

    if is_prod:
        renderer: structlog.types.Processor = JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer()

    structlog.configure(
        processors=[*shared_processors, renderer],
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    logging.config.dictConfig({
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "raw": {"format": "%(message)s"},
        },
        "handlers": {
            "stdout": {
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stdout",
                "level": log_level,
                "formatter": "raw",
            },
            "file": {
                "class": "logging.handlers.RotatingFileHandler",
                "filename": str(log_dir / "app.log"),
                "maxBytes": settings.log.max_bytes,
                "backupCount": settings.log.backup_count,
                "encoding": "utf-8",
                "level": log_level,
                "formatter": "raw",
            },
            "error_file": {
                "class": "logging.handlers.RotatingFileHandler",
                "filename": str(log_dir / "errors.log"),
                "maxBytes": settings.log.max_bytes,
                "backupCount": settings.log.backup_count,
                "encoding": "utf-8",
                "level": logging.ERROR,
                "formatter": "raw",
            },
        },
        "root": {
            "level": log_level,
            "handlers": ["stdout", "file", "error_file"],
        },
        "loggers": {
            "uvicorn.access": {"level": "WARNING"},
            "uvicorn.error": {"level": "WARNING"},
            "httpx": {"level": "WARNING"},
            "httpcore": {"level": "WARNING", "propagate": False},
            "sqlalchemy": {"level": "WARNING", "propagate": False},
            "grpc": {"level": "ERROR", "propagate": False},
            "opentelemetry": {"level": "ERROR", "propagate": False},
            "asyncio": {"level": "WARNING", "propagate": False},
            "anyio": {"level": "WARNING", "propagate": False},
            "anyio._backends._asyncio": {"level": "WARNING", "propagate": False},
        },
    })


def get_log_context() -> dict[str, Any]:
    ctx = structlog.contextvars.get_contextvars()
    return {
        "request_id": ctx.get("request_id"),
        "trace_id": ctx.get("trace_id"),
        "ip": ctx.get("ip"),
        "user_agent": ctx.get("user_agent"),
        "status_code": ctx.get("status_code"),
        "duration_ms": ctx.get("duration_ms"),
    }
