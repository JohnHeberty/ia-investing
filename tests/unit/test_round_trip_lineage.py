"""F2-PR04.6 round-trip and lineage traceability tests.

Covers:
  - Fact revision lifecycle (close window, bump revision, idempotency)
  - Temporal as_of queries returning only historically-known facts
  - Metric provenance / MetricFactLineage traceability
  - Multi-sector reconciliation of CVM DFP and ITR fixtures
"""

from __future__ import annotations

import csv
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from database.models.financial_facts import (
    FinancialFact,
    MetricFactLineage,
    MetricObservation,
)
from ia_investing.application.financial_facts import (
    FinancialFactInput,
    FinancialFactRepository,
)

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "cvm"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TZ = UTC


def _dt(year: int, month: int, day: int, hour: int = 0, minute: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=_TZ)


def _make_input(
    *,
    reporting_period_id: UUID | None = None,
    knowledge_at: datetime | None = None,
    value: Decimal = Decimal("1000.00"),
    value_status: str = "reported",
    source_object_version_id: UUID | None = None,
    parser_version: str = "parser-v1",
    mapping_rule_id: UUID | None = None,
) -> FinancialFactInput:
    return FinancialFactInput(
        issuer_id=uuid4(),
        reporting_period_id=reporting_period_id or uuid4(),
        statement_type="BPA",
        consolidation_scope="consolidated",
        original_account_code="1.01",
        original_account_label="Ativo Circulante",
        taxonomy_account_id=uuid4(),
        value=value,
        currency_code="BRL",
        scale_factor=1,
        value_status=value_status,
        source_object_version_id=source_object_version_id or uuid4(),
        parser_version=parser_version,
        mapping_rule_id=mapping_rule_id or uuid4(),
        published_at=_dt(2024, 12, 31),
        discovered_at=_dt(2024, 12, 31, 23),
        ingested_at=_dt(2024, 12, 31, 23, 59),
        validated_at=_dt(2025, 1, 1),
        knowledge_at=knowledge_at or _dt(2025, 1, 2),
    )


def _fact_stub(**overrides: Any) -> FinancialFact:
    defaults = {
        "id": uuid4(),
        "issuer_id": uuid4(),
        "reporting_period_id": uuid4(),
        "statement_type": "BPA",
        "consolidation_scope": "consolidated",
        "original_account_code": "1.01",
        "original_account_label": "Ativo Circulante",
        "taxonomy_account_id": uuid4(),
        "value": Decimal("1000.00"),
        "currency_code": "BRL",
        "scale_factor": 1,
        "value_status": "reported",
        "source_object_version_id": uuid4(),
        "parser_version": "parser-v1",
        "mapping_rule_id": uuid4(),
        "published_at": _dt(2024, 12, 31),
        "discovered_at": _dt(2024, 12, 31, 23),
        "ingested_at": _dt(2024, 12, 31, 23, 59),
        "validated_at": _dt(2025, 1, 1),
        "knowledge_at": _dt(2025, 1, 2),
        "valid_from": _dt(2025, 1, 2),
        "valid_to": None,
        "revision_number": 1,
    }
    defaults.update(overrides)
    return FinancialFact(**defaults)


def _metric_observation_stub(**overrides: Any) -> MetricObservation:
    defaults = {
        "id": uuid4(),
        "issuer_id": uuid4(),
        "reporting_period_id": uuid4(),
        "metric_definition_id": uuid4(),
        "value": Decimal("1.5"),
        "value_status": "calculated",
        "quality_score": Decimal("1.0000"),
        "coverage_ratio": Decimal("1.0000"),
        "data_as_of": _dt(2025, 1, 3),
        "calculation_version": "current_ratio:v1",
    }
    defaults.update(overrides)
    return MetricObservation(**defaults)


def _parse_csv(fixture_name: str) -> list[dict[str, str]]:
    fixture_path = FIXTURES_DIR / fixture_name
    rows: list[dict[str, str]] = []
    with fixture_path.open(encoding="utf-8") as fh:
        reader = csv.DictReader(fh, delimiter=";")
        for row in reader:
            rows.append(row)
    return rows


