from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ._utils import utcnow
from .base import Base


class MacroSeriesDefinition(Base):
    __tablename__ = "macro_series_definitions"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    source_id: Mapped[UUID] = mapped_column(sa.ForeignKey("data_sources.id", ondelete="RESTRICT"))
    series_code: Mapped[str] = mapped_column(sa.String(100))
    version: Mapped[int] = mapped_column()
    name: Mapped[str] = mapped_column(sa.String(200))
    unit: Mapped[str] = mapped_column(sa.String(50))
    frequency: Mapped[str] = mapped_column(sa.String(30))
    revision_policy: Mapped[str] = mapped_column(sa.String(100))
    transformation: Mapped[dict[str, object]] = mapped_column(JSONB)
    content_sha256: Mapped[str] = mapped_column(sa.String(64))
    valid_from: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True))
    valid_to: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))

    __table_args__ = (
        sa.UniqueConstraint(
            "source_id", "series_code", "version", name="uq_macro_series_definitions_source_code_version"
        ),
        sa.CheckConstraint("version > 0", name="positive_version"),
        sa.CheckConstraint("content_sha256 ~ '^[0-9a-f]{64}$'", name="sha256_format"),
        sa.CheckConstraint("valid_to IS NULL OR valid_to > valid_from", name="valid_window"),
    )


class MacroObservationRevision(Base):
    __tablename__ = "macro_observation_revisions"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    series_definition_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("macro_series_definitions.id", ondelete="RESTRICT"), index=True
    )
    effective_date: Mapped[date]
    revision: Mapped[int] = mapped_column()
    value: Mapped[Decimal | None] = mapped_column(sa.Numeric(28, 10))
    value_status: Mapped[str] = mapped_column(sa.String(30))
    published_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True))
    knowledge_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), index=True)
    source_object_version_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("source_object_versions.id", ondelete="RESTRICT")
    )

    __table_args__ = (
        sa.UniqueConstraint(
            "series_definition_id", "effective_date", "revision", name="uq_macro_observations_series_date_revision"
        ),
        sa.CheckConstraint("revision > 0", name="positive_revision"),
        sa.CheckConstraint(
            "value_status IN ('reported', 'missing', 'suppressed', 'parse_error')", name="value_status_values"
        ),
        sa.CheckConstraint("(value_status = 'reported') = (value IS NOT NULL)", name="value_matches_status"),
    )


class PolicyObject(Base):
    __tablename__ = "policy_objects"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    jurisdiction: Mapped[str] = mapped_column(sa.String(20), default="BR")
    authority: Mapped[str] = mapped_column(sa.String(100))
    object_type: Mapped[str] = mapped_column(sa.String(50))
    external_id: Mapped[str] = mapped_column(sa.String(150))
    canonical_key: Mapped[str] = mapped_column(sa.String(300), unique=True)
    title: Mapped[str] = mapped_column(sa.Text)
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=utcnow)


class PolicyObjectVersion(Base):
    __tablename__ = "policy_object_versions"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    policy_object_id: Mapped[UUID] = mapped_column(sa.ForeignKey("policy_objects.id", ondelete="CASCADE"), index=True)
    version: Mapped[int] = mapped_column()
    text_sha256: Mapped[str] = mapped_column(sa.String(64))
    metadata_sha256: Mapped[str] = mapped_column(sa.String(64))
    text_content: Mapped[str] = mapped_column(sa.Text)
    metadata_payload: Mapped[dict[str, object]] = mapped_column(JSONB)
    diff_from_previous: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    published_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True))
    knowledge_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), index=True)
    source_object_version_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("source_object_versions.id", ondelete="RESTRICT")
    )

    __table_args__ = (
        sa.UniqueConstraint("policy_object_id", "version", name="uq_policy_object_versions_object_version"),
        sa.UniqueConstraint(
            "policy_object_id", "text_sha256", "metadata_sha256", name="uq_policy_object_versions_content"
        ),
        sa.CheckConstraint("text_sha256 ~ '^[0-9a-f]{64}$' AND metadata_sha256 ~ '^[0-9a-f]{64}$'", name="hash_format"),
    )


