from __future__ import annotations

import time

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

_SKIP_PATHS = frozenset({"/api/v1/health", "/api/v1/readiness"})

logger = structlog.get_logger("api.access")


class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.url.path in _SKIP_PATHS:
            return await call_next(request)

        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000

        ctx = getattr(request.state, "audit_context", {})
        log = logger.bind(
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=round(duration_ms, 2),
            request_id=ctx.get("request_id"),
            trace_id=ctx.get("trace_id"),
            ip=ctx.get("ip"),
            user_agent=ctx.get("user_agent"),
        )

        if response.status_code >= 500:
            log.error("request")
        elif response.status_code >= 400:
            log.warning("request")
        else:
            log.info("request")
        return response
