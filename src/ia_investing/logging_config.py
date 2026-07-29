from __future__ import annotations

import logging
import logging.handlers
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

    root = logging.getLogger()
    root.setLevel(log_level)

    for handler in root.handlers[:]:
        root.removeHandler(handler)

    stdout_handler = logging.StreamHandler(stream=sys.stdout)
    stdout_handler.setLevel(log_level)
    stdout_handler.setFormatter(logging.Formatter("%(message)s"))
    root.addHandler(stdout_handler)

    error_handler = logging.handlers.RotatingFileHandler(
        filename=str(log_dir / "errors.log"),
        maxBytes=settings.log.max_bytes,
        backupCount=settings.log.backup_count,
        encoding="utf-8",
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(logging.Formatter("%(message)s"))
    root.addHandler(error_handler)

    app_handler = logging.handlers.RotatingFileHandler(
        filename=str(log_dir / "app.log"),
        maxBytes=settings.log.max_bytes,
        backupCount=settings.log.backup_count,
        encoding="utf-8",
    )
    app_handler.setLevel(log_level)
    app_handler.setFormatter(logging.Formatter("%(message)s"))
    root.addHandler(app_handler)

    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


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
