from __future__ import annotations

import socket
from dataclasses import dataclass

from ia_investing.settings import Settings, get_settings


@dataclass(frozen=True, slots=True)
class EgressRule:
    host: str
    port: int
    protocol: str = "tcp"
    purpose: str = ""
    required_for: str = ""


EGRESS_ALLOWLIST: list[EgressRule] = []


def _resolve_host(host: str) -> str:
    try:
        return str(socket.gethostbyname(host))
    except OSError:
        return host


def get_allowed_egress_rules(settings: Settings | None = None) -> list[EgressRule]:
    if settings is None:
        settings = get_settings()

    rules: list[EgressRule] = [
        EgressRule(
            host=_resolve_host("api.openai.com"),
            port=443,
            protocol="tcp",
            purpose="OpenAI API",
            required_for="AI provider (LLM calls)",
        ),
        EgressRule(
            host=_resolve_host("api.anthropic.com"),
            port=443,
            protocol="tcp",
            purpose="Anthropic API",
            required_for="AI provider (LLM calls)",
        ),
    ]

    oidc_host = _resolve_host("localhost")
    rules.append(
        EgressRule(
            host=oidc_host,
            port=443,
            protocol="tcp",
            purpose="OIDC provider",
            required_for="Authentication",
        )
    )

    db_host, db_port_str = settings.database.url.split("://", 1)[1].split("@")[-1].split(":")
    db_port = int(db_port_str.split("/")[0])
    rules.append(
        EgressRule(
            host=_resolve_host(db_host),
            port=db_port,
            protocol="tcp",
            purpose="PostgreSQL",
            required_for="Database persistence",
        )
    )

    storage_host = settings.storage.endpoint.split("://", 1)[1].split(":")[0]
    storage_port = int(settings.storage.endpoint.split(":")[-1])
    rules.append(
        EgressRule(
            host=_resolve_host(storage_host),
            port=storage_port,
            protocol="tcp",
            purpose="MinIO storage",
            required_for="Object storage",
        )
    )

    temporal_host = settings.temporal.address.split(":")[0]
    temporal_port = int(settings.temporal.address.split(":")[1])
    rules.append(
        EgressRule(
            host=_resolve_host(temporal_host),
            port=temporal_port,
            protocol="tcp",
            purpose="Temporal server",
            required_for="Workflow orchestration",
        )
    )

    return rules


def validate_egress(settings: Settings | None = None) -> list[EgressRule]:
    allowed = get_allowed_egress_rules(settings)
    violations: list[EgressRule] = []

    for rule in allowed:
        try:
            addrinfos = socket.getaddrinfo(rule.host, rule.port, socket.AF_UNSPEC, socket.SOCK_STREAM)
            connected = False
            for family, socktype, proto, _canonname, sockaddr in addrinfos:
                try:
                    with socket.socket(family, socktype, proto) as sock:
                        sock.settimeout(2.0)
                        if sock.connect_ex(sockaddr) == 0:
                            connected = True
                            break
                except OSError:
                    continue
            if not connected:
                violations.append(rule)
        except OSError:
            violations.append(rule)

    return violations
