from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

PERSONA_PERMISSIONS: dict[str, frozenset[str]] = {
    "researcher": frozenset({"research:read", "research:write", "portfolio:read"}),
    "portfolio_manager": frozenset({"research:read", "portfolio:read", "portfolio:propose"}),
    "risk": frozenset({"portfolio:read", "risk:read", "risk:decide", "risk:waive"}),
    "committee": frozenset(
        {
            "portfolio:read",
            "portfolio:approve",
            "committee:vote",
            "readiness:read",
            "readiness:vote",
            "readiness:decide",
        }
    ),
    "operations": frozenset(
        {
            "portfolio:read",
            "paper_orders:operate",
            "paper_orders:kill",
            "reconciliation:write",
            "alerts:acknowledge",
            "postmortem:write",
            "readiness:submit",
        }
    ),
    "auditor": frozenset({"research:read", "portfolio:read", "risk:read", "audit:read", "readiness:read"}),
}


@dataclass(frozen=True, slots=True)
class InstitutionalAccessContext:
    subject: str
    organization_id: UUID
    team_ids: frozenset[UUID]
    permissions: frozenset[str]
    environment: str


@dataclass(frozen=True, slots=True)
class ResourceAttributes:
    organization_id: UUID
    owner_team_id: UUID | None = None
    environment: str = "paper"
    state: str | None = None


def authorize(context: InstitutionalAccessContext, permission: str, resource: ResourceAttributes) -> None:
    if context.organization_id != resource.organization_id:
        raise PermissionError("cross-organization access is forbidden")
    if permission not in context.permissions:
        raise PermissionError(f"permission required: {permission}")
    if (
        resource.owner_team_id is not None
        and resource.owner_team_id not in context.team_ids
        and "organization:admin" not in context.permissions
    ):
        raise PermissionError("resource belongs to another team")
    if resource.environment == "live" or context.environment == "live":
        raise PermissionError("live portfolio actions are disabled in phase 5")


def ensure_four_eyes(author_id: str, approver_id: str) -> None:
    if author_id == approver_id:
        raise PermissionError("author cannot approve their own action")
