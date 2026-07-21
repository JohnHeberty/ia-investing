from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID


@dataclass(frozen=True, slots=True)
class ActorContext:
    subject: str
    organization_id: UUID | None
    roles: frozenset[str] = field(default_factory=frozenset)
    permissions: frozenset[str] = field(default_factory=frozenset)
    team_ids: frozenset[UUID] = field(default_factory=frozenset)
    authentication_method: str = "unknown"

    def has_permission(self, permission: str) -> bool:
        return permission in self.permissions

    def has_role(self, role: str) -> bool:
        return role in self.roles

    def belongs_to_org(self, org_id: UUID) -> bool:
        return self.organization_id is not None and self.organization_id == org_id

    def belongs_to_team(self, team_id: UUID) -> bool:
        return team_id in self.team_ids


@dataclass(frozen=True, slots=True)
class ResourceAttributes:
    resource_type: str
    organization_id: UUID | None = None
    owner_team_id: UUID | None = None
    owner_subject: str | None = None
    environment: str = "paper"
    state: str | None = None
    custom_attributes: dict[str, object] = field(default_factory=dict)


class PolicyEngine:
    def __init__(self) -> None:
        self._global_overrides: dict[str, frozenset[str]] = {
            "admin": frozenset({"*"}),
            "organization:admin": frozenset({"organization:*"}),
        }

    def enforce(
        self,
        resource: str,
        action: str,
        context: ActorContext,
        resource_attrs: ResourceAttributes | None = None,
    ) -> bool:
        for role, permissions in self._global_overrides.items():
            if context.has_role(role) and ("*" in permissions or f"{resource}:*" in permissions):
                return True

        required_permission = f"{resource}:{action}"
        if context.has_permission(required_permission) or context.has_permission(f"{resource}:*"):
            if resource_attrs is None:
                return True
            return self._check_abac(context, resource_attrs)

        return False

    def _check_abac(self, context: ActorContext, resource_attrs: ResourceAttributes) -> bool:
        if resource_attrs.organization_id is not None and not context.belongs_to_org(resource_attrs.organization_id):
            return False
        if resource_attrs.owner_team_id is not None and not context.belongs_to_team(resource_attrs.owner_team_id):
            return False
        if resource_attrs.owner_subject is not None and context.subject != resource_attrs.owner_subject:
            return False
        return resource_attrs.environment != "live"

    def add_global_role(self, role: str, permissions: frozenset[str]) -> None:
        self._global_overrides[role] = permissions


_policy_engine: PolicyEngine | None = None


def get_policy_engine() -> PolicyEngine:
    global _policy_engine
    if _policy_engine is None:
        _policy_engine = PolicyEngine()
    return _policy_engine


def enforce(
    resource: str,
    action: str,
    context: ActorContext,
    resource_attrs: ResourceAttributes | None = None,
) -> bool:
    return get_policy_engine().enforce(resource, action, context, resource_attrs)


class SecurityAuditor:
    def on_auth_failure(self, token_present: bool, detail: str) -> None:
        pass

    def on_permission_denied(
        self,
        actor: ActorContext | None,
        resource: str,
        action: str,
        detail: str,
    ) -> None:
        pass


_security_auditor: SecurityAuditor | None = None


def get_security_auditor() -> SecurityAuditor:
    global _security_auditor
    if _security_auditor is None:
        _security_auditor = SecurityAuditor()
    return _security_auditor
