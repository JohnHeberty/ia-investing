from __future__ import annotations

import logging
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Literal

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ComplianceCheck:
    code: str
    label: str
    passed: bool
    severity: Literal["info", "warning", "blocking"]
    detail: str = ""


@dataclass(frozen=True, slots=True)
class ComplianceEvaluation:
    overall_status: Literal["compliant", "non_compliant", "needs_review"]
    score: Decimal
    checks: tuple[ComplianceCheck, ...]
    blocking_violations: tuple[str, ...] = field(default_factory=tuple)

    @property
    def is_compliant(self) -> bool:
        return self.overall_status == "compliant"


class CandidateComplianceEvaluator:
    """Deterministic compliance evaluator for candidate investment suggestions.

    Evaluates suggestions against regulatory and internal compliance rules
    without any LLM dependency. Pure business logic.
    """

    def evaluate_source_compliance(
        self,
        sources: list[dict[str, object]],
    ) -> tuple[ComplianceCheck, ...]:
        checks: list[ComplianceCheck] = []

        official_count = sum(1 for s in sources if s.get("official"))
        checks.append(
            ComplianceCheck(
                code="official_sources_present",
                label="Official sources present",
                passed=official_count > 0,
                severity="blocking",
                detail=f"{official_count} official source(s) found",
            )
        )

        verified_count = sum(1 for s in sources if s.get("status") == "verified")
        total_count = len(sources)
        verification_rate = verified_count / total_count if total_count > 0 else 0.0
        checks.append(
            ComplianceCheck(
                code="source_verification_rate",
                label="Source verification rate",
                passed=verification_rate >= 0.5,
                severity="warning",
                detail=f"{verification_rate:.0%} of sources verified ({verified_count}/{total_count})",
            )
        )

        source_kinds = {s.get("kind") for s in sources}
        has_cvm = "cvm_filings" in source_kinds or "cvm_profile" in source_kinds
        checks.append(
            ComplianceCheck(
                code="cvm_regulatory_source",
                label="CVM regulatory source",
                passed=has_cvm,
                severity="blocking",
                detail="CVM filing or profile source present" if has_cvm else "No CVM regulatory source found",
            )
        )

        has_b3 = "b3_listing" in source_kinds
        checks.append(
            ComplianceCheck(
                code="b3_listing_source",
                label="B3 listing source",
                passed=has_b3,
                severity="blocking",
                detail="B3 listing source present" if has_b3 else "No B3 listing source found",
            )
        )

        return tuple(checks)

    def evaluate_data_completeness(
        self,
        fact_count: int,
        source_count: int,
        has_financial_statements: bool,
    ) -> tuple[ComplianceCheck, ...]:
        checks: list[ComplianceCheck] = []

        checks.append(
            ComplianceCheck(
                code="financial_facts_present",
                label="Financial facts present",
                passed=fact_count > 0,
                severity="blocking",
                detail=f"{fact_count} financial fact(s) available",
            )
        )

        checks.append(
            ComplianceCheck(
                code="sufficient_data_coverage",
                label="Sufficient data coverage",
                passed=fact_count >= 10,
                severity="warning",
                detail=f"{fact_count} facts (minimum 10 recommended)",
            )
        )

        detail_msg = "DFP/ITR financial statements present" if has_financial_statements else "No financial statements"
        checks.append(
            ComplianceCheck(
                code="financial_statements_available",
                label="Financial statements available",
                passed=has_financial_statements,
                severity="blocking",
                detail=detail_msg,
            )
        )

        return tuple(checks)

    def evaluate_risk_disclosure(
        self,
        risk_factors: list[str],
        risk_rating: str,
    ) -> tuple[ComplianceCheck, ...]:
        checks: list[ComplianceCheck] = []

        checks.append(
            ComplianceCheck(
                code="risk_factors_disclosed",
                label="Risk factors disclosed",
                passed=len(risk_factors) > 0,
                severity="blocking",
                detail=f"{len(risk_factors)} risk factor(s) disclosed",
            )
        )

        checks.append(
            ComplianceCheck(
                code="adequate_risk_disclosure",
                label="Adequate risk disclosure",
                passed=len(risk_factors) >= 2,
                severity="warning",
                detail=f"{len(risk_factors)} risk factor(s) (minimum 2 recommended)",
            )
        )

        high_risk = risk_rating in ("high", "critical")
        has_risk_ack = any(
            keyword in " ".join(risk_factors).lower()
            for keyword in ["risk", "volatil", "loss", "drawdown", "uncertaint"]
        )
        detail_msg = (
            "High-risk ratings include risk acknowledgment"
            if has_risk_ack
            else "Risk acknowledgment missing for high-risk rating"
        )
        checks.append(
            ComplianceCheck(
                code="high_risk_acknowledgment",
                label="High risk acknowledgment",
                passed=not high_risk or has_risk_ack,
                severity="warning",
                detail=detail_msg,
            )
        )

        return tuple(checks)

    def evaluate_candidate_suggestion(
        self,
        sources: list[dict[str, object]],
        fact_count: int,
        risk_factors: list[str],
        risk_rating: str,
        has_financial_statements: bool,
    ) -> ComplianceEvaluation:
        all_checks: list[ComplianceCheck] = []
        all_checks.extend(self.evaluate_source_compliance(sources))
        all_checks.extend(self.evaluate_data_completeness(fact_count, len(sources), has_financial_statements))
        all_checks.extend(self.evaluate_risk_disclosure(risk_factors, risk_rating))

        blocking = tuple(c.code for c in all_checks if not c.passed and c.severity == "blocking")
        warnings = sum(1 for c in all_checks if not c.passed and c.severity == "warning")

        if blocking:
            status: Literal["compliant", "non_compliant", "needs_review"] = "non_compliant"
        elif warnings > 0:
            status = "needs_review"
        else:
            status = "compliant"

        passed_count = sum(1 for c in all_checks if c.passed)
        score = Decimal(str(round(passed_count / len(all_checks), 4))) if all_checks else Decimal("0")

        return ComplianceEvaluation(
            overall_status=status,
            score=score,
            checks=tuple(all_checks),
            blocking_violations=blocking,
        )
