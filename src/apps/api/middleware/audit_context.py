from __future__ import annotations

from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response


class AuditContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = str(uuid4())
        trace_id = request.headers.get("X-Trace-Id") or request_id
        ip = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("User-Agent", "unknown")

        request.state.audit_context = {
            "request_id": request_id,
            "trace_id": trace_id,
            "ip": ip,
            "user_agent": user_agent,
        }

        return await call_next(request)
