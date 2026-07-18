from datetime import UTC, datetime

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from .base import Base


class UniverseFilter(Base):
    """Filtros para universo de ações monitoradas."""

    __tablename__ = "universe_filters"

    id = sa.Column(UUID(as_uuid=True), primary_key=True, default=sa.func.gen_random_uuid())
    name = sa.Column(sa.String(200))  # "Small Cap", "Dividend Aristocrats"

    criteria = JSONB()  # Critérios de filtro: min_market_cap, sectors_include...
    is_active = sa.Column(sa.Boolean, default=True)

    created_at = sa.Column(sa.DateTime(timezone=True), default=lambda: datetime.now(UTC))

    def __repr__(self) -> str:
        return f"UniverseFilter(name={self.name!r}, is_active={self.is_active})"


class UniverseMembership(Base):
    """Ações que pertencem a um universo filtrado."""

    __tablename__ = "universe_memberships"

    id = sa.Column(UUID(as_uuid=True), primary_key=True, default=sa.func.gen_random_uuid())
    universe_filter_id = sa.Column(
        UUID(as_uuid=True), sa.ForeignKey("universe_filters.id", ondelete="CASCADE"),
        nullable=False,
    )
    issuer_id = sa.Column(
        UUID(as_uuid=True), sa.ForeignKey("issuers.id", ondelete="SET NULL"),
    )

    added_at = sa.Column(sa.DateTime(timezone=True))  # Quando entrou no universo
    removed_at = sa.Column(sa.DateTime(timezone=True))  # Quando saiu do universo

    def __repr__(self) -> str:
        return f"UniverseMembership(issuer_id={self.issuer_id!r}, added_at={self.added_at!r})"
