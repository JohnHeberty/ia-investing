from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from ia_investing.ai.guardrails import (
    GuardrailViolationError,
    validate_candidate_agent_output,
    validate_committee_decision_output,
    validate_fundamental_analysis_output,
    validate_risk_analysis_output,
)


def _base_fundamental_payload(**overrides: object) -> dict[str, object]:
    base = {
        "ticker": "PETR4",
        "issuer_id": "5b940ca0-1c9e-4bd4-a5e0-123456789abc",
        "summary": "Petrobras shows strong cash generation with manageable leverage.",
        "findings": [
            {
                "statement": "Net income grew 15% YoY",
                "kind": "fact",
                "confidence": 0.85,
                "citations": [{"evidence_id": "5b940ca0-1c9e-4bd4-a5e0-123456789001", "claim": "DFP 2025"}],
            },
            {
                "statement": "Dividend yield appears attractive",
                "kind": "inference",
                "confidence": 0.7,
                "citations": [],
            },
        ],
        "financial_health_score": 0.75,
        "key_metrics": {"roe": "18%", "debt_ebitda": "1.2x"},
        "risks": ["Oil price volatility"],
        "catalysts": ["Pre-salt production growth"],
        "knowledge_cutoff": datetime(2025, 12, 31, tzinfo=UTC),
    }
    base.update(overrides)
    return base


def _base_risk_payload(**overrides: object) -> dict[str, object]:
    base = {
        "ticker": "PETR4",
        "issuer_id": "5b940ca0-1c9e-4bd4-a5e0-123456789abc",
        "summary": "Moderate risk profile with commodity exposure.",
        "findings": [
            {
                "statement": "Oil price dropped 20% in Q4",
                "kind": "fact",
                "confidence": 0.9,
                "citations": [{"evidence_id": "5b940ca0-1c9e-4bd4-a5e0-123456789002", "claim": "Market data"}],
            },
            {
                "statement": "Currency depreciation may impact costs",
                "kind": "inference",
                "confidence": 0.6,
                "citations": [],
            },
        ],
        "risk_rating": "medium",
        "risk_factors": ["Commodity price risk", "FX risk"],
        "max_drawdown_estimate": Decimal("0.25"),
        "volatility_regime": "normal",
        "knowledge_cutoff": datetime(2025, 12, 31, tzinfo=UTC),
    }
    base.update(overrides)
    return base


def _base_committee_payload(**overrides: object) -> dict[str, object]:
    base = {
        "ticker": "PETR4",
        "decision": "approve",
        "confidence": 0.75,
        "rationale": "Strong fundamentals with acceptable risk profile.",
        "conditions": [],
        "dissenting_views": [],
        "risk_acknowledgment": "Oil price exposure is the primary risk factor.",
        "knowledge_cutoff": datetime(2025, 12, 31, tzinfo=UTC),
    }
    base.update(overrides)
    return base


class TestValidateFundamentalAnalysisOutput:
    def test_valid_output_passes(self) -> None:
        output = validate_fundamental_analysis_output(_base_fundamental_payload())
        assert output.ticker == "PETR4"
        assert len(output.findings) == 2

    def test_empty_findings_rejected(self) -> None:
        with pytest.raises(GuardrailViolationError, match="empty_findings"):
            validate_fundamental_analysis_output(_base_fundamental_payload(findings=[]))

    def test_low_citation_coverage_accepted(self) -> None:
        citation = {"evidence_id": "5b940ca0-1c9e-4bd4-a5e0-123456789001", "claim": "DFP"}
        payload = _base_fundamental_payload(
            findings=[
                {"statement": "Revenue grew", "kind": "fact", "confidence": 0.8, "citations": [citation]},
                {"statement": "Costs fell", "kind": "inference", "confidence": 0.7, "citations": []},
                {"statement": "Margin expanded", "kind": "inference", "confidence": 0.6, "citations": []},
                {"statement": "Outlook positive", "kind": "inference", "confidence": 0.5, "citations": []},
            ]
        )
        output = validate_fundamental_analysis_output(payload)
        assert len(output.findings) == 4

    def test_all_inferences_no_citations_ok(self) -> None:
        citation = {"evidence_id": "5b940ca0-1c9e-4bd4-a5e0-123456789001", "claim": "Market analysis"}
        payload = _base_fundamental_payload(
            findings=[
                {
                    "statement": "Outlook seems positive",
                    "kind": "inference",
                    "confidence": 0.6,
                    "citations": [citation],
                },
            ]
        )
        output = validate_fundamental_analysis_output(payload)
        assert len(output.findings) == 1

    def test_extra_fields_rejected(self) -> None:
        payload = _base_fundamental_payload()
        payload["injected_field"] = "malicious"
        with pytest.raises(ValidationError):
            validate_fundamental_analysis_output(payload)


