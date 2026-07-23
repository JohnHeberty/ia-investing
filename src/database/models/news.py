from datetime import datetime
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ._utils import utcnow
from .base import Base


class NewsSource(Base):
    __tablename__ = "news_sources"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(sa.String(200), nullable=False)
    url_pattern: Mapped[str | None] = mapped_column(sa.Text)

    trust_level: Mapped[int | None] = mapped_column(sa.Integer, default=3)  # 1=CVM/B3/RI, 5=social media/unverified
    source_type: Mapped[str | None] = mapped_column(sa.String(20))

    is_active: Mapped[bool | None] = mapped_column(sa.Boolean, default=True)
    created_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), default=utcnow)

    def __repr__(self) -> str:
        return f"NewsSource(name={self.name!r}, trust_level={self.trust_level})"


class NewsItem(Base):
    __tablename__ = "news_items"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    source_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("news_sources.id", ondelete="CASCADE"),
        nullable=False,
    )

    title: Mapped[str | None] = mapped_column(sa.Text)
    body: Mapped[str | None] = mapped_column(sa.Text)
    url: Mapped[str | None] = mapped_column(sa.Text)

    published_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    retrieved_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), default=utcnow)

    language: Mapped[str | None] = mapped_column(sa.String(10))
    sentiment_score: Mapped[float | None] = mapped_column(sa.Float)

    raw_data: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    is_processed: Mapped[bool | None] = mapped_column(sa.Boolean, default=False)
    created_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), default=utcnow)

    def __repr__(self) -> str:
        return f"NewsItem(title={self.title!r}, published_at={self.published_at!r})"


class NewsEntityLink(Base):
    __tablename__ = "news_entity_links"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    news_item_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("news_items.id", ondelete="CASCADE"),
        nullable=False,
    )
    issuer_id: Mapped[UUID | None] = mapped_column(
        sa.ForeignKey("issuers.id", ondelete="SET NULL"),
    )

    relevance_score: Mapped[float | None] = mapped_column(sa.Float)
    created_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), default=utcnow)

    def __repr__(self) -> str:
        return f"NewsEntityLink(relevance_score={self.relevance_score})"


class DetectedEvent(Base):
    __tablename__ = "detected_events"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    news_item_id: Mapped[UUID | None] = mapped_column(
        sa.ForeignKey("news_items.id", ondelete="SET NULL"),
    )
    issuer_id: Mapped[UUID | None] = mapped_column(
        sa.ForeignKey("issuers.id", ondelete="SET NULL"),
    )

    event_type: Mapped[str | None] = mapped_column(sa.String(50))  # "earnings", "guidance", "ma", "regulation"
    description: Mapped[str | None] = mapped_column(sa.Text)

    materiality_score: Mapped[float | None] = mapped_column(sa.Float)
    direction_hint: Mapped[str | None] = mapped_column(sa.String(20))  # "positive", "negative", "neutral"
    time_horizon: Mapped[str | None] = mapped_column(sa.String(20))

    affected_metrics: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    agent_run_id: Mapped[UUID | None] = mapped_column(sa.ForeignKey("agent_runs.id", ondelete="SET NULL"))
    created_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), default=utcnow)

    def __repr__(self) -> str:
        return f"DetectedEvent(event_type={self.event_type!r}, direction_hint={self.direction_hint!r})"


class EventImpact(Base):
    __tablename__ = "event_impacts"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    event_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("detected_events.id", ondelete="CASCADE"),
        nullable=False,
    )
    thesis_id: Mapped[UUID | None] = mapped_column(sa.ForeignKey("investment_theses.id", ondelete="SET NULL"))

    impact_score: Mapped[float | None] = mapped_column(sa.Float)  # -1.0 a +1.0
    confidence: Mapped[float | None] = mapped_column(sa.Float)
    reasoning: Mapped[str | None] = mapped_column(sa.Text)

    thesis_effect: Mapped[str | None] = mapped_column(sa.String(20))  # "strengthen", "weaken", "neutral"
    created_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), default=utcnow)

    def __repr__(self) -> str:
        return f"EventImpact(impact_score={self.impact_score}, thesis_effect={self.thesis_effect!r})"


class EventDuplicate(Base):
    __tablename__ = "event_duplicates"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    original_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("detected_events.id", ondelete="CASCADE"),
        nullable=False,
    )
    duplicate_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("detected_events.id", ondelete="CASCADE"),
        nullable=False,
    )

    similarity_method: Mapped[str | None] = mapped_column(sa.String(50))
    similarity_score: Mapped[float | None] = mapped_column(sa.Float)
    created_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), default=utcnow)

    def __repr__(self) -> str:
        return f"EventDuplicate(similarity_method={self.similarity_method!r})"
