"""Tests for Fase 7 — policy alerts, historical outcomes, and versioned features."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from connectors.macro import MACRO_SERIES_INVENTORY
from ia_investing.domain.policy import (
    LEGAL_TYPE_STAGE_TRANSITIONS,
    PolicyDeadline,
    PolicyTheme,
    RectificationRecord,
    compute_versioned_features,
    detect_rectification,
    features_hash,
    validate_policy_stage_transition,
)
from ia_investing.domain.policy_alerts import (
    DEFAULT_ALERT_RULES,
    AlertSeverity,
    AlertType,
    PolicyAlert,
    is_duplicate,
    should_fire_alert,
)
from ia_investing.domain.policy_historical import (
    HISTORICAL_OUTCOMES,
    get_historical_outcomes,
)

# ── Legal-type-specific state machines ───────────────────────────────────────


class TestLegalTypeStageTransitions:
    def test_all_four_legal_types_defined(self) -> None:
        assert set(LEGAL_TYPE_STAGE_TRANSITIONS.keys()) == {
            "projeto_lei",
            "decreto",
            "normativo",
            "ato_oficial",
        }

    def test_projeto_lei_full_lifecycle(self) -> None:
        validate_policy_stage_transition("discovered", "introduced", "projeto_lei")
        validate_policy_stage_transition("introduced", "committee", "projeto_lei")
        validate_policy_stage_transition("committee", "floor", "projeto_lei")
        validate_policy_stage_transition("floor", "other_house", "projeto_lei")
        validate_policy_stage_transition("other_house", "approved", "projeto_lei")
        validate_policy_stage_transition("approved", "sanction", "projeto_lei")
        validate_policy_stage_transition("sanction", "published", "projeto_lei")

    def test_projeto_lei_veto_path(self) -> None:
        validate_policy_stage_transition("approved", "veto", "projeto_lei")
        validate_policy_stage_transition("veto", "veto_review", "projeto_lei")
        validate_policy_stage_transition("veto_review", "published", "projeto_lei")

    def test_decreto_bypasses_legislative_stages(self) -> None:
        transitions = LEGAL_TYPE_STAGE_TRANSITIONS["decreto"]
        assert "committee" not in transitions.get("discovered", frozenset())
        assert "floor" not in transitions.get("discovered", frozenset())
        validate_policy_stage_transition("discovered", "published", "decreto")
        validate_policy_stage_transition("published", "regulated", "decreto")
        validate_policy_stage_transition("published", "revoked", "decreto")

    def test_normativo_has_suspension_state(self) -> None:
        transitions = LEGAL_TYPE_STAGE_TRANSITIONS["normativo"]
        assert "suspended" in transitions.get("published", frozenset())
        validate_policy_stage_transition("published", "suspended", "normativo")
        validate_policy_stage_transition("suspended", "regulated", "normativo")

    def test_ato_oficial_simple_lifecycle(self) -> None:
        transitions = LEGAL_TYPE_STAGE_TRANSITIONS["ato_oficial"]
        assert "regulated" not in transitions.get("published", frozenset())
        validate_policy_stage_transition("published", "corrected", "ato_oficial")
        validate_policy_stage_transition("published", "revoked", "ato_oficial")

    def test_invalid_transition_rejected_with_legal_type(self) -> None:
        with pytest.raises(ValueError, match="invalid"):
            validate_policy_stage_transition("discovered", "floor", "projeto_lei")
        with pytest.raises(ValueError, match="invalid"):
            validate_policy_stage_transition("discovered", "committee", "decreto")

    def test_unknown_legal_type_falls_back_to_generic(self) -> None:
        validate_policy_stage_transition("introduced", "committee")
        with pytest.raises(ValueError, match="invalid"):
            validate_policy_stage_transition("introduced", "published")


# ── Rectification tracking ───────────────────────────────────────────────────


class TestRectification:
    def test_detect_rectification_returns_none_for_identical_text(self) -> None:
        result = detect_rectification("text", "text", rectification_type="amendment")
        assert result is None

    def test_detect_rectification_captures_diff(self) -> None:
        result = detect_rectification(
            "Art. 1 texto original",
            "Art. 1 texto alterado",
            rectification_type="amendment",
        )
        assert result is not None
        assert result["rectification_type"] == "amendment"
        assert result["additions"] == 1
        assert result["removals"] == 1
        assert len(result["content_sha256"]) == 64

    def test_rectification_record_validates_type(self) -> None:
        now = datetime.now(UTC)
        record = RectificationRecord(
            original_action_id="orig-1",
            rectifying_action_id="rect-1",
            rectification_type="amendment",
            content_sha256="a" * 64,
            knowledge_at=now,
        )
        assert record.rectification_type == "amendment"

    def test_rectification_record_rejects_unknown_type(self) -> None:
        now = datetime.now(UTC)
        with pytest.raises(ValueError, match="unknown rectification type"):
            RectificationRecord(
                original_action_id="orig-1",
                rectifying_action_id="rect-1",
                rectification_type="unknown_type",
                content_sha256="a" * 64,
                knowledge_at=now,
            )

    @pytest.mark.parametrize(
        "rect_type",
        ["amendment", "rectification", "revocation", "veto_partial", "suspension"],
    )
    def test_all_valid_rectification_types(self, rect_type: str) -> None:
        now = datetime.now(UTC)
        record = RectificationRecord(
            original_action_id="o",
            rectifying_action_id="r",
            rectification_type=rect_type,
            content_sha256="b" * 64,
            knowledge_at=now,
        )
        assert record.rectification_type == rect_type


# ── Policy themes and deadlines ──────────────────────────────────────────────


class TestPolicyThemesAndDeadlines:
    def test_theme_creation(self) -> None:
        theme = PolicyTheme(
            theme="tributaria",
            sector_exposures=("financeiro", "varejo"),
            weight=Decimal("0.8"),
            confidence=Decimal("0.9"),
        )
        assert theme.theme == "tributaria"
        assert len(theme.sector_exposures) == 2

    def test_deadline_creation(self) -> None:
        now = datetime.now(UTC)
        deadline = PolicyDeadline(
            deadline_type="committee_vote",
            due_date=now + timedelta(days=30),
            description="Votação na comissão especial",
        )
        assert deadline.deadline_type == "committee_vote"
        assert not deadline.is_extended

    def test_deadline_extension(self) -> None:
        now = datetime.now(UTC)
        deadline = PolicyDeadline(
            deadline_type="committee_vote",
            due_date=now + timedelta(days=30),
            description="Votação adiada",
            is_extended=True,
            extension_date=now + timedelta(days=60),
        )
        assert deadline.is_extended
        assert deadline.extension_date is not None


# ── Versioned features computation ───────────────────────────────────────────


class TestVersionedFeatures:
    def test_compute_features_basic(self) -> None:
        now = datetime.now(UTC)
        features = compute_versioned_features(
            stage="committee",
            legal_type="projeto_lei",
            themes=(PolicyTheme("tributaria", ("financeiro",), Decimal("0.8"), Decimal("0.9")),),
            deadlines=(PolicyDeadline("committee_vote", now + timedelta(days=15), "Prazo comissão"),),
            base_rate=Decimal("0.35"),
            corroboration_count=3,
            materiality=Decimal("0.7"),
        )
        assert features["stage"] == "committee"
        assert features["legal_type"] == "projeto_lei"
        assert features["theme_count"] == 1
        assert features["deadline_count"] == 1
        assert features["base_rate"] == "0.35"
        assert features["corroboration_count"] == 3
        assert features["materiality"] == "0.7"

    def test_features_hash_deterministic(self) -> None:
        features = compute_versioned_features(
            stage="floor",
            legal_type="decreto",
            themes=(),
            deadlines=(),
            base_rate=Decimal("0.50"),
            corroboration_count=2,
            materiality=Decimal("0.6"),
        )
        h1 = features_hash(features)
        h2 = features_hash(features)
        assert h1 == h2
        assert len(h1) == 64

    def test_features_hash_changes_with_different_features(self) -> None:
        f1 = compute_versioned_features(
            stage="committee",
            legal_type="projeto_lei",
            themes=(),
            deadlines=(),
            base_rate=Decimal("0.3"),
            corroboration_count=1,
            materiality=Decimal("0.5"),
        )
        f2 = compute_versioned_features(
            stage="floor",
            legal_type="projeto_lei",
            themes=(),
            deadlines=(),
            base_rate=Decimal("0.3"),
            corroboration_count=1,
            materiality=Decimal("0.5"),
        )
        assert features_hash(f1) != features_hash(f2)


# ── Alert rules ──────────────────────────────────────────────────────────────


class TestAlertRules:
    def test_default_rules_defined(self) -> None:
        assert len(DEFAULT_ALERT_RULES) == 6
        types = {r.alert_type for r in DEFAULT_ALERT_RULES}
        assert AlertType.STAGE_CHANGED in types
        assert AlertType.MATERIAL_IMPACT in types
        assert AlertType.PROBABILITY_SHIFT in types

    def test_should_fire_material_impact_above_threshold(self) -> None:
        rule = DEFAULT_ALERT_RULES[1]  # MATERIAL_IMPACT
        assert should_fire_alert(rule, current_value=Decimal("0.25"))
        assert not should_fire_alert(rule, current_value=Decimal("0.10"))

    def test_should_fire_probability_shift(self) -> None:
        rule = DEFAULT_ALERT_RULES[2]  # PROBABILITY_SHIFT
        assert should_fire_alert(rule, current_value=Decimal("0.50"), previous_value=Decimal("0.30"))
        assert not should_fire_alert(rule, current_value=Decimal("0.50"), previous_value=Decimal("0.45"))

    def test_disabled_rule_never_fires(self) -> None:
        from ia_investing.domain.policy_alerts import AlertRule

        rule = AlertRule(
            alert_type=AlertType.STAGE_CHANGED,
            severity=AlertSeverity.INFO,
            threshold=Decimal("0"),
            description="disabled",
            enabled=False,
        )
        assert not should_fire_alert(rule, current_value=Decimal("0"))


# ── Alert deduplication ─────────────────────────────────────────────────────


class TestAlertDeduplication:
    def test_no_duplicate_when_no_existing_alerts(self) -> None:
        new = PolicyAlert(
            alert_type=AlertType.STAGE_CHANGED,
            policy_object_id=None,
            created_at=datetime.now(UTC),
        )
        assert not is_duplicate([], new)

    def test_duplicate_detected_within_window(self) -> None:
        now = datetime.now(UTC)
        existing = PolicyAlert(
            alert_type=AlertType.STAGE_CHANGED,
            policy_object_id=None,
            created_at=now,
        )
        new = PolicyAlert(
            alert_type=AlertType.STAGE_CHANGED,
            policy_object_id=None,
            created_at=now + timedelta(minutes=30),
        )
        assert is_duplicate([existing], new, window_seconds=3600)

    def test_no_duplicate_after_window_expires(self) -> None:
        now = datetime.now(UTC)
        existing = PolicyAlert(
            alert_type=AlertType.STAGE_CHANGED,
            policy_object_id=None,
            created_at=now - timedelta(hours=2),
        )
        new = PolicyAlert(
            alert_type=AlertType.STAGE_CHANGED,
            policy_object_id=None,
            created_at=now,
        )
        assert not is_duplicate([existing], new, window_seconds=3600)

    def test_resolved_alert_not_counted_as_duplicate(self) -> None:
        now = datetime.now(UTC)
        existing = PolicyAlert(
            alert_type=AlertType.STAGE_CHANGED,
            policy_object_id=None,
            created_at=now,
            resolved=True,
        )
        new = PolicyAlert(
            alert_type=AlertType.STAGE_CHANGED,
            policy_object_id=None,
            created_at=now + timedelta(minutes=5),
        )
        assert not is_duplicate([existing], new)


# ── Historical outcomes dataset ──────────────────────────────────────────────


class TestHistoricalOutcomes:
    def test_dataset_has_minimum_samples(self) -> None:
        outcomes = get_historical_outcomes()
        assert len(outcomes) >= 10

    def test_all_outcomes_have_required_fields(self) -> None:
        for outcome in HISTORICAL_OUTCOMES:
            assert outcome.policy_type
            assert outcome.legal_type in ("projeto_lei", "decreto", "normativo", "ato_oficial")
            assert outcome.stage
            assert outcome.source
            assert isinstance(outcome.outcome, bool)

    def test_outcomes_cover_all_legal_types(self) -> None:
        types = {o.legal_type for o in HISTORICAL_OUTCOMES}
        assert types == {"projeto_lei", "decreto", "normativo", "ato_oficial"}

    def test_outcomes_include_both_outcomes(self) -> None:
        outcomes_true = [o for o in HISTORICAL_OUTCOMES if o.outcome]
        outcomes_false = [o for o in HISTORICAL_OUTCOMES if not o.outcome]
        assert len(outcomes_true) >= 5
        assert len(outcomes_false) >= 5


# ── Macro series inventory ──────────────────────────────────────────────────


class TestMacroSeriesInventory:
    def test_inventory_has_all_series(self) -> None:
        assert "SELIC" in MACRO_SERIES_INVENTORY
        assert "IPCA" in MACRO_SERIES_INVENTORY
        assert "USD_BRL" in MACRO_SERIES_INVENTORY
        assert "FOCUS_SELIC" in MACRO_SERIES_INVENTORY
        assert "FOCUS_IPCA" in MACRO_SERIES_INVENTORY
        assert "FOCUS_USD" in MACRO_SERIES_INVENTORY

    def test_inventory_metadata_complete(self) -> None:
        for _name, meta in MACRO_SERIES_INVENTORY.items():
            assert "code" in meta
            assert "unit" in meta
            assert "frequency" in meta
            assert "source" in meta
            assert meta["frequency"] in ("daily", "monthly", "quarterly")

    def test_focus_series_have_correct_codes(self) -> None:
        assert MACRO_SERIES_INVENTORY["FOCUS_SELIC"]["code"] == 4513
        assert MACRO_SERIES_INVENTORY["FOCUS_IPCA"]["code"] == 4512
        assert MACRO_SERIES_INVENTORY["FOCUS_USD"]["code"] == 4514
