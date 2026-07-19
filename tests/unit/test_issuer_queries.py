from sqlalchemy import select
from sqlalchemy.dialects import postgresql

from database.models.catalog import Issuer, Sector


def test_sector_filter_uses_typed_relationship_joins() -> None:
    statement = (
        select(Issuer)
        .join(Issuer.industry)
        .join(Sector)
        .where(Issuer.is_active.is_(True), Sector.name_pt.ilike("%energia%"))
        .offset(10)
        .limit(20)
    )

    compiled = str(statement.compile(dialect=postgresql.dialect()))

    assert "JOIN industries" in compiled
    assert "JOIN sectors" in compiled
    assert "issuers.is_active IS true" in compiled