class TestValidateRiskAnalysisOutput:
    def test_valid_output_passes(self) -> None:
        output = validate_risk_analysis_output(_base_risk_payload())
        assert output.risk_rating == "medium"
        assert len(output.risk_factors) == 2

    def test_missing_risk_factors_rejected(self) -> None:
        with pytest.raises(Exception, match="risk_factors"):
            validate_risk_analysis_output(_base_risk_payload(risk_factors=[]))

    def test_critical_rating_inconsistent_with_low_drawdown(self) -> None:
        ev1 = {"evidence_id": "5b940ca0-1c9e-4bd4-a5e0-123456789002", "claim": "Market data"}
        ev2 = {"evidence_id": "5b940ca0-1c9e-4bd4-a5e0-123456789003", "claim": "DFP"}
        ev3 = {"evidence_id": "5b940ca0-1c9e-4bd4-a5e0-123456789004", "claim": "News"}
        with pytest.raises(GuardrailViolationError, match="risk_rating_inconsistent"):
            validate_risk_analysis_output(
                _base_risk_payload(
                    risk_rating="critical",
                    max_drawdown_estimate=Decimal("0.2"),
                    findings=[
                        {"statement": "Oil price dropped 20%", "kind": "fact", "confidence": 0.9, "citations": [ev1]},
                        {"statement": "Leverage increasing", "kind": "fact", "confidence": 0.8, "citations": [ev2]},
                        {"statement": "Political risk rising", "kind": "fact", "confidence": 0.75, "citations": [ev3]},
                    ],
                )
            )

    def test_extreme_volatility_with_low_rating_rejected(self) -> None:
        with pytest.raises(GuardrailViolationError, match="volatility_rating_mismatch"):
            validate_risk_analysis_output(_base_risk_payload(volatility_regime="extreme", risk_rating="low"))

    def test_no_high_confidence_facts_accepted(self) -> None:
        payload = _base_risk_payload(
            findings=[
                {"statement": "Maybe risky", "kind": "inference", "confidence": 0.4, "citations": []},
            ]
        )
        output = validate_risk_analysis_output(payload)
        assert len(output.findings) == 1


class TestValidateCommitteeDecisionOutput:
    def test_valid_approval_passes(self) -> None:
        output = validate_committee_decision_output(_base_committee_payload())
        assert output.decision == "approve"
        assert output.confidence == Decimal("0.75")

    def test_low_confidence_approval_rejected(self) -> None:
        with pytest.raises(GuardrailViolationError, match="approval_confidence_too_low"):
            validate_committee_decision_output(_base_committee_payload(confidence=Decimal("0.5")))

    def test_rejection_without_rationale_rejected(self) -> None:
        with pytest.raises(Exception, match="rationale"):
            validate_committee_decision_output(_base_committee_payload(decision="reject", rationale=""))

    def test_conditional_without_conditions_rejected(self) -> None:
        with pytest.raises(Exception, match="conditions"):
            validate_committee_decision_output(_base_committee_payload(decision="conditional", conditions=[]))

    def test_missing_risk_acknowledgment_rejected(self) -> None:
        with pytest.raises(GuardrailViolationError, match="missing_risk_acknowledgment"):
            validate_committee_decision_output(_base_committee_payload(risk_acknowledgment="none"))

    def test_valid_conditional_passes(self) -> None:
        output = validate_committee_decision_output(
            _base_committee_payload(
                decision="conditional",
                conditions=["Board approval required"],
                confidence=Decimal("0.7"),
            )
        )
        assert output.decision == "conditional"
        assert len(output.conditions) == 1


class TestValidateCandidateAgentOutput:
    def test_dispatches_to_fundamental(self) -> None:
        result = validate_candidate_agent_output("fundamentalist_analyst", _base_fundamental_payload())
        assert result["ticker"] == "PETR4"

    def test_dispatches_to_risk(self) -> None:
        result = validate_candidate_agent_output("risk_director", _base_risk_payload())
        assert result["risk_rating"] == "medium"

    def test_dispatches_to_committee(self) -> None:
        result = validate_candidate_agent_output("investment_committee", _base_committee_payload())
        assert result["decision"] == "approve"

    def test_unknown_capability_passthrough(self) -> None:
        payload = {"some": "data"}
        result = validate_candidate_agent_output("unknown_agent", payload)
        assert result == payload

    def test_guardrail_error_propagates(self) -> None:
        with pytest.raises(GuardrailViolationError, match="empty_findings"):
            validate_candidate_agent_output("fundamentalist_analyst", _base_fundamental_payload(findings=[]))
