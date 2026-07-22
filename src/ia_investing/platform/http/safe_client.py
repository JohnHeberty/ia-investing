from __future__ import annotations

import asyncio
import ipaddress
import socket
from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from urllib.parse import urljoin, urlsplit, urlunsplit

import httpx


class UnsafeUrlError(ValueError):
    """Raised when a dynamic outbound URL violates the egress policy."""


@dataclass(frozen=True, slots=True)
class EgressPolicy:
    """Policy applied to every dynamic outbound request and redirect.

    DNS is checked before each request. Production deployments must additionally
    enforce network-level egress controls because application-only DNS validation
    cannot fully eliminate DNS rebinding between validation and connection.
    """

    allowed_host_suffixes: tuple[str, ...] = ()
    require_https: bool = True
    allowed_ports: frozenset[int] = frozenset({443})
    maximum_redirects: int = 5
    maximum_response_bytes: int = 5 * 1024 * 1024
    timeout_seconds: float = 20.0
    allowed_content_types: tuple[str, ...] = (
        "text/html",
        "text/plain",
        "text/csv",
        "application/pdf",
        "application/json",
        "application/xml",
        "text/xml",
    )
    user_agent: str = "IA-Investing-Source-Validator/1.0"

    def __post_init__(self) -> None:
        if self.maximum_redirects < 0:
            raise ValueError("maximum_redirects must be non-negative")
        if self.maximum_response_bytes <= 0:
            raise ValueError("maximum_response_bytes must be positive")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        normalized = tuple(_normalize_policy_host(value) for value in self.allowed_host_suffixes)
        object.__setattr__(self, "allowed_host_suffixes", normalized)


@dataclass(frozen=True, slots=True)
class ValidatedHttpResponse:
    requested_url: str
    final_url: str
    status_code: int
    headers: Mapping[str, str]
    content: bytes
    redirect_chain: tuple[str, ...]
    resolved_ips: tuple[str, ...]


@dataclass(slots=True)
class SafeHttpClient:
    policy: EgressPolicy
    _client: httpx.AsyncClient | None = field(default=None, init=False, repr=False)

    async def __aenter__(self) -> SafeHttpClient:
        await self.open()
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:  # type: ignore[no-untyped-def]
        await self.close()

    async def open(self) -> None:
        if self._client is None:
            self._client = httpx.AsyncClient(
                follow_redirects=False,
                timeout=httpx.Timeout(self.policy.timeout_seconds),
                trust_env=False,
                headers={"User-Agent": self.policy.user_agent},
            )

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def get(self, url: str) -> ValidatedHttpResponse:
        await self.open()
        assert self._client is not None
        requested_url = normalize_and_validate_url(url, self.policy)
        current_url = requested_url
        redirect_chain: list[str] = []
        all_ips: set[str] = set()

        for redirect_number in range(self.policy.maximum_redirects + 1):
            parsed = urlsplit(current_url)
            port = parsed.port or (443 if parsed.scheme == "https" else 80)
            resolved = await resolve_public_ips(parsed.hostname or "", port)
            all_ips.update(str(ip) for ip in resolved)

            async with self._client.stream("GET", current_url) as response:
                if response.status_code in {301, 302, 303, 307, 308}:
                    location = response.headers.get("location")
                    if not location:
                        raise UnsafeUrlError("redirect response does not contain Location")
                    if redirect_number >= self.policy.maximum_redirects:
                        raise UnsafeUrlError("maximum redirect count exceeded")
                    next_url = urljoin(current_url, location)
                    current_url = normalize_and_validate_url(next_url, self.policy)
                    redirect_chain.append(current_url)
                    continue

                _validate_content_type(response.headers.get("content-type"), self.policy)
                content = await _read_limited(response, self.policy.maximum_response_bytes)
                headers = MappingProxyType({key.lower(): value for key, value in response.headers.items()})
                return ValidatedHttpResponse(
                    requested_url=requested_url,
                    final_url=current_url,
                    status_code=response.status_code,
                    headers=headers,
                    content=content,
                    redirect_chain=tuple(redirect_chain),
                    resolved_ips=tuple(sorted(all_ips)),
                )

        raise UnsafeUrlError("redirect processing did not produce a response")


async def _read_limited(response: httpx.Response, maximum_bytes: int) -> bytes:
    chunks: list[bytes] = []
    total = 0
    async for chunk in response.aiter_bytes():
        total += len(chunk)
        if total > maximum_bytes:
            raise UnsafeUrlError("response exceeds maximum_response_bytes")
        chunks.append(chunk)
    return b"".join(chunks)