class PolicyStageEvent(Base):
    __tablename__ = "policy_stage_events"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    policy_object_id: Mapped[UUID] = mapped_column(sa.ForeignKey("policy_objects.id", ondelete="CASCADE"), index=True)
    stage: Mapped[str] = mapped_column(sa.String(80))
    occurred_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True))
    knowledge_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), index=True)
    evidence_id: Mapped[UUID] = mapped_column(sa.ForeignKey("research_evidence.id", ondelete="RESTRICT"))
    metadata_payload: Mapped[dict[str, object]] = mapped_column(JSONB)

    __table_args__ = (
        sa.UniqueConstraint(
            "policy_object_id", "stage", "occurred_at", "knowledge_at", name="uq_policy_stage_events_pit"
        ),
    )


class PolicyActor(Base):
    __tablename__ = "policy_actors"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    authority: Mapped[str] = mapped_column(sa.String(100))
    external_id: Mapped[str] = mapped_column(sa.String(150))
    display_name: Mapped[str] = mapped_column(sa.String(250))
    actor_type: Mapped[str] = mapped_column(sa.String(50))

    __table_args__ = (sa.UniqueConstraint("authority", "external_id", name="uq_policy_actors_authority_external"),)


class PolicyVote(Base):
    __tablename__ = "policy_votes"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    policy_object_id: Mapped[UUID] = mapped_column(sa.ForeignKey("policy_objects.id", ondelete="CASCADE"), index=True)
    actor_id: Mapped[UUID] = mapped_column(sa.ForeignKey("policy_actors.id", ondelete="RESTRICT"))
    vote_session_key: Mapped[str] = mapped_column(sa.String(150))
    position: Mapped[str] = mapped_column(sa.String(30))
    voted_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True))
    knowledge_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True))
    evidence_id: Mapped[UUID] = mapped_column(sa.ForeignKey("research_evidence.id", ondelete="RESTRICT"))

    __table_args__ = (sa.UniqueConstraint("vote_session_key", "actor_id", name="uq_policy_votes_session_actor"),)


class PolicyCorroboration(Base):
    __tablename__ = "policy_corroborations"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    policy_object_id: Mapped[UUID] = mapped_column(sa.ForeignKey("policy_objects.id", ondelete="CASCADE"), index=True)
    assertion_sha256: Mapped[str] = mapped_column(sa.String(64))
    evidence_id: Mapped[UUID] = mapped_column(sa.ForeignKey("research_evidence.id", ondelete="RESTRICT"))
    stance: Mapped[str] = mapped_column(sa.String(20))
    confidence: Mapped[Decimal] = mapped_column(sa.Numeric(5, 4))
    knowledge_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True))

    __table_args__ = (
        sa.UniqueConstraint(
            "policy_object_id", "assertion_sha256", "evidence_id", name="uq_policy_corroborations_assertion_evidence"
        ),
        sa.CheckConstraint("assertion_sha256 ~ '^[0-9a-f]{64}$'", name="sha256_format"),
        sa.CheckConstraint("stance IN ('supports', 'contradicts', 'neutral')", name="stance_values"),
        sa.CheckConstraint("confidence BETWEEN 0 AND 1", name="confidence_range"),
    )


class PolicyProbabilityForecast(Base):
    __tablename__ = "policy_probability_forecasts"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    policy_object_id: Mapped[UUID] = mapped_column(sa.ForeignKey("policy_objects.id", ondelete="CASCADE"), index=True)
    target_outcome: Mapped[str] = mapped_column(sa.String(100))
    methodology_version: Mapped[str] = mapped_column(sa.String(100))
    features_sha256: Mapped[str] = mapped_column(sa.String(64))
    probability: Mapped[Decimal] = mapped_column(sa.Numeric(5, 4))
    interval_low: Mapped[Decimal] = mapped_column(sa.Numeric(5, 4))
    interval_high: Mapped[Decimal] = mapped_column(sa.Numeric(5, 4))
    assumptions: Mapped[list[str]] = mapped_column(JSONB)
    factors: Mapped[dict[str, object]] = mapped_column(JSONB)
    predicted_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True))
    knowledge_cutoff: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True))
    outcome: Mapped[bool | None]
    outcome_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))

    __table_args__ = (
        sa.UniqueConstraint(
            "policy_object_id",
            "target_outcome",
            "methodology_version",
            "predicted_at",
            name="uq_policy_forecasts_target_time",
        ),
        sa.CheckConstraint("features_sha256 ~ '^[0-9a-f]{64}$'", name="sha256_format"),
        sa.CheckConstraint(
            "0 <= interval_low AND interval_low <= probability AND probability <= interval_high AND interval_high <= 1",
            name="valid_interval",
        ),
        sa.CheckConstraint("outcome_at IS NULL OR outcome IS NOT NULL", name="outcome_consistency"),
    )


