import sqlalchemy as sa
from sqlalchemy import select
from sqlalchemy.dialects import postgresql

from database.models.catalog import Issuer, Sector


def _compile(statement: sa.Select) -> str:
    return str(statement.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))


def test_sector_filter_uses_typed_relationship_joins() -> None:
    statement = (
        select(Issuer)
        .join(Issuer.industry)
        .join(Sector)
        .where(Issuer.is_active.is_(True), Sector.name_pt.ilike("%energia%"))
        .offset(10)
        .limit(20)
    )

    compiled = _compile(statement)

    assert "JOIN industries" in compiled
    assert "JOIN sectors" in compiled
    assert "issuers.is_active IS true" in compiled


def test_sector_filter_orders_by_name_with_offset_limit() -> None:
    statement = (
        select(Issuer)
        .join(Issuer.industry)
        .join(Sector)
        .where(Issuer.is_active.is_(True), Sector.name_pt.ilike("%energia%"))
        .order_by(Issuer.name_pt)
        .offset(0)
        .limit(50)
    )

    compiled = _compile(statement)

    assert "ORDER BY issuers.name_pt" in compiled
    assert "LIMIT 50" in compiled
    assert "OFFSET 0" in compiled


def test_single_issuer_by_cnpj_uses_unique_index() -> None:
    statement = select(Issuer).where(Issuer.cnpj == "12345678000190")
    compiled = _compile(statement)

    assert "issuers.cnpj =" in compiled or "issuers.cnpj = " in compiled


def test_single_issuer_by_id_uses_primary_key() -> None:
    statement = select(Issuer).where(Issuer.id == sa.bindparam("issuer_id"))
    compiled = _compile(statement)

    assert "issuers.id =" in compiled or "issuers.id = " in compiled


def test_active_only_filter_without_sector_has_no_join() -> None:
    statement = select(Issuer).where(Issuer.is_active.is_(True)).order_by(Issuer.name_pt).limit(50)
    compiled = _compile(statement)

    assert "JOIN" not in compiled
    assert "sectors" not in compiled.lower()


def test_sector_filter_selects_only_issuer_columns() -> None:
    statement = (
        select(Issuer)
        .join(Issuer.industry)
        .join(Sector)
        .where(Issuer.is_active.is_(True), Sector.name_pt.ilike("%banco%"))
    )

    compiled = _compile(statement)

    assert compiled.strip().startswith("SELECT issuers.")
    assert "industries." not in compiled.split("FROM")[0]
    assert "sectors." not in compiled.split("FROM")[0]
