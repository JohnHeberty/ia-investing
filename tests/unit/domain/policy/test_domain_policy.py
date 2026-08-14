"""Unit tests for ia_investing.domain.policy — core policy domain logic."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from ia_investing.domain.policy import (
    HistoricalOutcome,
    ImpactEdge,
    PolicyDeadline,
    PolicyTheme,
    base_rate,
    brier_score,
    canonical_policy_key,
    compute_versioned_features,
    detect_rectification,
    features_hash,
    material_review_required,
    propagate_impact,
    text_diff,
    validate_policy_stage_transition,
)

# ── canonical_policy_key ─────────────────────────────────────────────────────


@pytest.mark.unit
class TestCanonicalPolicyKey:
    def test_deterministic(self) -> None:
        assert canonical_policy_key("Camara", "PL", "123") == canonical_policy_key("camara", "PL", "123")

    def test_format_colon_separated(self) -> None:
        result = canonical_policy_key("camara", "PL", "123")
        assert result == "camara:pl:123"

    def test_different_authorities_produce_different_keys(self) -> None:
        assert canonical_policy_key("camara", "PL", "123") != canonical_policy_key("senado", "PL", "123")

    def test_different_types_produce_different_keys(self) -> None:
        assert canonical_policy_key("camara", "PL", "123") != canonical_policy_key("camara", "PEC", "123")

    def test_different_ids_produce_different_keys(self) -> None:
        assert canonical_policy_key("camara", "PL", "123") != canonical_policy_key("camara", "PL", "456")

    def test_strips_whitespace(self) -> None:
        assert canonical_policy_key("  camara  ", "  PL  ", "  123  ") == "camara:pl:123"

    def test_empty_authority_raises(self) -> None:
        with pytest.raises(ValueError, match="policy identity requires"):
            canonical_policy_key("", "PL", "123")

    def test_empty_type_raises(self) -> None:
        with pytest.raises(ValueError, match="policy identity requires"):
            canonical_policy_key("camara", "", "123")

    def test_empty_id_raises(self) -> None:
        with pytest.raises(ValueError, match="policy identity requires"):
            canonical_policy_key("camara", "PL", "")

    def test_whitespace_only_raises(self) -> None:
        with pytest.raises(ValueError, match="policy identity requires"):
            canonical_policy_key("   ", "PL", "123")


# ── validate_policy_stage_transition ──────────────────────────────────────────


@pytest.mark.unit
class TestValidatePolicyStageTransition:
    def test_valid_generic_transition(self) -> None:
        validate_policy_stage_transition("discovered", "introduced")

    def test_invalid_generic_transition(self) -> None:
        with pytest.raises(ValueError, match="invalid"):
            validate_policy_stage_transition("introduced", "published")

    def test_terminal_state_no_transitions(self) -> None:
        with pytest.raises(ValueError, match="invalid"):
            validate_policy_stage_transition("withdrawn", "introduced")

    def test_projeto_lei_valid_lifecycle(self) -> None:
        transitions = [
            ("discovered", "introduced"),
            ("introduced", "committee"),
            ("committee", "floor"),
            ("floor", "other_house"),
            ("other_house", "approved"),
            ("approved", "sanction"),
            ("sanction", "published"),
        ]
        for current, target in transitions:
            validate_policy_stage_transition(current, target, "projeto_lei")

    def test_decreto_bypasses_legislative(self) -> None:
        validate_policy_stage_transition("discovered", "published", "decreto")
        with pytest.raises(ValueError, match="invalid"):
            validate_policy_stage_transition("discovered", "introduced", "decreto")

    def test_normativo_suspension_path(self) -> None:
        validate_policy_stage_transition("published", "suspended", "normativo")
        validate_policy_stage_transition("suspended", "regulated", "normativo")

    def test_ato_oficial_simple(self) -> None:
        validate_policy_stage_transition("published", "corrected", "ato_oficial")
        validate_policy_stage_transition("published", "revoked", "ato_oficial")
        with pytest.raises(ValueError, match="invalid"):
            validate_policy_stage_transition("published", "regulated", "ato_oficial")

    def test_invalid_transition_for_legal_type(self) -> None:
        with pytest.raises(ValueError, match="invalid"):
            validate_policy_stage_transition("discovered", "floor", "projeto_lei")

    def test_unknown_legal_type_falls_back_to_generic(self) -> None:
        validate_policy_stage_transition("introduced", "committee")
        with pytest.raises(ValueError, match="invalid"):
            validate_policy_stage_transition("introduced", "published")


# ── text_diff ─────────────────────────────────────────────────────────────────


@pytest.mark.unit
class TestTextDiff:
    def test_identical_strings(self) -> None:
        result = text_diff("hello", "hello")
        assert result["changed"] is False
        assert result["additions"] == 0
        assert result["removals"] == 0

    def test_addition(self) -> None:
        result = text_diff("line1", "line1\nline2")
        assert result["changed"] is True
        assert int(str(result["additions"])) >= 1

    def test_removal(self) -> None:
        result = text_diff("line1\nline2", "line1")
        assert result["changed"] is True
        assert int(str(result["removals"])) >= 1

    def test_change(self) -> None:
        result = text_diff("old text", "new text")
        assert result["changed"] is True
        assert int(str(result["additions"])) == 1
        assert int(str(result["removals"])) == 1

    def test_unified_diff_structure(self) -> None:
        result = text_diff("a", "b")
        assert isinstance(result["unified"], list)
        assert any(line.startswith("@@") for line in result["unified"])


# ── base_rate ─────────────────────────────────────────────────────────────────


@pytest.mark.unit
class TestBaseRate:
    def _outcome(self, policy_type: str, stage: str, outcome: bool, days_ago: int) -> HistoricalOutcome:
        now = datetime(2026, 1, 1, tzinfo=UTC)
        return HistoricalOutcome(
            policy_type=policy_type,
            stage=stage,
            predicted_at=now - timedelta(days=days_ago + 10),
            outcome_at=now - timedelta(days=days_ago),
            outcome=outcome,
        )

    def test_zero_samples_jeffreys_prior(self) -> None:
        estimate = base_rate(
            (),
            policy_type="bill",
            stage="committee",
            knowledge_cutoff=datetime(2026, 1, 1, tzinfo=UTC),
        )
        assert estimate.sample_size == 0
        assert estimate.probability == Decimal("0.5")

    def test_all_successes(self) -> None:
        outcomes = tuple(self._outcome("bill", "floor", True, i) for i in range(10))
        estimate = base_rate(outcomes, policy_type="bill", stage="floor", knowledge_cutoff=datetime(2026, 1, 1, tzinfo=UTC))
        assert estimate.sample_size == 10
        assert estimate.probability > Decimal("0.9")

    def test_all_failures(self) -> None:
        outcomes = tuple(self._outcome("bill", "floor", False, i) for i in range(10))
        estimate = base_rate(outcomes, policy_type="bill", stage="floor", knowledge_cutoff=datetime(2026, 1, 1, tzinfo=UTC))
        assert estimate.sample_size == 10
        assert estimate.probability < Decimal("0.1")

    def test_filters_by_cutoff(self) -> None:
        included = self._outcome("bill", "committee", True, 5)
        excluded = HistoricalOutcome(
            "bill", "committee",
            datetime(2026, 1, 1, tzinfo=UTC),
            datetime(2026, 12, 31, tzinfo=UTC),
            True,
        )
        estimate = base_rate(
            (included, excluded),
            policy_type="bill",
            stage="committee",
            knowledge_cutoff=datetime(2026, 1, 1, tzinfo=UTC),
        )
        assert estimate.sample_size == 1

    def test_filters_by_type_and_stage(self) -> None:
        matching = self._outcome("bill", "committee", True, 5)
        wrong_type = self._outcome("decret", "committee", True, 5)
        wrong_stage = self._outcome("bill", "floor", True, 5)
        estimate = base_rate(
            (matching, wrong_type, wrong_stage),
            policy_type="bill",
            stage="committee",
            knowledge_cutoff=datetime(2026, 1, 1, tzinfo=UTC),
        )
        assert estimate.sample_size == 1

    def test_interval_bounded(self) -> None:
        outcomes = tuple(self._outcome("bill", "floor", bool(i % 2), i) for i in range(20))
        estimate = base_rate(outcomes, policy_type="bill", stage="floor", knowledge_cutoff=datetime(2026, 1, 1, tzinfo=UTC))
        assert Decimal(0) <= estimate.interval_low <= estimate.probability <= estimate.interval_high <= Decimal(1)

    def test_wilson_assumptions_metadata(self) -> None:
        estimate = base_rate((), policy_type="x", stage="y", knowledge_cutoff=datetime(2026, 1, 1, tzinfo=UTC))
        assert any("Wilson" in a for a in estimate.assumptions)


# ── brier_score ───────────────────────────────────────────────────────────────


@pytest.mark.unit
class TestBrierScore:
    def test_perfect_forecasts(self) -> None:
        forecasts = ((Decimal("1.0"), True), (Decimal("0.0"), False))
        assert brier_score(forecasts) == Decimal("0")

    def test_worst_case(self) -> None:
        forecasts = ((Decimal("0.0"), True), (Decimal("1.0"), False))
        assert brier_score(forecasts) == Decimal("1")

    def test_intermediate(self) -> None:
        forecasts = ((Decimal("0.8"), True), (Decimal("0.3"), False))
        score = brier_score(forecasts)
        assert Decimal(0) < score < Decimal("0.5")

    def test_empty_raises(self) -> None:
        with pytest.raises(ValueError, match="at least one"):
            brier_score(())

    def test_single_forecast(self) -> None:
        assert brier_score(((Decimal("0.5"), True),)) == Decimal("0.25")


# ── propagate_impact ──────────────────────────────────────────────────────────


@pytest.mark.unit
class TestPropagateImpact:
    def test_linear_chain(self) -> None:
        edges = (
            ImpactEdge("a", "b", "rel", Decimal("0.5"), Decimal("1")),
            ImpactEdge("b", "c", "rel", Decimal("0.5"), Decimal("1")),
        )
        results = propagate_impact("a", Decimal(1), edges)
        assert len(results) == 2
        assert results[0].impact == Decimal("0.5")
        assert results[1].impact == Decimal("0.25")

    def test_diamond_graph(self) -> None:
        edges = (
            ImpactEdge("root", "left", "r", Decimal("1"), Decimal("1")),
            ImpactEdge("root", "right", "r", Decimal("1"), Decimal("1")),
            ImpactEdge("left", "shared", "r", Decimal("0.5"), Decimal("1")),
            ImpactEdge("right", "shared", "r", Decimal("0.5"), Decimal("1")),
        )
        results = propagate_impact("root", Decimal(1), edges)
        targets = [r.node for r in results]
        assert targets.count("shared") == 2

    def test_cycle_detected(self) -> None:
        edges = (
            ImpactEdge("a", "b", "r", Decimal("1"), Decimal("1")),
            ImpactEdge("b", "a", "r", Decimal("1"), Decimal("1")),
        )
        with pytest.raises(ValueError, match="cycle"):
            propagate_impact("a", Decimal(1), edges)

    def test_zero_confidence(self) -> None:
        edges = (ImpactEdge("a", "b", "r", Decimal("1"), Decimal(0)),)
        results = propagate_impact("a", Decimal(1), edges)
        assert results[0].impact == Decimal("0")

    def test_full_confidence_preserves_weight(self) -> None:
        edges = (ImpactEdge("a", "b", "r", Decimal("0.7"), Decimal(1)),)
        results = propagate_impact("a", Decimal(1), edges)
        assert results[0].impact == Decimal("0.7")

    def test_non_approved_edges_ignored(self) -> None:
        edges = (ImpactEdge("a", "b", "r", Decimal("1"), Decimal("1"), status="pending"),)
        results = propagate_impact("a", Decimal(1), edges)
        assert results == ()

    def test_confidence_out_of_range_raises(self) -> None:
        edges = (ImpactEdge("a", "b", "r", Decimal("1"), Decimal("1.5")),)
        with pytest.raises(ValueError, match="confidence"):
            propagate_impact("a", Decimal(1), edges)

    def test_path_tracking(self) -> None:
        edges = (
            ImpactEdge("a", "b", "r", Decimal("1"), Decimal("1")),
            ImpactEdge("b", "c", "r", Decimal("1"), Decimal("1")),
        )
        results = propagate_impact("a", Decimal(1), edges)
        assert results[1].path == ("a", "b", "c")


# ── material_review_required ──────────────────────────────────────────────────


@pytest.mark.unit
class TestMaterialReviewRequired:
    def test_above_threshold(self) -> None:
        assert material_review_required(
            materiality=Decimal("0.9"), exposure=Decimal("0.8"),
            corroboration=Decimal("0.9"), freshness=Decimal("1"),
        )

    def test_below_threshold(self) -> None:
        assert not material_review_required(
            materiality=Decimal("0.1"), exposure=Decimal("0.1"),
            corroboration=Decimal("0.1"), freshness=Decimal("0.1"),
        )

    def test_exact_threshold(self) -> None:
        assert material_review_required(
            materiality=Decimal("1"), exposure=Decimal("0.5"),
            corroboration=Decimal("0.5"), freshness=Decimal("0.8"),
            threshold=Decimal("0.20"),
        )

    def test_zero_materiality(self) -> None:
        assert not material_review_required(
            materiality=Decimal(0), exposure=Decimal("1"),
            corroboration=Decimal("1"), freshness=Decimal("1"),
        )

    def test_custom_threshold(self) -> None:
        assert material_review_required(
            materiality=Decimal("0.5"), exposure=Decimal("0.5"),
            corroboration=Decimal("0.5"), freshness=Decimal("0.5"),
            threshold=Decimal("0.05"),
        )

    def test_out_of_range_raises(self) -> None:
        with pytest.raises(ValueError, match="between zero and one"):
            material_review_required(
                materiality=Decimal("1.5"), exposure=Decimal("0.5"),
                corroboration=Decimal("0.5"), freshness=Decimal("0.5"),
            )


# ── detect_rectification ──────────────────────────────────────────────────────


@pytest.mark.unit
class TestDetectRectification:
    def test_no_change_returns_none(self) -> None:
        assert detect_rectification("text", "text", rectification_type="amendment") is None

    def test_amendment_detected(self) -> None:
        result = detect_rectification("Art. 1 old", "Art. 1 new", rectification_type="amendment")
        assert result is not None
        assert result["rectification_type"] == "amendment"
        assert int(str(result["additions"])) >= 1
        assert int(str(result["removals"])) >= 1

    def test_rectification_type_preserved(self) -> None:
        for rtype in ("amendment", "rectification", "revocation", "veto_partial", "suspension"):
            result = detect_rectification("old", "new", rectification_type=rtype)
            assert result is not None
            assert result["rectification_type"] == rtype

    def test_content_sha256_is_hex(self) -> None:
        result = detect_rectification("a", "b", rectification_type="amendment")
        assert result is not None
        sha = str(result["content_sha256"])
        assert len(sha) == 64
        int(sha, 16)  # raises if not hex

    def test_full_removal(self) -> None:
        result = detect_rectification("content", "", rectification_type="revocation")
        assert result is not None
        assert int(str(result["removals"])) >= 1
        assert int(str(result["additions"])) == 0


# ── compute_versioned_features ────────────────────────────────────────────────


@pytest.mark.unit
class TestComputeVersionedFeatures:
    def test_basic_features(self) -> None:
        now = datetime.now(UTC)
        features = compute_versioned_features(
            stage="committee",
            legal_type="projeto_lei",
            themes=(PolicyTheme("tributaria", ("financeiro",), Decimal("0.8"), Decimal("0.9")),),
            deadlines=(PolicyDeadline("vote", now + timedelta(days=15), "Vote"),),
            base_rate=Decimal("0.35"),
            corroboration_count=3,
            materiality=Decimal("0.7"),
        )
        assert features["stage"] == "committee"
        assert features["theme_count"] == 1
        assert features["deadline_count"] == 1

    def test_empty_themes_and_deadlines(self) -> None:
        features = compute_versioned_features(
            stage="floor", legal_type="decreto",
            themes=(), deadlines=(),
            base_rate=Decimal("0.5"), corroboration_count=0,
            materiality=Decimal("0"),
        )
        assert features["theme_count"] == 0
        assert features["deadline_count"] == 0
        assert features["nearest_deadline"] is None

    def test_sector_exposures_deduplicated(self) -> None:
        features = compute_versioned_features(
            stage="floor", legal_type="projeto_lei",
            themes=(
                PolicyTheme("a", ("fin", "retail"), Decimal("0.5"), Decimal("0.5")),
                PolicyTheme("b", ("fin",), Decimal("0.5"), Decimal("0.5")),
            ),
            deadlines=(), base_rate=Decimal("0.5"),
            corroboration_count=1, materiality=Decimal("0.5"),
        )
        assert str(features["sector_exposures"]).count("fin") == 1

    def test_features_hash_deterministic(self) -> None:
        features = compute_versioned_features(
            stage="x", legal_type="y",
            themes=(), deadlines=(),
            base_rate=Decimal("0"), corroboration_count=0,
            materiality=Decimal("0"),
        )
        assert features_hash(features) == features_hash(features)

    def test_features_hash_changes_with_different_data(self) -> None:
        f1 = compute_versioned_features(
            stage="a", legal_type="b",
            themes=(), deadlines=(),
            base_rate=Decimal("0"), corroboration_count=0,
            materiality=Decimal("0"),
        )
        f2 = compute_versioned_features(
            stage="x", legal_type="y",
            themes=(), deadlines=(),
            base_rate=Decimal("0"), corroboration_count=0,
            materiality=Decimal("0"),
        )
        assert features_hash(f1) != features_hash(f2)

    def test_materiality_as_string(self) -> None:
        features = compute_versioned_features(
            stage="s", legal_type="t",
            themes=(), deadlines=(),
            base_rate=Decimal("0.123"), corroboration_count=1,
            materiality=Decimal("0.456"),
        )
        assert features["materiality"] == "0.456"
        assert features["base_rate"] == "0.123"
