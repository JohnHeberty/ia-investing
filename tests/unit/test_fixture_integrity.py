from __future__ import annotations

import csv
import hashlib
import json
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from connectors.b3._cotahist import _parse_csv_int, _parse_csv_price, _parse_date_str

FIXTURES_ROOT = Path(__file__).parents[1] / "fixtures"
MANIFEST_PATH = FIXTURES_ROOT / "manifest.json"


@pytest.fixture(scope="module")
def manifest() -> dict[str, Any]:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def test_manifest_covers_every_data_fixture(manifest: dict[str, Any]) -> None:
    declared = {entry["path"] for entry in manifest["fixtures"]}
    present = {
        path.relative_to(FIXTURES_ROOT).as_posix()
        for path in FIXTURES_ROOT.rglob("*")
        if path.is_file() and (path.suffix in {".csv", ".txt"} or (path.suffix == ".json" and "policy" in path.parts))
    }
    assert declared == present


def test_fixture_hashes_and_utf8(manifest: dict[str, Any]) -> None:
    for entry in manifest["fixtures"]:
        path = FIXTURES_ROOT / entry["path"]
        payload = path.read_bytes()
        assert hashlib.sha256(payload).hexdigest() == entry["sha256"], entry["path"]
        payload.decode(entry["encoding"])


def test_manifest_has_provenance_and_redistribution_policy(manifest: dict[str, Any]) -> None:
    required = {
        "id",
        "path",
        "sha256",
        "bytes",
        "media_type",
        "encoding",
        "profile",
        "source_url",
        "license",
        "terms_url",
        "redistribution_status",
        "transformations",
    }
    for entry in manifest["fixtures"]:
        assert required <= entry.keys(), entry["path"]
        assert entry["source_url"].startswith("https://")
        assert entry["transformations"]
        assert (FIXTURES_ROOT / entry["path"]).stat().st_size == entry["bytes"]
        expected_media_type = "application/json" if entry["path"].endswith(".json") else "text/csv"
        assert entry["media_type"] == expected_media_type


def test_cvm_fixtures_cover_initial_sector_profiles(manifest: dict[str, Any]) -> None:
    profiles = {entry["profile"] for entry in manifest["fixtures"] if entry["path"].startswith("cvm/")}
    assert {"industry", "financial_institution", "utility"} <= profiles


def test_b3_synthetic_csv_matches_parser_contract() -> None:
    fixture = FIXTURES_ROOT / "b3" / "cotahist_synthetic_sample.csv"
    with fixture.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))

    assert {row["Codigo"] for row in rows} == {"PETR4", "ITUB4", "EGIE3"}
    assert all(_parse_date_str(row["Data"]) == date(2024, 3, 26) for row in rows)
    assert all(_parse_csv_price(row["Fechamento"]) > 0 for row in rows)
    assert all(_parse_csv_int(row["Negocios"]) > 0 for row in rows)


def test_utility_fixture_preserves_consolidated_scope_and_scale() -> None:
    fixture = FIXTURES_ROOT / "cvm" / "dfp_utility_consolidated_sample.csv"
    with fixture.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream, delimiter=";"))

    assert rows
    assert {row["CNPJ_CIA"] for row in rows} == {"02.474.103/0001-19"}
    assert all(row["GRUPO_DFP"].startswith("DF Consolidado") for row in rows)
    assert all(row["ESCALA_MOEDA"] == "MIL" for row in rows)
    assert {row["CD_CONTA"] for row in rows} >= {"1", "2", "3.01"}


def test_financial_fixture_preserves_individual_restatement_version() -> None:
    fixture = FIXTURES_ROOT / "cvm" / "dfp_financial_individual_restatement_sample.csv"
    with fixture.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream, delimiter=";"))

    assert rows
    assert {row["CNPJ_CIA"] for row in rows} == {"00.000.208/0001-00"}
    assert {row["VERSAO"] for row in rows} == {"3"}
    assert all(row["GRUPO_DFP"].startswith("DF Individual") for row in rows)
    assert {row["CD_CONTA"] for row in rows} >= {"1", "2", "3.01"}