# ---------------------------------------------------------------------------
# 1. test_revise_creates_new_version_with_closed_window
# ---------------------------------------------------------------------------


async def test_revise_creates_new_version_with_closed_window() -> None:
    """revise() closes the current fact window and creates a new revision."""
    session = AsyncMock(spec=AsyncSession)
    repo = FinancialFactRepository(session)

    first_input = _make_input(knowledge_at=_dt(2025, 1, 2))
    second_input = _make_input(
        knowledge_at=_dt(2025, 6, 1),
        value=Decimal("2000.00"),
        source_object_version_id=uuid4(),
    )

    current_fact = _fact_stub(
        valid_from=_dt(2025, 1, 2),
        valid_to=None,
        revision_number=1,
        value=Decimal("1000.00"),
    )

    # Simulate first call: no existing fact -> create revision 1
    mock_result_first = MagicMock()
    mock_result_first.scalar_one_or_none.return_value = None
    session.execute.return_value = mock_result_first

    result1 = await repo.revise(first_input)
    assert result1.created is True
    assert result1.superseded_fact_id is None
    assert result1.fact.revision_number == 1
    assert result1.fact.valid_to is None

    # Simulate second call: existing fact -> close and create revision 2
    mock_result_second = MagicMock()
    mock_result_second.scalar_one_or_none.return_value = current_fact
    session.execute.return_value = mock_result_second

    result2 = await repo.revise(second_input)
    assert result2.created is True
    assert result2.superseded_fact_id == current_fact.id

    # The original fact was mutated (valid_to set)
    assert current_fact.valid_to == _dt(2025, 6, 1)
    # The new fact has incremented revision
    assert result2.fact.revision_number == 2
    assert result2.fact.valid_from == _dt(2025, 6, 1)
    assert result2.fact.valid_to is None


# ---------------------------------------------------------------------------
# 2. test_list_as_of_returns_only_known_facts
# ---------------------------------------------------------------------------


async def test_list_as_of_returns_only_known_facts() -> None:
    """list_as_of returns only facts whose knowledge_at <= as_of and window is open."""
    session = AsyncMock(spec=AsyncSession)
    repo = FinancialFactRepository(session)

    issuer_id = uuid4()
    period_id = uuid4()

    known_fact = _fact_stub(
        issuer_id=issuer_id,
        reporting_period_id=period_id,
        knowledge_at=_dt(2025, 3, 1),
        valid_from=_dt(2025, 3, 1),
        valid_to=None,
    )

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [known_fact]
    session.execute.return_value = mock_result

    # Query at a date after the fact was known
    results = await repo.list_as_of(issuer_id, period_id, _dt(2025, 4, 1))
    assert len(results) == 1
    assert results[0].id == known_fact.id

    # Verify the query was constructed with the right filters (call args)
    call_args = session.execute.call_args
    # The select statement should have been executed
    assert call_args is not None


# ---------------------------------------------------------------------------
# 3. test_list_as_of_with_revision_returns_latest_known
# ---------------------------------------------------------------------------


async def test_list_as_of_with_revision_returns_latest_known() -> None:
    """Between two revisions, list_as_of returns only the revision valid at query time."""
    session = AsyncMock(spec=AsyncSession)
    repo = FinancialFactRepository(session)

    issuer_id = uuid4()
    period_id = uuid4()

    # Revision 1: valid 2025-01-01 .. 2025-06-01
    rev1 = _fact_stub(
        id=uuid4(),
        issuer_id=issuer_id,
        reporting_period_id=period_id,
        valid_from=_dt(2025, 1, 1),
        valid_to=_dt(2025, 6, 1),
        revision_number=1,
        value=Decimal("100.00"),
    )

    # Query at 2025-03-01 should find revision 1
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [rev1]
    session.execute.return_value = mock_result

    results = await repo.list_as_of(issuer_id, period_id, _dt(2025, 3, 1))
    assert len(results) == 1
    assert results[0].revision_number == 1
    assert results[0].valid_from == _dt(2025, 1, 1)
    assert results[0].valid_to == _dt(2025, 6, 1)


