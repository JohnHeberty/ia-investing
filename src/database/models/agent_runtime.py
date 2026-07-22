from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class AgentCapability(Base):
    __tablename__ = "agent_capabilities"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    logical_id: Mapped[str] = mapped_column(sa.String(100), unique=True)
    display_name: Mapped[str] = mapped_column(sa.String(200))
    description: Mapped[str] = mapped_column(sa.Text)
    active_version_id: Mapped[UUID | None] = mapped_column(index=True)
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=utcnow)


class AgentArtifact(Base):
    __tablename__ = "agent_artifacts"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    logical_id: Mapped[str] = mapped_column(sa.String(150))
    kind: Mapped[str] = mapped_column(sa.String(30))
    version: Mapped[int] = mapped_column()
    sha256: Mapped[str] = mapped_column(sa.String(64))
    content: Mapped[dict[str, object]] = mapped_column(JSONB)
    source_path: Mapped[str | None] = mapped_column(sa.String(500))
    created_by: Mapped[str] = mapped_column(sa.String(255))
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=utcnow)

    __table_args__ = (
        sa.UniqueConstraint("logical_id", "kind", "version", name="uq_agent_artifacts_logical_kind_version"),
        sa.UniqueConstraint("logical_id", "kind", "sha256", name="uq_agent_artifacts_logical_kind_hash"),
        sa.CheckConstraint("kind IN ('prompt', 'schema', 'model_profile', 'toolset')", name="kind_values"),
        sa.CheckConstraint("sha256 ~ '^[0-9a-f]{64}$'", name="sha256_format"),
        sa.CheckConstraint("version > 0", name="positive_version"),
    )


class AgentVersion(Base):
    __tablename__ = "agent_versions"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    capability_id: Mapped[UUID] = mapped_column(sa.ForeignKey("agent_capabilities.id", ondelete="CASCADE"), index=True)
    version: Mapped[int] = mapped_column()
    prompt_artifact_id: Mapped[UUID] = mapped_column(sa.ForeignKey("agent_artifacts.id", ondelete="RESTRICT"))
    schema_artifact_id: Mapped[UUID] = mapped_column(sa.ForeignKey("agent_artifacts.id", ondelete="RESTRICT"))
    model_artifact_id: Mapped[UUID] = mapped_column(sa.ForeignKey("agent_artifacts.id", ondelete="RESTRICT"))
    toolset_artifact_id: Mapped[UUID] = mapped_column(sa.ForeignKey("agent_artifacts.id", ondelete="RESTRICT"))
    budgets: Mapped[dict[str, object]] = mapped_column(JSONB)
    policies: Mapped[dict[str, object]] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(sa.String(20), default="draft")
    created_by: Mapped[str] = mapped_column(sa.String(255))
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=utcnow)

    __table_args__ = (
        sa.UniqueConstraint("capability_id", "version", name="uq_agent_versions_capability_version"),
        sa.CheckConstraint("version > 0", name="positive_version"),
        sa.CheckConstraint("status IN ('draft', 'candidate', 'active', 'retired')", name="status_values"),
    )


class AgentRuntimeRun(Base):
    __tablename__ = "agent_runtime_runs"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(sa.ForeignKey("organizations.id", ondelete="RESTRICT"), index=True)
    capability_id: Mapped[UUID] = mapped_column(sa.ForeignKey("agent_capabilities.id", ondelete="RESTRICT"))
    agent_version_id: Mapped[UUID] = mapped_column(sa.ForeignKey("agent_versions.id", ondelete="RESTRICT"))
    case_id: Mapped[UUID | None] = mapped_column(sa.ForeignKey("research_cases.id", ondelete="RESTRICT"), index=True)
    workflow_id: Mapped[str | None] = mapped_column(sa.String(255), index=True)
    trace_id: Mapped[str] = mapped_column(sa.String(64), index=True)
    idempotency_key: Mapped[str | None] = mapped_column(sa.String(255))
    input_sha256: Mapped[str] = mapped_column(sa.String(64))
    input_payload: Mapped[dict[str, object]] = mapped_column(JSONB)
    output_payload: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    data_as_of: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True))
    knowledge_cutoff: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True))
    status: Mapped[str] = mapped_column(sa.String(30), default="queued", index=True)
    provider_run_id: Mapped[str | None] = mapped_column(sa.String(255))
    prompt_tokens: Mapped[int] = mapped_column(default=0)
    completion_tokens: Mapped[int] = mapped_column(default=0)
    cost_usd: Mapped[Decimal] = mapped_column(sa.Numeric(16, 8), default=0)
    duration_ms: Mapped[int | None] = mapped_column()
    evidence_coverage: Mapped[Decimal | None] = mapped_column(sa.Numeric(5, 4))
    error_code: Mapped[str | None] = mapped_column(sa.String(100))
    error_detail: Mapped[str | None] = mapped_column(sa.Text)
    started_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=utcnow)

    __table_args__ = (
        sa.UniqueConstraint("capability_id", "idempotency_key", name="uq_agent_runtime_runs_capability_idempotency"),
        sa.CheckConstraint("input_sha256 ~ '^[0-9a-f]{64}$'", name="sha256_format"),
        sa.CheckConstraint("knowledge_cutoff <= data_as_of", name="valid_temporal_cutoff"),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'awaiting_approval', 'succeeded', 'failed', 'cancelled', 'expired')",
            name="status_values",
        ),
        sa.CheckConstraint("prompt_tokens >= 0 AND completion_tokens >= 0 AND cost_usd >= 0", name="nonnegative_usage"),
        sa.CheckConstraint("evidence_coverage IS NULL OR evidence_coverage BETWEEN 0 AND 1", name="coverage_range"),
    )


