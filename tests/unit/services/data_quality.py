"""Tests for the data_quality package and QualityGovernanceService."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from database.models.data_governance import QualityIncident, QualityRule, QuarantineRecord
from data_quality._accounting import REQUIRED_FIELDS, run_all_checks
from data_quality._balance_sheet import validate_balance_sheet
from data_quality._cash_flow import validate_cash_flow
from data_quality._completeness import check_data_completeness
from data_quality._dre import validate_dre
from data_quality._models import ValidationResult, _close, _get, _make
from data_quality._temporal import check_temporal_consistency
from ia_investing.application.data_quality import (
    ALLOWED_TRANSITIONS,
    QualityGateResult,
    QualityGovernanceService,
    validate_transition,
)
from ia_investing.application.audit_service import create_domain_audit_entry


# ---------------------------------------------------------------------------
# _models.py
# ---------------------------------------------------------------------------
class TestClose:
    def test_both_zero(self):
        assert _close(0.0, 0.0) is True

    def test_exact_match(self):
        assert _close(100.0, 100.0) is True

    def test_within_tolerance(self):
        assert _close(100.0, 100.05) is True

    def test_outside_tolerance(self):
        assert _close(100.0, 110.0) is False

    def test_custom_tolerance(self):
        assert _close(100.0, 110.0, tolerance_pct=0.2) is True


class TestGet:
    def test_returns_float(self):
        assert _get({"x": 42}, "x") == 42.0

    def test_missing_raises(self):
        with pytest.raises(ValueError, match="missing"):
            _get({}, "x")


class TestMake:
    def test_creates_validation_result(self):
        r = _make("check1", True, "entity", "e1", severity="info", key="val")
        assert r.check_name == "check1"
        assert r.passed is True
        assert r.severity == "info"
        assert r.details["key"] == "val"


# ---------------------------------------------------------------------------
# _balance_sheet.py
# ---------------------------------------------------------------------------
def _valid_bs():
    return {
        "entity_id": "test",
        "total_assets": 1000,
        "total_liabilities": 400,
        "equity": 600,
        "current_assets": 300,
        "non_current_assets": 700,
        "cash": 100,
        "accounts_receivable": 50,
        "inventory": 150,
    }


class TestValidateBalanceSheet:
    def test_valid_balanced(self):
        results = validate_balance_sheet(_valid_bs())
        assert any(r.check_name == "balance_sheet_balances" and r.passed for r in results)

    def test_missing_fields(self):
        results = validate_balance_sheet({"entity_id": "test"})
        assert len(results) == 1
        assert results[0].check_name == "balance_sheet_required_fields"
        assert results[0].passed is False

    def test_unbalanced(self):
        data = _valid_bs()
        data["total_assets"] = 2000
        results = validate_balance_sheet(data)
        balance = next(r for r in results if r.check_name == "balance_sheet_balances")
        assert balance.passed is False

    def test_negative_field(self):
        data = _valid_bs()
        data["cash"] = -50
        results = validate_balance_sheet(data)
        cash_check = next(r for r in results if r.check_name == "cash_non_negative")
        assert cash_check.passed is False

    def test_negative_equity_severity_warning(self):
        data = _valid_bs()
        data["equity"] = -100
        results = validate_balance_sheet(data)
        eq_check = next(r for r in results if r.check_name == "equity_non_negative")
        assert eq_check.severity == "warning"


# ---------------------------------------------------------------------------
# _cash_flow.py
# ---------------------------------------------------------------------------
def _valid_cf():
    return {
        "entity_id": "test",
        "operating_cash_flow": 500,
        "capital_expenditure": -100,
        "free_cash_flow": 400,
        "net_income": 200,
    }


class TestValidateCashFlow:
    def test_valid(self):
        results = validate_cash_flow(_valid_cf())
        assert any(r.passed for r in results)

    def test_missing_fields(self):
        results = validate_cash_flow({"entity_id": "test"})
        assert results[0].check_name == "cash_flow_required_fields"

    def test_fcf_consistency(self):
        data = _valid_cf()
        data["free_cash_flow"] = 999
        results = validate_cash_flow(data)
        fcf = next(r for r in results if r.check_name == "free_cash_flow_consistency")
        assert fcf.passed is False

    def test_net_income_zero(self):
        data = _valid_cf()
        data["net_income"] = 0
        results = validate_cash_flow(data)
        assert any(r.check_name == "operating_cf_vs_net_income" for r in results)

    def test_ratio_out_of_range(self):
        data = _valid_cf()
        data["net_income"] = 1
        data["operating_cash_flow"] = 100
        results = validate_cash_flow(data)
        ocf = next(r for r in results if r.check_name == "operating_cf_vs_net_income")
        assert ocf.passed is False


# ---------------------------------------------------------------------------
# _dre.py
# ---------------------------------------------------------------------------
def _valid_dre():
    return {
        "entity_id": "test",
        "receita_liquida": 1000,
        "custo_receita": 600,
        "despesas_operacionais": 100,
        "ebitda": 300,
        "ebit": 250,
        "despesas_financeiras": 50,
        "impostos": 30,
        "lucro_liquido": 170,
    }


class TestValidateDRE:
    def test_valid(self):
        results = validate_dre(_valid_dre())
        assert all(r.passed for r in results)

    def test_missing_fields(self):
        results = validate_dre({"entity_id": "test"})
        assert results[0].check_name == "dre_required_fields"

    def test_negative_receita(self):
        data = _valid_dre()
        data["receita_liquida"] = -100
        results = validate_dre(data)
        check = next(r for r in results if r.check_name == "receita_liquida_non_negative")
        assert check.passed is False

    def test_custo_exceeds_receita(self):
        data = _valid_dre()
        data["custo_receita"] = 2000
        results = validate_dre(data)
        check = next(r for r in results if r.check_name == "custo_receita_lte_receita")
        assert check.passed is False

    def test_ebitda_inconsistency(self):
        data = _valid_dre()
        data["ebitda"] = 9999
        results = validate_dre(data)
        check = next(r for r in results if r.check_name == "ebitda_consistency")
        assert check.passed is False

    def test_lucro_inconsistency(self):
        data = _valid_dre()
        data["lucro_liquido"] = 9999
        results = validate_dre(data)
        check = next(r for r in results if r.check_name == "lucro_liquido_consistency")
        assert check.passed is False


# ---------------------------------------------------------------------------
# _completeness.py
# ---------------------------------------------------------------------------
class TestCheckDataCompleteness:
    def test_all_present(self):
        results = check_data_completeness("test", {"a": 1, "b": 2}, ["a", "b"])
        assert results[0].passed is True
        assert len(results) == 1

    def test_missing_fields(self):
        results = check_data_completeness("test", {"a": 1}, ["a", "b", "c"])
        assert results[0].passed is False
        assert len(results) == 3  # overall + 2 missing fields

    def test_none_values_count_as_missing(self):
        results = check_data_completeness("test", {"a": None}, ["a"])
        assert results[0].passed is False

    def test_empty_required(self):
        results = check_data_completeness("test", {}, [])
        assert results[0].passed is True


# ---------------------------------------------------------------------------
# _temporal.py
# ---------------------------------------------------------------------------
class TestCheckTemporalConsistency:
    def test_empty_series(self):
        results = check_temporal_consistency([], "date", "value")
        assert results[0].check_name == "temporal_empty_series"
        assert results[0].passed is False

    def test_sorted_dates(self):
        series = [
            {"date": "2024-01-01", "value": 10},
            {"date": "2024-02-01", "value": 20},
            {"date": "2024-03-01", "value": 30},
        ]
        results = check_temporal_consistency(series, "date", "value")
        sorted_check = next(r for r in results if r.check_name == "temporal_sorted")
        assert sorted_check.passed is True

    def test_unsorted_dates(self):
        series = [
            {"date": "2024-03-01", "value": 30},
            {"date": "2024-01-01", "value": 10},
        ]
        results = check_temporal_consistency(series, "date", "value")
        sorted_check = next(r for r in results if r.check_name == "temporal_sorted")
        assert sorted_check.passed is False

    def test_duplicates(self):
        series = [
            {"date": "2024-01-01", "value": 10},
            {"date": "2024-01-01", "value": 20},
        ]
        results = check_temporal_consistency(series, "date", "value")
        dup_check = next(r for r in results if r.check_name == "temporal_no_duplicates")
        assert dup_check.passed is False

    def test_large_gaps(self):
        series = [
            {"date": "2024-01-01", "value": 10},
            {"date": "2024-12-31", "value": 20},
        ]
        results = check_temporal_consistency(series, "date", "value", max_gap_days=30)
        gap_check = next(r for r in results if r.check_name == "temporal_no_large_gaps")
        assert gap_check.passed is False

    def test_no_gaps(self):
        series = [
            {"date": "2024-01-01", "value": 10},
            {"date": "2024-01-15", "value": 20},
        ]
        results = check_temporal_consistency(series, "date", "value", max_gap_days=30)
        gap_check = next(r for r in results if r.check_name == "temporal_no_large_gaps")
        assert gap_check.passed is True

    def test_single_record(self):
        series = [{"date": "2024-01-01", "value": 10}]
        results = check_temporal_consistency(series, "date", "value")
        assert len(results) == 3


# ---------------------------------------------------------------------------
# _accounting.py
# ---------------------------------------------------------------------------
class TestRunAllChecks:
    def test_balance_sheet(self):
        results = run_all_checks("BALANCE_SHEET", _valid_bs())
        assert any(r.passed for r in results)

    def test_dre(self):
        results = run_all_checks("DRE", _valid_dre())
        assert any(r.passed for r in results)

    def test_cash_flow(self):
        results = run_all_checks("CASH_FLOW", _valid_cf())
        assert any(r.passed for r in results)

    def test_unknown_type(self):
        results = run_all_checks("UNKNOWN", {})
        assert results[0].check_name == "unknown_statement_type"

    def test_missing_fields_triggers_completeness(self):
        results = run_all_checks("BALANCE_SHEET", {"entity_id": "test"})
        assert any(r.check_name == "completeness_overall" for r in results)

    def test_required_fields_populated(self):
        assert "BALANCE_SHEET" in REQUIRED_FIELDS
        assert "DRE" in REQUIRED_FIELDS
        assert "CASH_FLOW" in REQUIRED_FIELDS


# ---------------------------------------------------------------------------
# validate_transition pure function
# ---------------------------------------------------------------------------
@pytest.mark.unit
class TestValidateTransition:
    @pytest.mark.parametrize(
        "current,target",
        [
            ("open", "acknowledged"),
            ("open", "resolved"),
            ("open", "waived"),
            ("acknowledged", "resolved"),
            ("acknowledged", "waived"),
            ("waived", "open"),
        ],
    )
    def test_valid_transitions(self, current: str, target: str) -> None:
        validate_transition(current, target)

    @pytest.mark.parametrize(
        "current,target",
        [
            ("resolved", "open"),
            ("resolved", "acknowledged"),
            ("open", "open"),
            ("acknowledged", "open"),
            ("completed", "open"),
        ],
    )
    def test_invalid_transitions(self, current: str, target: str) -> None:
        with pytest.raises(ValueError, match="invalid"):
            validate_transition(current, target)

    def test_unknown_state_fails(self) -> None:
        with pytest.raises(ValueError, match="invalid"):
            validate_transition("unknown", "resolved")


@pytest.mark.unit
class TestQualityGateResult:
    def test_default_fields(self) -> None:
        r = QualityGateResult(promotion_allowed=True)
        assert r.promotion_allowed is True
        assert r.incident_id is None
        assert r.quarantine_id is None

    def test_frozen(self) -> None:
        r = QualityGateResult(promotion_allowed=False, incident_id=uuid4())
        with pytest.raises(AttributeError):
            r.promotion_allowed = True  # type: ignore[misc]


# ---------------------------------------------------------------------------
# QualityGovernanceService.apply_gate
# ---------------------------------------------------------------------------
def _validation(check: str = "rev_rec_check", passed: bool = False) -> ValidationResult:
    return ValidationResult(
        check_name=check,
        passed=passed,
        entity_type="financial_fact",
        entity_id="fact-1",
        details={},
        severity="error",
    )


def _rule(*, code: str = "rev_rec_check", is_material: bool = True, severity: str = "error") -> QualityRule:
    r = MagicMock(spec=QualityRule)
    r.id = uuid4()
    r.code = code
    r.is_material = is_material
    r.severity = severity
    return r


@pytest.mark.unit
class TestApplyGate:
    @pytest.mark.asyncio
    async def test_rule_not_found(self) -> None:
        session = AsyncMock()
        session.get = AsyncMock(return_value=None)
        svc = QualityGovernanceService(session)
        with pytest.raises(ValueError, match="quality rule not found"):
            await svc.apply_gate(uuid4(), uuid4(), _validation(), "ref", "role", uuid4())

    @pytest.mark.asyncio
    async def test_check_name_mismatch(self) -> None:
        session = AsyncMock()
        rule = _rule(code="expected_check")
        session.get = AsyncMock(return_value=rule)
        svc = QualityGovernanceService(session)
        val = _validation(check="different_check")
        with pytest.raises(ValueError, match="does not match"):
            await svc.apply_gate(uuid4(), rule.id, val, "ref", "role", uuid4())

    @pytest.mark.asyncio
    async def test_validation_passed_allows_promotion(self) -> None:
        session = AsyncMock()
        rule = _rule()
        session.get = AsyncMock(return_value=rule)
        svc = QualityGovernanceService(session)
        val = _validation(passed=True)
        result = await svc.apply_gate(uuid4(), rule.id, val, "ref", "role", uuid4())
        assert result.promotion_allowed is True

    @pytest.mark.asyncio
    async def test_non_material_rule_allows_promotion(self) -> None:
        session = AsyncMock()
        rule = _rule(is_material=False)
        session.get = AsyncMock(return_value=rule)
        svc = QualityGovernanceService(session)
        val = _validation(passed=False)
        result = await svc.apply_gate(uuid4(), rule.id, val, "ref", "role", uuid4())
        assert result.promotion_allowed is True

    @pytest.mark.asyncio
    async def test_existing_incident_returns_blocked(self) -> None:
        session = AsyncMock()
        rule = _rule()
        existing_incident = MagicMock(spec=QualityIncident)
        existing_incident.id = uuid4()
        quarantine = MagicMock(spec=QuarantineRecord)
        quarantine.id = uuid4()

        session.get = AsyncMock(return_value=rule)
        execute_results = [
            MagicMock(scalar_one_or_none=MagicMock(return_value=existing_incident)),
            MagicMock(scalar_one=MagicMock(return_value=quarantine)),
        ]
        session.execute = AsyncMock(side_effect=execute_results)

        svc = QualityGovernanceService(session)
        result = await svc.apply_gate(uuid4(), rule.id, _validation(), "ref", "role", uuid4())
        assert result.promotion_allowed is False
        assert result.incident_id == existing_incident.id
        assert result.quarantine_id == quarantine.id

    @pytest.mark.asyncio
    @patch("ia_investing.application.data_quality.create_domain_audit_entry", new_callable=AsyncMock)
    async def test_new_incident_created_on_failure(self, mock_audit: AsyncMock) -> None:
        mock_audit.return_value = MagicMock()
        session = AsyncMock()
        rule = _rule()
        session.get = AsyncMock(return_value=rule)
        session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
        session.flush = AsyncMock()

        added = []
        session.add = MagicMock(side_effect=lambda obj: added.append(obj))

        svc = QualityGovernanceService(session)
        sv_id = uuid4()
        result = await svc.apply_gate(sv_id, rule.id, _validation(), "payload-ref", "data-engineer", uuid4())
        assert result.promotion_allowed is False
        types_added = [type(o).__name__ for o in added]
        assert "QualityIncident" in types_added
        assert "QuarantineRecord" in types_added
        assert mock_audit.called


# ---------------------------------------------------------------------------
# QualityGovernanceService.transition
# ---------------------------------------------------------------------------
@pytest.mark.unit
class TestTransition:
    @pytest.mark.asyncio
    async def test_missing_permission(self) -> None:
        session = AsyncMock()
        svc = QualityGovernanceService(session)
        with pytest.raises(PermissionError, match="quality_incidents:manage"):
            await svc.transition(uuid4(), "resolved", "user", frozenset(), uuid4())

    @pytest.mark.asyncio
    async def test_incident_not_found(self) -> None:
        session = AsyncMock()
        session.get = AsyncMock(return_value=None)
        svc = QualityGovernanceService(session)
        with pytest.raises(LookupError, match="not found"):
            await svc.transition(
                uuid4(), "resolved", "user", frozenset({"quality_incidents:manage"}), uuid4()
            )

    @pytest.mark.asyncio
    async def test_invalid_transition(self) -> None:
        session = AsyncMock()
        incident = MagicMock(spec=QualityIncident)
        incident.status = "resolved"
        session.get = AsyncMock(return_value=incident)
        svc = QualityGovernanceService(session)
        with pytest.raises(ValueError, match="invalid"):
            await svc.transition(
                incident.id, "open", "user", frozenset({"quality_incidents:manage"}), uuid4()
            )

    @pytest.mark.asyncio
    async def test_resolve_requires_reason(self) -> None:
        session = AsyncMock()
        incident = MagicMock(spec=QualityIncident)
        incident.id = uuid4()
        incident.status = "open"
        session.get = AsyncMock(return_value=incident)
        svc = QualityGovernanceService(session)
        with pytest.raises(ValueError, match="resolution requires notes"):
            await svc.transition(
                incident.id, "resolved", "user", frozenset({"quality_incidents:manage"}), uuid4()
            )

    @pytest.mark.asyncio
    @patch("ia_investing.application.data_quality.create_domain_audit_entry", new_callable=AsyncMock)
    async def test_resolve_success(self, mock_audit: AsyncMock) -> None:
        mock_audit.return_value = MagicMock()
        session = AsyncMock()
        incident = MagicMock(spec=QualityIncident)
        incident.id = uuid4()
        incident.status = "open"
        incident.quality_rule_id = uuid4()
        quarantine = MagicMock(spec=QuarantineRecord)
        session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=quarantine)))
        session.get = AsyncMock(return_value=incident)
        session.flush = AsyncMock()

        svc = QualityGovernanceService(session)
        result = await svc.transition(
            incident.id, "resolved", "user", frozenset({"quality_incidents:manage"}), uuid4(),
            reason="fixed the issue",
        )
        assert result.status == "resolved"
        assert result.resolution_notes == "fixed the issue"
        assert quarantine.status == "released"

    @pytest.mark.asyncio
    async def test_waive_requires_reason_and_expiry(self) -> None:
        session = AsyncMock()
        incident = MagicMock(spec=QualityIncident)
        incident.id = uuid4()
        incident.status = "open"
        session.get = AsyncMock(return_value=incident)
        svc = QualityGovernanceService(session)
        with pytest.raises(ValueError, match="waiver requires a reason"):
            await svc.transition(
                incident.id, "waived", "user", frozenset({"quality_incidents:manage"}), uuid4(),
                reason="accepted risk",
            )

    @pytest.mark.asyncio
    async def test_waive_past_expiry_rejected(self) -> None:
        session = AsyncMock()
        incident = MagicMock(spec=QualityIncident)
        incident.id = uuid4()
        incident.status = "open"
        session.get = AsyncMock(return_value=incident)
        svc = QualityGovernanceService(session)
        with pytest.raises(ValueError, match="waiver requires a reason"):
            await svc.transition(
                incident.id, "waived", "user", frozenset({"quality_incidents:manage"}), uuid4(),
                reason="ok", waiver_expires_at=datetime(2025, 1, 1, tzinfo=UTC),
            )

    @pytest.mark.asyncio
    @patch("ia_investing.application.data_quality.create_domain_audit_entry", new_callable=AsyncMock)
    async def test_waive_success(self, mock_audit: AsyncMock) -> None:
        mock_audit.return_value = MagicMock()
        session = AsyncMock()
        incident = MagicMock(spec=QualityIncident)
        incident.id = uuid4()
        incident.status = "open"
        incident.quality_rule_id = uuid4()
        quarantine = MagicMock(spec=QuarantineRecord)
        session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=quarantine)))
        session.get = AsyncMock(return_value=incident)
        session.flush = AsyncMock()

        svc = QualityGovernanceService(session)
        future = datetime.now(UTC) + timedelta(days=30)
        result = await svc.transition(
            incident.id, "waived", "user", frozenset({"quality_incidents:manage"}), uuid4(),
            reason="accepted risk", waiver_expires_at=future,
        )
        assert result.status == "waived"
        assert result.waiver_reason == "accepted risk"
        assert result.waiver_approved_by == "user"

    @pytest.mark.asyncio
    async def test_open_clears_waiver_fields(self) -> None:
        session = AsyncMock()
        incident = MagicMock(spec=QualityIncident)
        incident.id = uuid4()
        incident.status = "waived"
        incident.quality_rule_id = uuid4()
        session.get = AsyncMock(return_value=incident)
        session.flush = AsyncMock()

        svc = QualityGovernanceService(session)
        result = await svc.transition(
            incident.id, "open", "user", frozenset({"quality_incidents:manage"}), uuid4(),
        )
        assert result.status == "open"
        assert result.waiver_reason is None
        assert result.waiver_approved_by is None
        assert result.waiver_expires_at is None

    @pytest.mark.asyncio
    @patch("ia_investing.application.data_quality.create_domain_audit_entry", new_callable=AsyncMock)
    async def test_transition_no_quarantine_to_release(self, mock_audit: AsyncMock) -> None:
        mock_audit.return_value = MagicMock()
        session = AsyncMock()
        incident = MagicMock(spec=QualityIncident)
        incident.id = uuid4()
        incident.status = "open"
        incident.quality_rule_id = uuid4()
        session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
        session.get = AsyncMock(return_value=incident)
        session.flush = AsyncMock()

        svc = QualityGovernanceService(session)
        result = await svc.transition(
            incident.id, "resolved", "user", frozenset({"quality_incidents:manage"}), uuid4(),
            reason="fixed",
        )
        assert result.status == "resolved"
