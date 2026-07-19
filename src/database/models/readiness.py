from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class ReadinessEvidence(Base):
    __tablename__ = "readiness_evidence"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(sa.ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    evidence_type: Mapped[str] = mapped_column(sa.String(80))
    title: Mapped[str] = mapped_column(sa.String(250))
    artifact_uri: Mapped[str] = mapped_column(sa.Text)
    content_sha256: Mapped[str] = mapped_column(sa.String(64))
    issued_by: Mapped[str] = mapped_column(sa.String(250))
    independent: Mapped[bool] = mapped_column(default=False)
    status: Mapped[str] = mapped_column(sa.String(20), default="pending")
    issued_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    verified_by: Mapped[str | None] = mapped_column(sa.String(200))
    verified_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    metadata_payload: Mapped[dict[str, object]] = mapped_column(JSONB)

    __table_args__ = (
        sa.UniqueConstraint("organization_id", "content_sha256", name="uq_readiness_evidence_org_hash"),
        sa.CheckConstraint("content_sha256 ~ '^[0-9a-f]{64}$'", name="sha256_format"),
        sa.CheckConstraint("status IN ('pending', 'verified', 'rejected', 'expired')", name="status_values"),
        sa.CheckConstraint("expires_at IS NULL OR expires_at > issued_at", name="valid_window"),
        sa.CheckConstraint(
            "status <> 'verified' OR (verified_by IS NOT NULL AND verified_at IS NOT NULL)",
            name="verification_is_attributed",
        ),
    )


class ReadinessControl(Base):
    __tablename__ = "readiness_controls"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(sa.ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    control_key: Mapped[str] = mapped_column(sa.String(100))
    version: Mapped[int]
    domain: Mapped[str] = mapped_column(sa.String(30))
    description: Mapped[str] = mapped_column(sa.Text)
    control_type: Mapped[str] = mapped_column(sa.String(20))
    owner_role: Mapped[str] = mapped_column(sa.String(100))
    frequency: Mapped[str] = mapped_column(sa.String(50))
    test_procedure: Mapped[str] = mapped_column(sa.Text)
    status: Mapped[str] = mapped_column(sa.String(20), default="draft")
    valid_from: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True))
    valid_to: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))

    __table_args__ = (
        sa.UniqueConstraint("organization_id", "control_key", "version", name="uq_readiness_controls_org_key_version"),
        sa.CheckConstraint("version > 0", name="positive_version"),
        sa.CheckConstraint(
            "domain IN ('legal', 'data', 'security', 'operations', 'model_risk', 'investments', 'compliance')",
            name="domain_values",
        ),
        sa.CheckConstraint("control_type IN ('preventive', 'detective', 'corrective')", name="control_type_values"),
        sa.CheckConstraint("status IN ('draft', 'effective', 'ineffective', 'retired')", name="status_values"),
        sa.CheckConstraint("valid_to IS NULL OR valid_to > valid_from", name="valid_window"),
    )


class ReadinessControlEvidence(Base):
    __tablename__ = "readiness_control_evidence"

    control_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("readiness_controls.id", ondelete="CASCADE"), primary_key=True
    )
    evidence_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("readiness_evidence.id", ondelete="RESTRICT"), primary_key=True
    )
    linked_by: Mapped[str] = mapped_column(sa.String(200))
    linked_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=utcnow)


