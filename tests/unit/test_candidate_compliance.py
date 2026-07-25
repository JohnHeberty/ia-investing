from __future__ import annotations

from decimal import Decimal

import pytest

from ia_investing.candidate_intelligence.compliance import (
    CandidateComplianceEvaluator,
)


@pytest.fixture
def evaluator() -> CandidateComplianceEvaluator:
    return CandidateComplianceEvaluator()


class TestSourceCompliance:
    def test_compliant_sources(self, evaluator: CandidateComplianceEvaluator) -> None:
        sources = [
            {"kind": "cvm_filings", "status": "verified", "official": True},
            {"kind": "b3_listing", "status": "verified", "official": True},
            {"kind": "investor_relations", "status": "verified", "official": True},
        ]
        checks = evaluator.evaluate_source_compliance(sources)
        assert all(c.passed for c in checks)

    def test_no_official_sources_blocking(self, evaluator: CandidateComplianceEvaluator) -> None:
        sources = [
            {"kind": "investor_relations", "status": "discovered", "official": False},
        ]
        checks = evaluator.evaluate_source_compliance(sources)
        blocking = [c for c in checks if c.severity == "blocking" and not c.passed]
        assert any(c.code == "official_sources_present" for c in blocking)

    def test_no_cvm_source_blocking(self, evaluator: CandidateComplianceEvaluator) -> None:
        sources = [
            {"kind": "b3_listing", "status": "verified", "official": True},
            {"kind": "investor_relations", "status": "verified", "official": True},
        ]
        checks = evaluator.evaluate_source_compliance(sources)
        blocking = [c for c in checks if c.severity == "blocking" and not c.passed]
        assert any(c.code == "cvm_regulatory_source" for c in blocking)

    def test_no_b3_source_blocking(self, evaluator: CandidateComplianceEvaluator) -> None:
        sources = [
            {"kind": "cvm_filings", "status": "verified", "official": True},
        ]
        checks = evaluator.evaluate_source_compliance(sources)
        blocking = [c for c in checks if c.severity == "blocking" and not c.passed]
        assert any(c.code == "b3_listing_source" for c in blocking)

    def test_empty_sources_all_blocking(self, evaluator: CandidateComplianceEvaluator) -> None:
        checks = evaluator.evaluate_source_compliance([])
        blocking = [c for c in checks if c.severity == "blocking"]
        assert all(not c.passed for c in blocking)


class TestDataCompleteness:
    def test_compliant_data(self, evaluator: CandidateComplianceEvaluator) -> None:
        checks = evaluator.evaluate_data_completeness(fact_count=50, source_count=3, has_financial_statements=True)
        assert all(c.passed for c in checks)

    def test_no_facts_blocking(self, evaluator: CandidateComplianceEvaluator) -> None:
        checks = evaluator.evaluate_data_completeness(fact_count=0, source_count=3, has_financial_statements=True)
        blocking = [c for c in checks if c.severity == "blocking" and not c.passed]
        assert any(c.code == "financial_facts_present" for c in blocking)

    def test_low_fact_count_warning(self, evaluator: CandidateComplianceEvaluator) -> None:
        checks = evaluator.evaluate_data_completeness(fact_count=5, source_count=3, has_financial_statements=True)
        warnings = [c for c in checks if c.severity == "warning" and not c.passed]
        assert any(c.code == "sufficient_data_coverage" for c in warnings)

    def test_no_financial_statements_blocking(self, evaluator: CandidateComplianceEvaluator) -> None:
        checks = evaluator.evaluate_data_completeness(fact_count=20, source_count=3, has_financial_statements=False)
        blocking = [c for c in checks if c.severity == "blocking" and not c.passed]
        assert any(c.code == "financial_statements_available" for c in blocking)


class TestRiskDisclosure:
    def test_compliant_risk(self, evaluator: CandidateComplianceEvaluator) -> None:
        checks = evaluator.evaluate_risk_disclosure(
            risk_factors=["Oil price volatility", "FX risk"],
            risk_rating="medium",
        )
        assert all(c.passed for c in checks)

    def test_no_risk_factors_blocking(self, evaluator: CandidateComplianceEvaluator) -> None:
        checks = evaluator.evaluate_risk_disclosure(risk_factors=[], risk_rating="medium")
        blocking = [c for c in checks if c.severity == "blocking" and not c.passed]
        assert any(c.code == "risk_factors_disclosed" for c in blocking)

    def test_single_risk_factor_warning(self, evaluator: CandidateComplianceEvaluator) -> None:
        checks = evaluator.evaluate_risk_disclosure(risk_factors=["Only one"], risk_rating="medium")
        warnings = [c for c in checks if c.severity == "warning" and not c.passed]
        assert any(c.code == "adequate_risk_disclosure" for c in warnings)

    def test_high_risk_no_ack_warning(self, evaluator: CandidateComplianceEvaluator) -> None:
        checks = evaluator.evaluate_risk_disclosure(
            risk_factors=["Something unrelated"],
            risk_rating="critical",
        )
        warnings = [c for c in checks if c.severity == "warning" and not c.passed]
        assert any(c.code == "high_risk_acknowledgment" for c in warnings)

    def test_high_risk_with_ack_ok(self, evaluator: CandidateComplianceEvaluator) -> None:
        checks = evaluator.evaluate_risk_disclosure(
            risk_factors=["High volatility risk", "Drawdown potential"],
            risk_rating="high",
        )
        assert all(c.passed for c in checks)


class TestFullEvaluation:
    def test_compliant_candidate(self, evaluator: CandidateComplianceEvaluator) -> None:
        result = evaluator.evaluate_candidate_suggestion(
            sources=[
                {"kind": "cvm_filings", "status": "verified", "official": True},
                {"kind": "b3_listing", "status": "verified", "official": True},
            ],
            fact_count=50,
            risk_factors=["Commodity risk", "FX risk"],
            risk_rating="medium",
            has_financial_statements=True,
        )
        assert result.is_compliant
        assert result.overall_status == "compliant"
        assert result.score >= Decimal("0.8")

    def test_non_compliant_candidate(self, evaluator: CandidateComplianceEvaluator) -> None:
        result = evaluator.evaluate_candidate_suggestion(
            sources=[],
            fact_count=0,
            risk_factors=[],
            risk_rating="high",
            has_financial_statements=False,
        )
        assert not result.is_compliant
        assert result.overall_status == "non_compliant"
        assert len(result.blocking_violations) > 0

    def test_needs_review_candidate(self, evaluator: CandidateComplianceEvaluator) -> None:
        result = evaluator.evaluate_candidate_suggestion(
            sources=[
                {"kind": "cvm_filings", "status": "verified", "official": True},
                {"kind": "b3_listing", "status": "verified", "official": True},
            ],
            fact_count=5,
            risk_factors=["Risk"],
            risk_rating="medium",
            has_financial_statements=True,
        )
        assert result.overall_status == "needs_review"
        assert not result.is_compliant
        assert len(result.blocking_violations) == 0
