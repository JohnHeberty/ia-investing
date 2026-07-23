"""Tests for DOU XML parsing and end-to-end policy pipeline lineage."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from connectors.policy._official import (
    FetchedOfficialPayload,
    parse_dou_xml,
)
from ia_investing.domain.policy import (
    HistoricalOutcome,
    ImpactEdge,
    PolicyDeadline,
    PolicyTheme,
    base_rate,
    compute_versioned_features,
    detect_rectification,
    features_hash,
    material_review_required,
    propagate_impact,
    validate_policy_stage_transition,
)
from ia_investing.domain.policy_historical import (
    HISTORICAL_OUTCOMES,
    get_historical_outcomes,
)

FIXTURES = Path(__file__).parents[1] / "fixtures" / "policy"


# ── DOU XML parsing ──────────────────────────────────────────────────────────


class TestDOUXMLParsing:
    def test_parse_dou_xml_extracts_records(self) -> None:
        xml_body = (FIXTURES / "dou_xml_synthetic.xml").read_bytes()
        payload = FetchedOfficialPayload(
            url="https://www.in.gov.br/dou",
            body=xml_body,
            content_sha256="a" * 64,
            media_type="application/xml",
            discovered_at=datetime.now(UTC),
        )
        records = parse_dou_xml(payload)
        assert len(records) == 2
        assert records[0].authority == "Banco Central do Brasil"
        assert records[0].object_type == "Resolução"
        assert records[0].external_id == "doc-901"
        assert records[0].title.startswith("Resolução BCB")
        assert records[1].authority == "Ministério do Meio Ambiente"

    def test_parse_dou_xml_metadata_includes_sha(self) -> None:
        xml_body = (FIXTURES / "dou_xml_synthetic.xml").read_bytes()
        payload = FetchedOfficialPayload(
            url="https://www.in.gov.br/dou",
            body=xml_body,
            content_sha256="b" * 64,
            media_type="application/xml",
            discovered_at=datetime.now(UTC),
        )
        records = parse_dou_xml(payload)
        assert records[0].metadata["source_sha256"] == "b" * 64

    def test_parse_dou_xml_empty_document(self) -> None:
        xml_body = b"<root></root>"
        payload = FetchedOfficialPayload(
            url="https://www.in.gov.br/dou",
            body=xml_body,
            content_sha256="c" * 64,
            media_type="application/xml",
            discovered_at=datetime.now(UTC),
        )
        records = parse_dou_xml(payload)
        assert records == ()

    def test_parse_dou_xml_malformed_raises(self) -> None:
        payload = FetchedOfficialPayload(
            url="https://www.in.gov.br/dou",
            body=b"<unclosed",
            content_sha256="d" * 64,
            media_type="application/xml",
            discovered_at=datetime.now(UTC),
        )
        with pytest.raises(ValueError, match="XML parse error"):
            parse_dou_xml(payload)

    def test_parse_dou_xml_synthetic_fixture_matches(self) -> None:
        xml_body = (FIXTURES / "dou_xml_synthetic.xml").read_bytes()
        payload = FetchedOfficialPayload(
            url="https://www.in.gov.br/dou",
            body=xml_body,
            content_sha256="e" * 64,
            media_type="application/xml",
            discovered_at=datetime.now(UTC),
        )
        records = parse_dou_xml(payload)
        types = {r.object_type for r in records}
        assert "Resolução" in types
        assert "Decreto" in types


# ── Historical outcomes with legal type ──────────────────────────────────────


class TestHistoricalOutcomesLegalType:
    def test_dataset_has_all_legal_types(self) -> None:
        types = {o.legal_type for o in HISTORICAL_OUTCOMES}
        assert types == {"projeto_lei", "decreto", "normativo", "ato_oficial"}

    def test_dataset_has_sources(self) -> None:
        sources = {o.source for o in HISTORICAL_OUTCOMES}
        assert "camara_historical" in sources
        assert "senado_historical" in sources
        assert "dou_historical" in sources
        assert "bcb_historical" in sources

    def test_base_rate_with_legal_type_dataset(self) -> None:
        outcomes = get_historical_outcomes()
        cutoff = datetime(2024, 1, 1, tzinfo=UTC)
        historical = [
            HistoricalOutcome(
                policy_type=o.policy_type,
                stage=o.stage,
                predicted_at=o.predicted_at,
                outcome_at=o.outcome_at,
                outcome=o.outcome,
            )
            for o in outcomes
            if o.outcome_at <= cutoff
        ]
        if historical:
            estimate = base_rate(
                tuple(historical),
                policy_type=historical[0].policy_type,
                stage=historical[0].stage,
                knowledge_cutoff=cutoff,
            )
            assert 0 <= float(estimate.probability) <= 1


# ── E2E lineage: source → sector → driver → issuer → portfolio ──────────────


class TestE2ELineage:
    def test_full_propagation_path(self) -> None:
        edges = (
            ImpactEdge("political_event", "financeiro", "affects_sector", Decimal("0.7"), Decimal("0.9")),
            ImpactEdge("financeiro", "selic_driver", "drives_metric", Decimal("0.8"), Decimal("0.85")),
            ImpactEdge("selic_driver", "bank_issuer", "impacts_issuer", Decimal("0.5"), Decimal("0.8")),
            ImpactEdge("bank_issuer", "portfolio_A", "held_by", Decimal("0.3"), Decimal("0.9")),
        )
        results = propagate_impact("political_event", Decimal(1), edges)
        assert len(results) == 4
        assert results[-1].path == (
            "political_event",
            "financeiro",
            "selic_driver",
            "bank_issuer",
            "portfolio_A",
        )
        assert results[-1].impact > 0

    def test_materiality_requires_all_dimensions(self) -> None:
        assert material_review_required(
            materiality=Decimal("0.9"),
            exposure=Decimal("0.8"),
            corroboration=Decimal("0.9"),
            freshness=Decimal("1"),
        )
        assert not material_review_required(
            materiality=Decimal("0.9"),
            exposure=Decimal("0.8"),
            corroboration=Decimal("0.1"),
            freshness=Decimal("1"),
        )

    def test_versioned_features_with_themes_and_deadlines(self) -> None:
        now = datetime.now(UTC)
        features = compute_versioned_features(
            stage="committee",
            legal_type="projeto_lei",
            themes=(
                PolicyTheme("tributaria", ("financeiro", "varejo"), Decimal("0.8"), Decimal("0.9")),
                PolicyTheme("ambiental", ("energia",), Decimal("0.5"), Decimal("0.7")),
            ),
            deadlines=(
                PolicyDeadline("committee_vote", now + timedelta(days=15), "Prazo comissão"),
                PolicyDeadline("floor_vote", now + timedelta(days=45), "Prazo plenário"),
            ),
            base_rate=Decimal("0.35"),
            corroboration_count=5,
            materiality=Decimal("0.75"),
        )
        h = features_hash(features)
        assert len(h) == 64
        assert features["theme_count"] == 2
        assert features["deadline_count"] == 2

    def test_rectification_tracks_amendment(self) -> None:
        original = "Art. 1 O Banco Central poderá alterar requisitos."
        amended = "Art. 1 O Banco Central deverá alterar requisitos."
        result = detect_rectification(original, amended, rectification_type="amendment")
        assert result is not None
        assert result["rectification_type"] == "amendment"
        assert result["additions"] == 1
        assert result["removals"] == 1

    def test_rectification_revocation(self) -> None:
        original = "Art. 1 norma vigente."
        amended = ""
        result = detect_rectification(original, amended, rectification_type="revocation")
        assert result is not None
        assert result["rectification_type"] == "revocation"

    def test_version_determines_state_machine(self) -> None:
        validate_policy_stage_transition("discovered", "introduced", "projeto_lei")
        validate_policy_stage_transition("discovered", "published", "decreto")
        validate_policy_stage_transition("discovered", "published", "normativo")
        validate_policy_stage_transition("discovered", "published", "ato_oficial")

    def test_pipeline_end_to_end(self) -> None:
        now = datetime.now(UTC)
        policy_type = "tributaria"
        stage = "committee"
        legal_type = "projeto_lei"

        validate_policy_stage_transition("introduced", stage, legal_type)
        themes = (PolicyTheme(policy_type, ("financeiro",), Decimal("0.8"), Decimal("0.9")),)
        deadlines = (PolicyDeadline("committee_vote", now + timedelta(days=20), "Votação"),)
        features = compute_versioned_features(
            stage=stage,
            legal_type=legal_type,
            themes=themes,
            deadlines=deadlines,
            base_rate=Decimal("0.35"),
            corroboration_count=3,
            materiality=Decimal("0.7"),
        )
        h = features_hash(features)
        assert len(h) == 64
        edges = (
            ImpactEdge("policy_event", "financeiro", "affects", Decimal("0.8"), Decimal("0.9")),
            ImpactEdge("financeiro", "bank", "exposes", Decimal("0.5"), Decimal("0.8")),
        )
        impacts = propagate_impact("policy_event", Decimal(1), edges)
        assert impacts[-1].impact > 0
        assert material_review_required(
            materiality=Decimal("0.7"),
            exposure=Decimal("0.8"),
            corroboration=Decimal("0.9"),
            freshness=Decimal("1"),
        )
