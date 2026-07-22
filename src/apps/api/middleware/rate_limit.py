from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from functools import wraps
from typing import Any, ParamSpec, TypeVar

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

logger = logging.getLogger(__name__)

P = ParamSpec("P")
R = TypeVar("R")


class SlidingWindowCounter:
    def __init__(self, max_requests: int, window_seconds: float) -> None:
        self._max_requests = max_requests
        self._window_seconds = window_seconds
        self._lock = asyncio.Lock()

    async def is_allowed(self, key: str) -> bool:
        now = time.monotonic()
        async with self._lock:
            if not hasattr(self, "_windows"):
                self._windows: dict[str, list[float]] = {}
            timestamps = self._windows.get(key, [])
            cutoff = now - self._window_seconds
            timestamps = [ts for ts in timestamps if ts > cutoff]
            if len(timestamps) >= self._max_requests:
                self._windows[key] = timestamps
                return False
            timestamps.append(now)
            self._windows[key] = timestamps
            return True

    async def retry_after(self, key: str) -> float:
        now = time.monotonic()
        async with self._lock:
            if hasattr(self, "_windows"):
                timestamps = self._windows.get(key, [])
                if timestamps:
                    return self._window_seconds - (now - timestamps[0])
            return 0.0


_global_limiter = SlidingWindowCounter(1000, 60.0)
_auth_limiter = SlidingWindowCounter(10, 60.0)
_api_limiter = SlidingWindowCounter(100, 60.0)


def _get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    client = request.client
    return client.host if client else "unknown"


def rate_limit(
    resource: str,
    max_requests: int = 100,
    window_seconds: float = 60.0,
) -> Callable[[Callable[P, Awaitable[R]]], Callable[P, Awaitable[R]]]:
    limiter = SlidingWindowCounter(max_requests, window_seconds)

    def decorator(handler: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
        @wraps(handler)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            request = _find_request(args, kwargs)
            if request is not None:
                key = f"{resource}:{_get_client_ip(request)}"
                if not await limiter.is_allowed(key):
                    retry = int(await limiter.retry_after(key))
                    raise _rate_limit_exception(retry)
            return await handler(*args, **kwargs)

        return wrapper

    return decorator


def _find_request(args: tuple[Any, ...], kwargs: dict[str, Any]) -> Request | None:
    for arg in args:
        if isinstance(arg, Request):
            return arg
    for value in kwargs.values():
        if isinstance(value, Request):
            return value
    return None


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        client_ip = _get_client_ip(request)
        path = request.url.path

        if not await _global_limiter.is_allowed(f"global:{client_ip}"):
            return _rate_limit_response()

        is_auth_path = path.startswith("/api/v1/auth") or path.startswith("/auth")
        if is_auth_path and not await _auth_limiter.is_allowed(f"auth:{client_ip}"):
            return _rate_limit_response()

        if not await _api_limiter.is_allowed(f"api:{client_ip}"):
            return _rate_limit_response()

        return await call_next(request)


def _rate_limit_response() -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={"detail": "Too many requests. Please try again later."},
        headers={"Retry-After": "60"},
    )


class RateLimitExceededError(Exception):
    def __init__(self, retry_after: int = 60) -> None:
        self.retry_after = retry_after
        super().__init__(f"Rate limit exceeded. Retry after {retry_after} seconds")


def _rate_limit_exception(retry_after: int = 60) -> RateLimitExceededError:
    return RateLimitExceededError(retry_after)