class AgentRuntimeToolCall(Base):
    __tablename__ = "agent_runtime_tool_calls"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    run_id: Mapped[UUID] = mapped_column(sa.ForeignKey("agent_runtime_runs.id", ondelete="CASCADE"), index=True)
    tool_name: Mapped[str] = mapped_column(sa.String(100))
    tool_version: Mapped[int] = mapped_column()
    arguments_sha256: Mapped[str] = mapped_column(sa.String(64))
    sanitized_arguments: Mapped[dict[str, object]] = mapped_column(JSONB)
    result_payload: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(sa.String(20))
    duration_ms: Mapped[int | None] = mapped_column()
    cost_usd: Mapped[Decimal] = mapped_column(sa.Numeric(16, 8), default=0)
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=utcnow)

    __table_args__ = (
        sa.CheckConstraint("arguments_sha256 ~ '^[0-9a-f]{64}$'", name="sha256_format"),
        sa.CheckConstraint(
            "status IN ('requested', 'approved', 'succeeded', 'failed', 'blocked')", name="status_values"
        ),
    )


class AgentApprovalRequest(Base):
    __tablename__ = "agent_approval_requests"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    run_id: Mapped[UUID] = mapped_column(sa.ForeignKey("agent_runtime_runs.id", ondelete="CASCADE"), index=True)
    tool_call_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("agent_runtime_tool_calls.id", ondelete="CASCADE"), unique=True
    )
    scope: Mapped[str] = mapped_column(sa.String(100))
    impact: Mapped[dict[str, object]] = mapped_column(JSONB)
    requested_by: Mapped[str] = mapped_column(sa.String(255))
    requested_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True))
    status: Mapped[str] = mapped_column(sa.String(20), default="pending")
    decided_by: Mapped[str | None] = mapped_column(sa.String(255))
    decision_reason: Mapped[str | None] = mapped_column(sa.Text)
    decided_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))

    __table_args__ = (
        sa.CheckConstraint("expires_at > requested_at", name="valid_expiry"),
        sa.CheckConstraint(
            "status IN ('pending', 'approved', 'rejected', 'expired', 'cancelled')", name="status_values"
        ),
    )


class AgentEvalDataset(Base):
    __tablename__ = "agent_eval_datasets"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    logical_id: Mapped[str] = mapped_column(sa.String(150))
    capability_id: Mapped[UUID] = mapped_column(sa.ForeignKey("agent_capabilities.id", ondelete="CASCADE"))
    version: Mapped[int] = mapped_column()
    sha256: Mapped[str] = mapped_column(sa.String(64))
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=utcnow)

    __table_args__ = (
        sa.UniqueConstraint("logical_id", "version", name="uq_agent_eval_datasets_logical_version"),
        sa.CheckConstraint("sha256 ~ '^[0-9a-f]{64}$'", name="sha256_format"),
    )


class AgentEvalCase(Base):
    __tablename__ = "agent_eval_cases"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    dataset_id: Mapped[UUID] = mapped_column(sa.ForeignKey("agent_eval_datasets.id", ondelete="CASCADE"), index=True)
    case_key: Mapped[str] = mapped_column(sa.String(150))
    input_payload: Mapped[dict[str, object]] = mapped_column(JSONB)
    expected_payload: Mapped[dict[str, object]] = mapped_column(JSONB)
    tags: Mapped[list[str]] = mapped_column(JSONB)

    __table_args__ = (sa.UniqueConstraint("dataset_id", "case_key", name="uq_agent_eval_cases_dataset_key"),)


class AgentEvalRun(Base):
    __tablename__ = "agent_eval_runs"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    dataset_id: Mapped[UUID] = mapped_column(sa.ForeignKey("agent_eval_datasets.id", ondelete="RESTRICT"))
    baseline_version_id: Mapped[UUID] = mapped_column(sa.ForeignKey("agent_versions.id", ondelete="RESTRICT"))
    candidate_version_id: Mapped[UUID] = mapped_column(sa.ForeignKey("agent_versions.id", ondelete="RESTRICT"))
    metrics: Mapped[dict[str, object]] = mapped_column(JSONB)
    thresholds: Mapped[dict[str, object]] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(sa.String(20))
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=utcnow)

    __table_args__ = (sa.CheckConstraint("status IN ('running', 'passed', 'failed')", name="status_values"),)


class AgentPromotion(Base):
    __tablename__ = "agent_promotions"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    capability_id: Mapped[UUID] = mapped_column(sa.ForeignKey("agent_capabilities.id", ondelete="CASCADE"), index=True)
    from_version_id: Mapped[UUID | None] = mapped_column(sa.ForeignKey("agent_versions.id", ondelete="RESTRICT"))
    to_version_id: Mapped[UUID] = mapped_column(sa.ForeignKey("agent_versions.id", ondelete="RESTRICT"))
    eval_run_id: Mapped[UUID] = mapped_column(sa.ForeignKey("agent_eval_runs.id", ondelete="RESTRICT"))
    override_reason: Mapped[str | None] = mapped_column(sa.Text)
    override_expires_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    promoted_by: Mapped[str] = mapped_column(sa.String(255))
    promoted_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=utcnow)
