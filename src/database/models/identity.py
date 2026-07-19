from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    slug: Mapped[str] = mapped_column(sa.String(100), unique=True)
    display_name: Mapped[str] = mapped_column(sa.String(200))
    status: Mapped[str] = mapped_column(sa.String(20), default="active")
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=utcnow)


class UserIdentity(Base):
    __tablename__ = "user_identities"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    oidc_issuer: Mapped[str] = mapped_column(sa.String(500))
    oidc_subject: Mapped[str] = mapped_column(sa.String(255))
    email: Mapped[str | None] = mapped_column(sa.String(320))
    display_name: Mapped[str | None] = mapped_column(sa.String(200))
    status: Mapped[str] = mapped_column(sa.String(20), default="active")
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=utcnow)

    __table_args__ = (sa.UniqueConstraint("oidc_issuer", "oidc_subject", name="uq_user_identities_issuer_subject"),)


class Team(Base):
    __tablename__ = "teams"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(sa.ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    slug: Mapped[str] = mapped_column(sa.String(100))
    display_name: Mapped[str] = mapped_column(sa.String(200))

    __table_args__ = (sa.UniqueConstraint("organization_id", "slug", name="uq_teams_organization_slug"),)


class OrganizationMembership(Base):
    __tablename__ = "organization_memberships"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(sa.ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[UUID] = mapped_column(sa.ForeignKey("user_identities.id", ondelete="CASCADE"), index=True)
    attributes: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    status: Mapped[str] = mapped_column(sa.String(20), default="active")

    __table_args__ = (sa.UniqueConstraint("organization_id", "user_id", name="uq_organization_memberships_org_user"),)


class TeamMembership(Base):
    __tablename__ = "team_memberships"

    team_id: Mapped[UUID] = mapped_column(sa.ForeignKey("teams.id", ondelete="CASCADE"), primary_key=True)
    organization_membership_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("organization_memberships.id", ondelete="CASCADE"), primary_key=True
    )


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID | None] = mapped_column(sa.ForeignKey("organizations.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(sa.String(100))
    description: Mapped[str] = mapped_column(sa.Text)

    __table_args__ = (sa.UniqueConstraint("organization_id", "name", name="uq_roles_organization_name"),)


class Permission(Base):
    __tablename__ = "permissions"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(sa.String(150), unique=True)
    description: Mapped[str] = mapped_column(sa.Text)


class RolePermission(Base):
    __tablename__ = "role_permissions"

    role_id: Mapped[UUID] = mapped_column(sa.ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True)
    permission_id: Mapped[UUID] = mapped_column(sa.ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True)


class MembershipRole(Base):
    __tablename__ = "membership_roles"

    membership_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("organization_memberships.id", ondelete="CASCADE"), primary_key=True
    )
    role_id: Mapped[UUID] = mapped_column(sa.ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True)


class ServiceIdentity(Base):
    __tablename__ = "service_identities"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(sa.ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    logical_id: Mapped[str] = mapped_column(sa.String(150))
    identity_type: Mapped[str] = mapped_column(sa.String(30))
    capability: Mapped[str] = mapped_column(sa.String(100))
    attributes: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    active: Mapped[bool] = mapped_column(default=True)

    __table_args__ = (
        sa.UniqueConstraint("organization_id", "logical_id", name="uq_service_identities_organization_logical"),
        sa.CheckConstraint("identity_type IN ('agent', 'worker', 'service')", name="identity_type_values"),
    )
