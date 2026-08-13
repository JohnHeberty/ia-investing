"""Contract tests for CVM fixture CSVs — validate against official format."""

import csv
from pathlib import Path

FIXTURES_DIR = Path("tests/fixtures/cvm")


def _read_csv(filename: str, delimiter: str = ";") -> list[dict]:
    path = FIXTURES_DIR / filename
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f, delimiter=delimiter))


def test_dfp_fixture_has_required_columns() -> None:
    """DFP fixture must have all required CVM columns."""
    rows = _read_csv("dfp_cia_aberta_sample.csv")
    assert len(rows) > 0
    required = {"CNPJ_CIA", "DT_REFER", "VERSAO", "CD_CONTA", "DS_CONTA", "VL_CONTA"}
    assert required.issubset(set(rows[0].keys())), f"Missing columns: {required - set(rows[0].keys())}"


def test_dfp_fixture_cnpj_format() -> None:
    """DFP fixture CNPJs must be 14 digits (dots and dashes stripped)."""
    rows = _read_csv("dfp_cia_aberta_sample.csv")
    for row in rows:
        cnpj = row.get("CNPJ_CIA", "").strip().replace(".", "").replace("-", "").replace("/", "")
        assert cnpj.isdigit() and len(cnpj) == 14, f"Invalid CNPJ: {row.get('CNPJ_CIA')}"


def test_itr_fixture_has_required_columns() -> None:
    """ITR fixture must have all required CVM columns."""
    rows = _read_csv("itr_cia_aberta_sample.csv")
    assert len(rows) > 0
    required = {"CNPJ_CIA", "DT_REFER", "VERSAO", "CD_CONTA", "DS_CONTA", "VL_CONTA"}
    assert required.issubset(set(rows[0].keys())), f"Missing columns: {required - set(rows[0].keys())}"


def test_cad_fixture_has_required_columns() -> None:
    """Cadastro fixture must have CNPJ and company name."""
    rows = _read_csv("cad_cia_aberta_sample.csv")
    assert len(rows) > 0
    first = rows[0]
    assert "CNPJ_CIA" in first
    assert "DENOM_CIA" in first


def test_dfp_fixture_multi_scope() -> None:
    """DFP fixture contains entries with valid DFP origin."""
    rows = _read_csv("dfp_cia_aberta_sample.csv")
    origins = {row.get("ORIGEM_DADOS", "").strip() for row in rows}
    assert "DFP" in origins