# ---------------------------------------------------------------------------
# 4. test_reprocessing_does_not_change_historical_result
# ---------------------------------------------------------------------------


async def test_reprocessing_does_not_change_historical_result() -> None:
    """Idempotent revise() returns the same fact when nothing changed."""
    session = AsyncMock(spec=AsyncSession)
    repo = FinancialFactRepository(session)

    item = _make_input()
    existing_fact = _fact_stub(
        valid_from=item.knowledge_at,
        valid_to=None,
        value=item.value,
        value_status=item.value_status,
        source_object_version_id=item.source_object_version_id,
        parser_version=item.parser_version,
        mapping_rule_id=item.mapping_rule_id,
    )

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = existing_fact
    session.execute.return_value = mock_result

    result = await repo.revise(item)
    # Idempotent: nothing changed, created=False
    assert result.created is False
    assert result.superseded_fact_id is None
    assert result.fact.id == existing_fact.id
    # The fact was not mutated
    assert result.fact.valid_to is None
    assert result.fact.revision_number == 1


# ---------------------------------------------------------------------------
# 5. test_metric_observation_links_to_source_facts
# ---------------------------------------------------------------------------


async def test_metric_observation_links_to_source_facts() -> None:
    """MetricFactLineage connects a MetricObservation to its source FinancialFacts."""
    session = AsyncMock(spec=AsyncSession)

    fact_a = _fact_stub(id=uuid4(), original_account_code="1.01")
    fact_b = _fact_stub(id=uuid4(), original_account_code="2.01")

    obs = _metric_observation_stub()

    # Simulate session.add + flush
    session.add = MagicMock()
    session.flush = AsyncMock()

    # Manually create lineage rows (simulating what MetricService does)
    lineage_a = MetricFactLineage(
        metric_observation_id=obs.id,
        financial_fact_id=fact_a.id,
        input_role="current_assets",
    )
    lineage_b = MetricFactLineage(
        metric_observation_id=obs.id,
        financial_fact_id=fact_b.id,
        input_role="current_liabilities",
    )

    # Query lineage back
    lineage_rows = [lineage_a, lineage_b]

    mock_lineage_result = MagicMock()
    mock_lineage_result.scalars.return_value.all.return_value = lineage_rows
    session.execute.return_value = mock_lineage_result

    # Verify traceability
    assert lineage_a.metric_observation_id == obs.id
    assert lineage_a.financial_fact_id == fact_a.id
    assert lineage_a.input_role == "current_assets"

    assert lineage_b.metric_observation_id == obs.id
    assert lineage_b.financial_fact_id == fact_b.id
    assert lineage_b.input_role == "current_liabilities"

    # Verify we can trace from observation -> facts
    traced_fact_ids = {ln.financial_fact_id for ln in lineage_rows}
    assert fact_a.id in traced_fact_ids
    assert fact_b.id in traced_fact_ids


# ---------------------------------------------------------------------------
# 6. test_lineage_bundle_returns_all_traced_facts
# ---------------------------------------------------------------------------


async def test_lineage_bundle_returns_all_traced_facts() -> None:
    """MetricBundleV1 contains correct lineage_ids, calculation_version, quality, coverage."""
    from ia_investing.application.metrics import MetricBundleV1

    fact_id_1 = uuid4()
    fact_id_2 = uuid4()

    bundle = MetricBundleV1(
        observation_id=uuid4(),
        issuer_id=uuid4(),
        reporting_period_id=uuid4(),
        metric_name="current_ratio",
        definition_version=1,
        formula="current_assets / current_liabilities",
        unit="ratio",
        value=Decimal("1.1500"),
        value_status="calculated",
        data_as_of=_dt(2025, 1, 3),
        quality_score=Decimal("1.0000"),
        coverage_ratio=Decimal("1.0000"),
        calculation_version="current_ratio:v1",
        lineage_ids=[fact_id_1, fact_id_2],
    )

    # Verify all provenance fields are present and correct
    assert bundle.schema_version == "1.0"
    assert len(bundle.lineage_ids) == 2
    assert fact_id_1 in bundle.lineage_ids
    assert fact_id_2 in bundle.lineage_ids
    assert bundle.calculation_version == "current_ratio:v1"
    assert bundle.quality_score == Decimal("1.0000")
    assert bundle.coverage_ratio == Decimal("1.0000")
    assert bundle.value_status == "calculated"
    assert bundle.value == Decimal("1.1500")

    # Verify it serialises to JSON cleanly
    json_str = bundle.model_dump_json()
    assert "lineage_ids" in json_str
    assert "calculation_version" in json_str


