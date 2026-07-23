import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from ._utils import utcnow
from .base import Base


class NewsSource(Base):
    __tablename__ = "news_sources"

    id = sa.Column(UUID(as_uuid=True), primary_key=True, default=sa.func.gen_random_uuid())
    name = sa.Column(sa.String(200), nullable=False)
    url_pattern = sa.Column(sa.Text)

    trust_level = sa.Column(sa.Integer, default=3)  # 1=CVM/B3/RI, 5=social media/unverified
    source_type = sa.Column(sa.String(20))

    is_active = sa.Column(sa.Boolean, default=True)
    created_at = sa.Column(sa.DateTime(timezone=True), default=utcnow)

    def __repr__(self) -> str:
        return f"NewsSource(name={self.name!r}, trust_level={self.trust_level})"


class NewsItem(Base):
    __tablename__ = "news_items"

    id = sa.Column(UUID(as_uuid=True), primary_key=True, default=sa.func.gen_random_uuid())
    source_id = sa.Column(
        UUID(as_uuid=True),
        sa.ForeignKey("news_sources.id", ondelete="CASCADE"),
        nullable=False,
    )

    title = sa.Column(sa.Text)
    body = sa.Column(sa.Text)
    url = sa.Column(sa.Text)

    published_at = sa.Column(sa.DateTime(timezone=True))
    retrieved_at = sa.Column(sa.DateTime(timezone=True), default=utcnow)

    language = sa.Column(sa.String(10))
    sentiment_score = sa.Column(sa.Float)

    raw_data = sa.Column(JSONB)
    is_processed = sa.Column(sa.Boolean, default=False)
    created_at = sa.Column(sa.DateTime(timezone=True), default=utcnow)

    def __repr__(self) -> str:
        return f"NewsItem(title={self.title!r}, published_at={self.published_at!r})"


class NewsEntityLink(Base):
    __tablename__ = "news_entity_links"

    id = sa.Column(UUID(as_uuid=True), primary_key=True, default=sa.func.gen_random_uuid())
    news_item_id = sa.Column(
        UUID(as_uuid=True),
        sa.ForeignKey("news_items.id", ondelete="CASCADE"),
        nullable=False,
    )
    issuer_id = sa.Column(
        UUID(as_uuid=True),
        sa.ForeignKey("issuers.id", ondelete="SET NULL"),
    )

    relevance_score = sa.Column(sa.Float)
    created_at = sa.Column(sa.DateTime(timezone=True), default=utcnow)

    def __repr__(self) -> str:
        return f"NewsEntityLink(relevance_score={self.relevance_score})"


class DetectedEvent(Base):
    __tablename__ = "detected_events"

    id = sa.Column(UUID(as_uuid=True), primary_key=True, default=sa.func.gen_random_uuid())
    news_item_id = sa.Column(
        UUID(as_uuid=True),
        sa.ForeignKey("news_items.id", ondelete="SET NULL"),
    )
    issuer_id = sa.Column(
        UUID(as_uuid=True),
        sa.ForeignKey("issuers.id", ondelete="SET NULL"),
    )

    event_type = sa.Column(sa.String(50))  # "earnings", "guidance", "ma", "regulation"
    description = sa.Column(sa.Text)

    materiality_score = sa.Column(sa.Float)
    direction_hint = sa.Column(sa.String(20))  # "positive", "negative", "neutral"
    time_horizon = sa.Column(sa.String(20))

    affected_metrics = sa.Column(JSONB)
    agent_run_id = sa.Column(UUID(as_uuid=True), sa.ForeignKey("agent_runs.id", ondelete="SET NULL"), nullable=True)
    created_at = sa.Column(sa.DateTime(timezone=True), default=utcnow)

    def __repr__(self) -> str:
        return f"DetectedEvent(event_type={self.event_type!r}, direction_hint={self.direction_hint!r})"


class EventImpact(Base):
    __tablename__ = "event_impacts"

    id = sa.Column(UUID(as_uuid=True), primary_key=True, default=sa.func.gen_random_uuid())
    event_id = sa.Column(
        UUID(as_uuid=True),
        sa.ForeignKey("detected_events.id", ondelete="CASCADE"),
        nullable=False,
    )
    thesis_id = sa.Column(UUID(as_uuid=True), sa.ForeignKey("investment_theses.id", ondelete="SET NULL"), nullable=True)

    impact_score = sa.Column(sa.Float)  # -1.0 a +1.0
    confidence = sa.Column(sa.Float)
    reasoning = sa.Column(sa.Text)

    thesis_effect = sa.Column(sa.String(20))  # "strengthen", "weaken", "neutral"
    created_at = sa.Column(sa.DateTime(timezone=True), default=utcnow)

    def __repr__(self) -> str:
        return f"EventImpact(impact_score={self.impact_score}, thesis_effect={self.thesis_effect!r})"


class EventDuplicate(Base):
    __tablename__ = "event_duplicates"

    id = sa.Column(UUID(as_uuid=True), primary_key=True, default=sa.func.gen_random_uuid())
    original_id = sa.Column(
        UUID(as_uuid=True),
        sa.ForeignKey("detected_events.id", ondelete="CASCADE"),
        nullable=False,
    )
    duplicate_id = sa.Column(
        UUID(as_uuid=True),
        sa.ForeignKey("detected_events.id", ondelete="CASCADE"),
        nullable=False,
    )

    similarity_method = sa.Column(sa.String(50))
    similarity_score = sa.Column(sa.Float)
    created_at = sa.Column(sa.DateTime(timezone=True), default=utcnow)

    def __repr__(self) -> str:
        return f"EventDuplicate(similarity_method={self.similarity_method!r})"
