from __future__ import annotations

import ipaddress
import logging
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from ia_investing.application.audit import emit_security_event
from ia_investing.settings import get_settings

logger = logging.getLogger(__name__)

_PRIVATE_IPV4_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
]

_PRIVATE_IPV6_NETWORKS = [
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
]


def _is_private_ip(host: str) -> bool:
    try:
        addr = ipaddress.ip_address(host)
        if isinstance(addr, ipaddress.IPv4Address):
            return any(addr in net for net in _PRIVATE_IPV4_NETWORKS)
        return any(addr in net for net in _PRIVATE_IPV6_NETWORKS)
    except ValueError:
        return False


def _is_host_allowed(host: str, allowed_hosts: set[str]) -> bool:
    return host in allowed_hosts


class SSRFProtectionMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        settings = get_settings()
        allowed_hosts = set(settings.security.ssrf_allowed_internal_hosts)

        response = await call_next(request)

        request_host = request.url.hostname
        if request_host and _is_private_ip(request_host) and not _is_host_allowed(request_host, allowed_hosts):
            emit_security_event(
                "ssrf_blocked",
                detail=f"Blocked request to private IP: {request_host}",
                source_ip=request.client.host if request.client else "unknown",
            )
            logger.warning("SSRF blocked request to %s", request_host)

        return response
