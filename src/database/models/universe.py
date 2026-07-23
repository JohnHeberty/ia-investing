from datetime import datetime
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ._utils import utcnow
from .base import Base


class UniverseFilter(Base):
    """Filtros para universo de ações monitoradas."""

    __tablename__ = "universe_filters"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str | None] = mapped_column(sa.String(200))  # "Small Cap", "Dividend Aristocrats"

    criteria: Mapped[dict[str, object] | None] = mapped_column(
        JSONB
    )  # Critérios de filtro: min_market_cap, sectors_include...
    is_active: Mapped[bool | None] = mapped_column(sa.Boolean, default=True)

    created_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), default=utcnow)

    def __repr__(self) -> str:
        return f"UniverseFilter(name={self.name!r}, is_active={self.is_active})"


class UniverseMembership(Base):
    """Ações que pertencem a um universo filtrado."""

    __tablename__ = "universe_memberships"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    universe_filter_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("universe_filters.id", ondelete="CASCADE"),
        nullable=False,
    )
    issuer_id: Mapped[UUID | None] = mapped_column(
        sa.ForeignKey("issuers.id", ondelete="SET NULL"),
    )

    added_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))  # Quando entrou no universo
    removed_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))  # Quando saiu do universo

    def __repr__(self) -> str:
        return f"UniverseMembership(issuer_id={self.issuer_id!r}, added_at={self.added_at!r})"
