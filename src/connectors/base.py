"""Async HTTP client with retry support for data connectors."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Mapping
from typing import Any, Protocol, runtime_checkable

import httpx

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT: float = 30.0


@runtime_checkable
class HttpClientProtocol(Protocol):
    """Protocol defining the HTTP client interface.

    Any class implementing ``get_bytes`` and ``get_text`` with compatible
    signatures satisfies this protocol without explicit registration.
    """

    async def get_bytes(
        self,
        url: str,
        *,
        params: Mapping[str, Any] | None = ...,
        headers: dict[str, str] | None = ...,
        follow_redirects: bool = ...,
    ) -> bytes: ...

    async def get_text(
        self,
        url: str,
        *,
        encoding: str = ...,
        params: Mapping[str, Any] | None = ...,
        headers: dict[str, str] | None = ...,
    ) -> str: ...


class HttpClient:
    """Async HTTP client with exponential backoff retry."""

    def __init__(
        self,
        base_url: str | None = None,
        timeout: float = 30.0,
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ) -> None:
        self._client: httpx.AsyncClient | None = None
        if max_retries < 1:
            raise ValueError("max_retries must be >= 1")
        self.base_url = (base_url or "").rstrip("/")
        self._timeout = httpx.Timeout(timeout)
        self._max_retries = max_retries
        self._retry_delay = retry_delay

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=self._timeout)
        return self._client

    async def close(self) -> None:
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    def __del__(self) -> None:
        if self._client is not None and not self._client.is_closed:
            logger.warning("HttpClient %r was not closed before garbage collection", self)

    def _build_url(self, url: str) -> str:
        if url.startswith("http"):
            return url
        return f"{self.base_url}/{url.lstrip('/')}" if self.base_url else url

    async def get_bytes(
        self,
        url: str,
        *,
        params: Mapping[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        follow_redirects: bool = True,
    ) -> bytes:
        """Fetch raw bytes from a URL with retry logic."""
        full_url = self._build_url(url)

        last_error: Exception | None = None
        client = await self._get_client()
        for attempt in range(1, self._max_retries + 1):
            try:
                response = await client.get(full_url, params=params, headers=headers, follow_redirects=follow_redirects)
                response.raise_for_status()
                return response.content
            except (TimeoutError, httpx.HTTPError) as exc:
                last_error = exc
                if attempt < self._max_retries:
                    delay = self._retry_delay * (2 ** (attempt - 1))
                    logger.warning(
                        "Attempt %d failed for %s: %s. Retrying in %.1fs...",
                        attempt,
                        full_url,
                        exc,
                        delay,
                    )
                    await asyncio.sleep(delay)

        if last_error is None:
            raise RuntimeError(f"No attempts made for {full_url}")
        raise last_error

    async def get_text(
        self,
        url: str,
        *,
        encoding: str = "utf-8",
        params: Mapping[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> str:
        """Fetch text content from a URL."""
        raw = await self.get_bytes(url, params=params, headers=headers)
        return raw.decode(encoding)
