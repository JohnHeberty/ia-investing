from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class User:
    id: str
    name: str
    email: str
    roles: list[str]
    permissions: list[str]


USERS: dict[str, User] = {
    "admin": User(
        id="usr-admin-001",
        name="Carlos Almeida",
        email="carlos.almeida@investimentos.com.br",
        roles=["admin"],
        permissions=[
            "portfolio:create",
            "portfolio:read",
            "portfolio:update",
            "portfolio:delete",
            "thesis:create",
            "thesis:read",
            "thesis:update",
            "thesis:delete",
            "user:manage",
            "compliance:override",
            "reports:export",
        ],
    ),
    "analyst": User(
        id="usr-analyst-001",
        name="Marina Santos",
        email="marina.santos@investimentos.com.br",
        roles=["analyst"],
        permissions=[
            "portfolio:read",
            "thesis:create",
            "thesis:read",
            "thesis:update",
            "reports:export",
        ],
    ),
    "portfolio_manager": User(
        id="usr-pm-001",
        name="Roberto Oliveira",
        email="roberto.oliveira@investimentos.com.br",
        roles=["portfolio_manager"],
        permissions=[
            "portfolio:create",
            "portfolio:read",
            "portfolio:update",
            "thesis:read",
            "thesis:approve",
            "reports:export",
            "rebalance:execute",
        ],
    ),
    "compliance_officer": User(
        id="usr-compliance-001",
        name="Ana Pereira",
        email="ana.pereira@investimentos.com.br",
        roles=["compliance_officer"],
        permissions=[
            "portfolio:read",
            "thesis:read",
            "compliance:audit",
            "compliance:override",
            "reports:export",
            "reports:audit_trail",
        ],
    ),
}


def get_user_by_role(role: str) -> User | None:
    return USERS.get(role)