class RegulatoryAction(Base):
    __tablename__ = "regulatory_actions"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    policy_object_id: Mapped[UUID] = mapped_column(sa.ForeignKey("policy_objects.id", ondelete="CASCADE"), index=True)
    authority: Mapped[str] = mapped_column(sa.String(100))
    action_type: Mapped[str] = mapped_column(sa.String(50))
    external_id: Mapped[str] = mapped_column(sa.String(150))
    title: Mapped[str] = mapped_column(sa.Text)
    description: Mapped[str] = mapped_column(sa.Text, default="")
    issued_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True))
    effective_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    parent_action_id: Mapped[UUID | None] = mapped_column(sa.ForeignKey("regulatory_actions.id", ondelete="SET NULL"))
    rectifies: Mapped[bool] = mapped_column(sa.Boolean, default=False)
    content_sha256: Mapped[str] = mapped_column(sa.String(64))
    metadata_payload: Mapped[dict[str, object]] = mapped_column(JSONB)
    knowledge_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), index=True)
    source_object_version_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("source_object_versions.id", ondelete="RESTRICT")
    )
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=utcnow)

    __table_args__ = (
        sa.UniqueConstraint("authority", "external_id", name="uq_regulatory_actions_authority_external"),
        sa.CheckConstraint("content_sha256 ~ '^[0-9a-f]{64}$'", name="sha256_format"),
        sa.CheckConstraint(
            "action_type IN ('normative', 'circular', 'resolution', 'instruction', 'edict', 'decree', 'law', 'other')",
            name="action_type_values",
        ),
        sa.CheckConstraint("parent_action_id IS NULL OR parent_action_id <> id", name="no_self_reference"),
    )


class PolicyGraphNode(Base):
    __tablename__ = "policy_graph_nodes"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID | None] = mapped_column(
        sa.ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    node_type: Mapped[str] = mapped_column(sa.String(30))
    reference_id: Mapped[UUID | None]
    logical_key: Mapped[str] = mapped_column(sa.String(250))
    label: Mapped[str] = mapped_column(sa.String(250))

    __table_args__ = (
        sa.UniqueConstraint("organization_id", "node_type", "logical_key", name="uq_policy_graph_nodes_scope_type_key"),
    )


class PolicyGraphEdge(Base):
    __tablename__ = "policy_graph_edges"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    from_node_id: Mapped[UUID] = mapped_column(sa.ForeignKey("policy_graph_nodes.id", ondelete="CASCADE"), index=True)
    to_node_id: Mapped[UUID] = mapped_column(sa.ForeignKey("policy_graph_nodes.id", ondelete="CASCADE"), index=True)
    relationship: Mapped[str] = mapped_column(sa.String(50))
    version: Mapped[int] = mapped_column()
    method: Mapped[str] = mapped_column(sa.String(100))
    evidence_id: Mapped[UUID] = mapped_column(sa.ForeignKey("research_evidence.id", ondelete="RESTRICT"))
    confidence: Mapped[Decimal] = mapped_column(sa.Numeric(5, 4))
    weight: Mapped[Decimal] = mapped_column(sa.Numeric(12, 8))
    status: Mapped[str] = mapped_column(sa.String(20), default="draft")
    valid_from: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True))
    valid_to: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))

    __table_args__ = (
        sa.UniqueConstraint(
            "from_node_id", "to_node_id", "relationship", "version", name="uq_policy_graph_edges_version"
        ),
        sa.CheckConstraint("from_node_id <> to_node_id", name="no_self_loop"),
        sa.CheckConstraint("version > 0", name="positive_version"),
        sa.CheckConstraint("confidence BETWEEN 0 AND 1", name="confidence_range"),
        sa.CheckConstraint("status IN ('draft', 'approved', 'retired')", name="status_values"),
        sa.CheckConstraint("valid_to IS NULL OR valid_to > valid_from", name="valid_window"),
    )