class ReadinessFinding(Base):
    __tablename__ = "readiness_findings"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(sa.ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    domain: Mapped[str] = mapped_column(sa.String(30))
    finding_key: Mapped[str] = mapped_column(sa.String(120))
    severity: Mapped[str] = mapped_column(sa.String(20))
    description: Mapped[str] = mapped_column(sa.Text)
    status: Mapped[str] = mapped_column(sa.String(30), default="open")
    owner_role: Mapped[str] = mapped_column(sa.String(100))
    remediation: Mapped[str | None] = mapped_column(sa.Text)
    exception_expires_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    retest_evidence_id: Mapped[UUID | None] = mapped_column(sa.ForeignKey("readiness_evidence.id", ondelete="RESTRICT"))
    opened_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=utcnow)
    closed_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))

    __table_args__ = (
        sa.UniqueConstraint("organization_id", "finding_key", name="uq_readiness_findings_org_key"),
        sa.CheckConstraint("severity IN ('low', 'medium', 'high', 'critical')", name="severity_values"),
        sa.CheckConstraint("status IN ('open', 'remediating', 'closed', 'risk_accepted')", name="status_values"),
        sa.CheckConstraint(
            "status <> 'closed' OR (closed_at IS NOT NULL AND retest_evidence_id IS NOT NULL)",
            name="closure_requires_retest",
        ),
    )


class ReadinessDecisionPack(Base):
    __tablename__ = "readiness_decision_packs"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(sa.ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    version: Mapped[int]
    content_sha256: Mapped[str] = mapped_column(sa.String(64))
    manifest: Mapped[dict[str, object]] = mapped_column(JSONB)
    frozen_by: Mapped[str] = mapped_column(sa.String(200))
    frozen_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True))

    __table_args__ = (
        sa.UniqueConstraint("organization_id", "version", name="uq_readiness_packs_org_version"),
        sa.UniqueConstraint("organization_id", "content_sha256", name="uq_readiness_packs_org_hash"),
        sa.CheckConstraint("version > 0", name="positive_version"),
        sa.CheckConstraint("content_sha256 ~ '^[0-9a-f]{64}$'", name="sha256_format"),
        sa.CheckConstraint("expires_at > frozen_at", name="valid_window"),
    )


class ReadinessVote(Base):
    __tablename__ = "readiness_votes"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    decision_pack_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("readiness_decision_packs.id", ondelete="CASCADE"), index=True
    )
    voter_subject: Mapped[str] = mapped_column(sa.String(200))
    voter_role: Mapped[str] = mapped_column(sa.String(50))
    vote: Mapped[str] = mapped_column(sa.String(30))
    rationale: Mapped[str] = mapped_column(sa.Text)
    conflicts: Mapped[list[str]] = mapped_column(JSONB)
    signed_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True))

    __table_args__ = (
        sa.UniqueConstraint("decision_pack_id", "voter_role", name="uq_readiness_votes_pack_role"),
        sa.CheckConstraint(
            "voter_role IN ('legal', 'security', 'risk', 'compliance', 'operations', 'data', 'investments')",
            name="voter_role_values",
        ),
        sa.CheckConstraint("vote IN ('go', 'conditional_go', 'no_go')", name="vote_values"),
    )


class ReadinessDecision(Base):
    __tablename__ = "readiness_decisions"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    decision_pack_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("readiness_decision_packs.id", ondelete="RESTRICT"), unique=True
    )
    result: Mapped[str] = mapped_column(sa.String(30))
    authorized_scope: Mapped[str] = mapped_column(sa.String(50))
    blockers: Mapped[list[dict[str, object]]] = mapped_column(JSONB)
    conditions: Mapped[list[dict[str, object]]] = mapped_column(JSONB)
    dissent: Mapped[list[dict[str, object]]] = mapped_column(JSONB)
    decided_by: Mapped[str] = mapped_column(sa.String(200))
    decided_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True))

    __table_args__ = (
        sa.CheckConstraint("result IN ('go', 'conditional_go', 'no_go')", name="result_values"),
        sa.CheckConstraint(
            "authorized_scope IN ('none', 'remediation_only', 'future_live_planning')", name="authorized_scope_values"
        ),
        sa.CheckConstraint(
            "(result = 'go' AND authorized_scope = 'future_live_planning') OR "
            "(result = 'conditional_go' AND authorized_scope = 'remediation_only') OR "
            "(result = 'no_go' AND authorized_scope = 'none')",
            name="result_scope_consistency",
        ),
        sa.CheckConstraint("expires_at > decided_at", name="valid_window"),
    )
