"""Unit tests for QualityGovernanceService and helpers (data_quality.py)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from database.models.data_governance import QualityIncident, QualityRule, QuarantineRecord
from data_quality._models import ValidationResult
from ia_investing.application.data_quality import (
    ALLOWED_TRANSITIONS,
    QualityGateResult,
    QualityGovernanceService,
    validate_transition,
)
from ia_investing.application.audit_service import create_domain_audit_entry


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