def normalize_and_validate_url(url: str, policy: EgressPolicy) -> str:
    value = url.strip()
    if not value:
        raise UnsafeUrlError("URL is empty")
    parsed = urlsplit(value)
    scheme = parsed.scheme.lower()
    if policy.require_https and scheme != "https":
        raise UnsafeUrlError("only HTTPS URLs are allowed")
    if scheme not in {"https", "http"}:
        raise UnsafeUrlError("unsupported URL scheme")
    if parsed.username is not None or parsed.password is not None:
        raise UnsafeUrlError("embedded URL credentials are forbidden")
    if not parsed.hostname:
        raise UnsafeUrlError("URL host is missing")
    host = _normalize_host(parsed.hostname)
    _validate_hostname(host)
    _validate_host_allowlist(host, policy.allowed_host_suffixes)
    port = parsed.port or (443 if scheme == "https" else 80)
    if port not in policy.allowed_ports:
        raise UnsafeUrlError(f"port {port} is not allowed")
    try:
        literal_ip = ipaddress.ip_address(host.strip("[]"))
    except ValueError:
        literal_ip = None
    if literal_ip is not None and not literal_ip.is_global:
        raise UnsafeUrlError(f"non-public IP address is forbidden: {literal_ip}")
    netloc = host
    if ":" in host and not host.startswith("["):
        netloc = f"[{host}]"
    default_port = 443 if scheme == "https" else 80
    if port != default_port:
        netloc = f"{netloc}:{port}"
    path = parsed.path or "/"
    return urlunsplit((scheme, netloc, path, parsed.query, ""))


async def resolve_public_ips(host: str, port: int) -> tuple[ipaddress.IPv4Address | ipaddress.IPv6Address, ...]:
    normalized = _normalize_host(host)
    try:
        literal = ipaddress.ip_address(normalized.strip("[]"))
    except ValueError:
        literal = None
    if literal is not None:
        if not literal.is_global:
            raise UnsafeUrlError(f"non-public IP address is forbidden: {literal}")
        return (literal,)

    try:
        records = await asyncio.to_thread(
            socket.getaddrinfo,
            normalized,
            port,
            type=socket.SOCK_STREAM,
        )
    except socket.gaierror as exc:
        raise UnsafeUrlError(f"DNS resolution failed for {normalized}") from exc
    addresses: set[ipaddress.IPv4Address | ipaddress.IPv6Address] = set()
    for record in records:
        address = ipaddress.ip_address(record[4][0])
        if not address.is_global:
            raise UnsafeUrlError(f"host {normalized} resolves to non-public address {address}")
        addresses.add(address)
    if not addresses:
        raise UnsafeUrlError(f"DNS resolution returned no addresses for {normalized}")
    return tuple(sorted(addresses, key=lambda value: (value.version, int(value))))


def _validate_content_type(value: str | None, policy: EgressPolicy) -> None:
    if not value:
        raise UnsafeUrlError("response Content-Type is missing")
    media_type = value.split(";", 1)[0].strip().lower()
    if media_type not in policy.allowed_content_types:
        raise UnsafeUrlError(f"response Content-Type is not allowed: {media_type}")


def _normalize_policy_host(value: str) -> str:
    host = value.strip().lower().lstrip(".")
    if not host:
        raise ValueError("allowed host suffix cannot be empty")
    return _normalize_host(host)


def _normalize_host(value: str) -> str:
    host = value.strip().rstrip(".").lower()
    try:
        return host.encode("idna").decode("ascii")
    except UnicodeError as exc:
        raise UnsafeUrlError("invalid internationalized hostname") from exc


def _validate_hostname(host: str) -> None:
    forbidden = {
        "localhost",
        "localhost.localdomain",
        "metadata",
        "metadata.google.internal",
        "instance-data",
    }
    if host in forbidden or host.endswith(".localhost") or host.endswith(".local"):
        raise UnsafeUrlError(f"forbidden hostname: {host}")
    if len(host) > 253:
        raise UnsafeUrlError("hostname is too long")


def _validate_host_allowlist(host: str, suffixes: tuple[str, ...]) -> None:
    if not suffixes:
        return
    if any(host == suffix or host.endswith(f".{suffix}") for suffix in suffixes):
        return
    raise UnsafeUrlError(f"host is outside the egress allowlist: {host}")