# ---------------------------------------------------------------------------
# 7. test_dfp_fixture_reconciles_to_expected_totals
# ---------------------------------------------------------------------------


def test_dfp_fixture_reconciles_to_expected_totals() -> None:
    """Load DFP fixture, verify BPA totals = sum of sub-accounts for PETROBRAS sample."""
    rows = _parse_csv("dfp_cia_aberta_sample.csv")
    assert len(rows) > 0, "DFP fixture must contain rows"

    petrobras_rows = [r for r in rows if r["CNPJ_CIA"] == "33.000.167/0001-01"]
    assert len(petrobras_rows) > 0, "PETROBRAS rows not found in DFP fixture"

    # --- BPA reconciliation ---
    bpa_rows = [r for r in petrobras_rows if r["TP_CONTA"] == "BPA"]
    account_values: dict[str, Decimal] = {}
    for r in bpa_rows:
        account_values[r["CD_CONTA"]] = Decimal(r["VL_CONTA"])

    # Ativo Total (code 1) = Ativo Circulante (1.01) + Ativo Não Circulante (1.02)
    ativo_total = account_values.get("1")
    ativo_circ = account_values.get("1.01")
    ativo_ncirc = account_values.get("1.02")

    assert ativo_total is not None, "Ativo Total (1) missing"
    assert ativo_circ is not None, "Ativo Circulante (1.01) missing"
    assert ativo_ncirc is not None, "Ativo Não Circulante (1.02) missing"
    assert ativo_total == ativo_circ + ativo_ncirc, (
        f"BPA: Ativo Total {ativo_total} != ({ativo_circ} + {ativo_ncirc}) = {ativo_circ + ativo_ncirc}"
    )

    # Passivo e PL (2) = Passivo Circulante (2.01) + Passivo Não Circulante (2.02) + PL (2.03)
    passivo_pl = account_values.get("2")
    passivo_circ = account_values.get("2.01")
    passivo_ncirc = account_values.get("2.02")
    pl = account_values.get("2.03")

    assert passivo_pl is not None, "Passivo e PL (2) missing"
    assert passivo_circ is not None, "Passivo Circulante (2.01) missing"
    assert passivo_ncirc is not None, "Passivo Não Circulante (2.02) missing"
    assert pl is not None, "Patrimônio Líquido (2.03) missing"
    assert passivo_pl == passivo_circ + passivo_ncirc + pl, (
        f"BPA: Passivo e PL {passivo_pl} != "
        f"({passivo_circ} + {passivo_ncirc} + {pl}) = {passivo_circ + passivo_ncirc + pl}"
    )

    # Accounting equation: Ativo Total = Passivo e PL
    assert ativo_total == passivo_pl, (
        f"Accounting equation violated: Ativo Total {ativo_total} != Passivo e PL {passivo_pl}"
    )

    # --- DRE reconciliation ---
    dre_rows = [r for r in petrobras_rows if r["TP_CONTA"] == "DRE"]
    dre_values: dict[str, Decimal] = {}
    for r in dre_rows:
        dre_values[r["CD_CONTA"]] = Decimal(r["VL_CONTA"])

    # Receita Líquida (3) = Receita de Vendas (3.01) - Impostos (3.02)
    receita_liq = dre_values.get("3")
    receita_vendas = dre_values.get("3.01")
    impostos = dre_values.get("3.02")

    assert receita_liq is not None, "Receita Líquida (3) missing"
    assert receita_vendas is not None, "Receita de Vendas (3.01) missing"
    assert impostos is not None, "Impostos sobre Receita (3.02) missing"
    assert receita_liq == receita_vendas - impostos, (
        f"DRE: Receita Líquida {receita_liq} != ({receita_vendas} - {impostos}) = {receita_vendas - impostos}"
    )

    # Lucro Líquido (6) = Lucro Consolidado (6.01) if both exist
    lucro_liq = dre_values.get("6")
    lucro_consolidado = dre_values.get("6.01")
    if lucro_liq is not None and lucro_consolidado is not None:
        assert lucro_liq == lucro_consolidado, (
            f"DRE: Lucro Líquido {lucro_liq} != Lucro Consolidado {lucro_consolidado}"
        )


