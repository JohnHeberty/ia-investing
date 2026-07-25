from __future__ import annotations

import logging
from decimal import Decimal

from ..contracts import (
    CommitteeDecisionOutput,
    FundamentalAnalysisOutput,
    RiskAnalysisOutput,
)
from ._types import GuardrailViolationError

logger = logging.getLogger(__name__)


def validate_fundamental_analysis_output(payload: dict[str, object]) -> FundamentalAnalysisOutput:
    """Validate agent output from the fundamentalist analyst agent."""
    output = FundamentalAnalysisOutput.model_validate(payload)

    if not output.findings:
        raise GuardrailViolationError("empty_findings", "Fundamental analysis must produce at least one finding")

    if output.financial_health_score < Decimal("0.1"):
        logger.warning(
            "fundamental_analysis low health score=%.2f ticker=%s",
            output.financial_health_score,
            output.ticker,
        )

    cited_statements = sum(1 for f in output.findings if f.citations)
    coverage = cited_statements / len(output.findings) if output.findings else 0.0
    if coverage < 0.5:
        raise GuardrailViolationError(
            "insufficient_citation_coverage",
            f"Citation coverage {coverage:.0%} below minimum 50% for fundamental analysis",
        )

    return output


def validate_risk_analysis_output(payload: dict[str, object]) -> RiskAnalysisOutput:
    """Validate agent output from the risk director agent."""
    output = RiskAnalysisOutput.model_validate(payload)

    if not output.risk_factors:
        raise GuardrailViolationError("missing_risk_factors", "Risk analysis must identify at least one risk factor")

    if output.risk_rating == "critical" and output.max_drawdown_estimate < Decimal("0.3"):
        raise GuardrailViolationError(
            "risk_rating_inconsistent",
            "Critical risk rating requires max drawdown estimate >= 30%",
        )

    if output.volatility_regime == "extreme" and output.risk_rating in ("low", "medium"):
        raise GuardrailViolationError(
            "volatility_rating_mismatch",
            "Extreme volatility regime is incompatible with low/medium risk rating",
        )

    high_confidence_facts = [f for f in output.findings if f.kind == "fact" and f.confidence >= Decimal("0.7")]
    if not high_confidence_facts:
        raise GuardrailViolationError(
            "insufficient_high_confidence_facts",
            "Risk analysis requires at least one high-confidence fact finding",
        )

    return output


def validate_committee_decision_output(payload: dict[str, object]) -> CommitteeDecisionOutput:
    """Validate agent output from the investment committee agent."""
    output = CommitteeDecisionOutput.model_validate(payload)

    if output.decision == "approve" and output.confidence < Decimal("0.6"):
        raise GuardrailViolationError(
            "approval_confidence_too_low",
            "Committee approval requires confidence >= 0.6",
        )

    if output.decision == "reject" and not output.rationale:
        raise GuardrailViolationError(
            "rejection_without_rationale",
            "Committee rejection must include rationale",
        )

    if output.risk_acknowledgment.lower().strip() in ("", "none", "n/a"):
        raise GuardrailViolationError(
            "missing_risk_acknowledgment",
            "Committee must acknowledge risks in the decision",
        )

    return output


def validate_candidate_agent_output(
    capability: str,
    payload: dict[str, object],
) -> dict[str, object]:
    """Dispatch to the appropriate candidate-specific validator."""
    validators = {
        "fundamentalist_analyst": validate_fundamental_analysis_output,
        "risk_director": validate_risk_analysis_output,
        "investment_committee": validate_committee_decision_output,
    }
    validator = validators.get(capability)
    if validator is None:
        return payload
    validated = validator(payload)
    return validated.model_dump(mode="json")