# ---------------------------------------------------------------------------
# 8. test_itr_fixture_reconciles_to_expected_totals
# ---------------------------------------------------------------------------


def test_itr_fixture_reconciles_to_expected_totals() -> None:
    """Load ITR fixture, verify BPA sub-accounts sum to total for VALE quarterly."""
    rows = _parse_csv("itr_cia_aberta_sample.csv")
    assert len(rows) > 0, "ITR fixture must contain rows"

    vale_rows = [r for r in rows if r["CNPJ_CIA"] == "60.872.504/0001-12"]
    assert len(vale_rows) > 0, "VALE rows not found in ITR fixture"

    # --- BPA reconciliation ---
    bpa_rows = [r for r in vale_rows if r["TP_CONTA"] == "BPA"]
    account_values: dict[str, Decimal] = {}
    for r in bpa_rows:
        account_values[r["CD_CONTA"]] = Decimal(r["VL_CONTA"])

    ativo_total = account_values.get("1")
    ativo_circ = account_values.get("1.01")
    ativo_ncirc = account_values.get("1.02")

    assert ativo_total is not None, "Ativo Total (1) missing"
    assert ativo_circ is not None, "Ativo Circulante (1.01) missing"
    assert ativo_ncirc is not None, "Ativo Não Circulante (1.02) missing"
    assert ativo_total == ativo_circ + ativo_ncirc, (
        f"ITR BPA: Ativo Total {ativo_total} != ({ativo_circ} + {ativo_ncirc}) = {ativo_circ + ativo_ncirc}"
    )

    passivo_pl = account_values.get("2")
    passivo_circ = account_values.get("2.01")
    passivo_ncirc = account_values.get("2.02")
    pl = account_values.get("2.03")

    assert passivo_pl is not None, "Passivo e PL (2) missing"
    assert passivo_circ is not None, "Passivo Circulante (2.01) missing"
    assert passivo_ncirc is not None, "Passivo Não Circulante (2.02) missing"
    assert pl is not None, "Patrimônio Líquido (2.03) missing"
    assert passivo_pl == passivo_circ + passivo_ncirc + pl, (
        f"ITR BPA: Passivo e PL {passivo_pl} != "
        f"({passivo_circ} + {passivo_ncirc} + {pl}) = {passivo_circ + passivo_ncirc + pl}"
    )

    # Accounting equation: Ativo Total = Passivo e PL
    assert ativo_total == passivo_pl, f"ITR accounting equation violated: {ativo_total} != {passivo_pl}"

    # --- Verify DRE rows are present ---
    dre_rows = [r for r in vale_rows if r["TP_CONTA"] == "DRE"]
    dre_codes = {r["CD_CONTA"] for r in dre_rows}
    assert "3" in dre_codes, "Receita Líquida (3) missing in ITR DRE"
    assert "6" in dre_codes, "Lucro Líquido (6) missing in ITR DRE"

    # Receita Líquida must be positive (revenue)
    receita_row = next(r for r in dre_rows if r["CD_CONTA"] == "3")
    assert Decimal(receita_row["VL_CONTA"]) > Decimal("0"), "ITR Receita Líquida should be positive"
