from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from ia_investing.application.calibration_engine import CalibrationEngine
from ia_investing.application.production_gate import (
    CalibrationGateError,
    GateOverrideLog,
    ProductionGate,
)
from ia_investing.domain.calibration import CalibrationRecord, ComponentName
from tests.fixtures.golden_ai_vectors import load_ai_test_vector


def test_brier_score_perfect_calibration():
    engine = CalibrationEngine()
    for _ in range(10):
        rec = engine.record_prediction(
            component="portfolio_ranking",
            inputs={"test": True},
            output={"score": 1.0},
            confidence=1.0,
        )
        engine.record_outcome(rec.id, {"positive": True}, is_synthetic=True)
    for _ in range(10):
        rec = engine.record_prediction(
            component="portfolio_ranking",
            inputs={"test": False},
            output={"score": 0.0},
            confidence=0.0,
        )
        engine.record_outcome(rec.id, {"positive": False}, is_synthetic=True)

    score = engine.calculate_calibration_score("portfolio_ranking")
    assert score["brier_score"] == 0.0
    assert score["n_records"] == 20


def test_brier_score_imperfect():
    engine = CalibrationEngine()
    rec = engine.record_prediction(
        component="thesis_analysis",
        inputs={"ticker": "PETR4"},
        output={"score": 0.9},
        confidence=0.9,
    )
    engine.record_outcome(rec.id, {"positive": False}, is_synthetic=True)

    score = engine.calculate_calibration_score("thesis_analysis")
    assert score["brier_score"] == pytest.approx(0.81)
    assert score["n_records"] == 1


def test_brier_score_uses_golden_vectors():
    engine = CalibrationEngine()
    vector = load_ai_test_vector("thesis_analysis")
    assert vector is not None

    rec = engine.record_prediction(
        component="thesis_analysis",
        inputs={"expected_input_pattern": vector.expected_input_pattern},
        output={
            "conviction_score": vector.expected_parsed_output["conviction_score"],
            "recommendation": vector.expected_parsed_output["recommendation"],
        },
        confidence=vector.expected_parsed_output["conviction_score"],
    )
    engine.record_outcome(rec.id, {"positive": True}, is_synthetic=True)

    calc = engine.calculate_calibration_score("thesis_analysis")
    assert calc["n_records"] == 1
    expected_brier = (0.85 - 1.0) ** 2
    assert calc["brier_score"] == pytest.approx(expected_brier)


def test_drift_detection_no_drift():
    engine = CalibrationEngine()
    for i in range(60):
        rec = engine.record_prediction(
            component="risk_assessment",
            inputs={"seq": i},
            output={"risk": 0.3},
            confidence=0.7,
        )
        calibrated_at = datetime.now(UTC) - timedelta(days=60 - i)
        record = engine._records[rec.id]
        engine._records[rec.id] = record.model_copy(update={"last_calibrated_at": calibrated_at})
        engine.record_outcome(rec.id, {"positive": True}, is_synthetic=True)

    drift = engine.detect_drift("risk_assessment", window_days=30)
    assert drift["drift_detected"] is False


def test_drift_detection_drift_present():
    engine = CalibrationEngine()
    now = datetime.now(UTC)
    for i in range(30):
        rec = engine.record_prediction(
            component="market_prediction",
            inputs={"seq": i},
            output={"pred": 0.8},
            confidence=0.8,
        )
        engine.record_outcome(rec.id, {"positive": True}, is_synthetic=True)
        calibrated_at = now - timedelta(days=60 - i)
        engine._records[rec.id] = engine._records[rec.id].model_copy(update={"last_calibrated_at": calibrated_at})

    for i in range(20):
        rec = engine.record_prediction(
            component="market_prediction",
            inputs={"seq": 100 + i},
            output={"pred": 0.9},
            confidence=0.9,
        )
        engine.record_outcome(rec.id, {"positive": False}, is_synthetic=True)
        calibrated_at = now - timedelta(hours=i)
        engine._records[rec.id] = engine._records[rec.id].model_copy(update={"last_calibrated_at": calibrated_at})

    drift = engine.detect_drift("market_prediction", window_days=30)
    assert drift["drift_detected"] is True
    assert drift["recent_brier"] > drift["historical_brier"]


def test_production_gate_blocks_insufficient_records():
    engine = CalibrationEngine()
    gate = ProductionGate(engine)

    with pytest.raises(CalibrationGateError, match="insufficient_records"):
        gate.require_calibration("portfolio_ranking", min_records=100)

    for _ in range(100):
        rec = engine.record_prediction(
            component="portfolio_ranking",
            inputs={"x": 1},
            output={"score": 0.5},
            confidence=0.5,
        )
        engine.record_outcome(rec.id, {"positive": True}, is_synthetic=True)

    gate.require_calibration("portfolio_ranking", min_records=100, max_brier_score=0.25)


def test_production_gate_blocks_high_brier():
    engine = CalibrationEngine()
    gate = ProductionGate(engine)

    rec = engine.record_prediction(
        component="thesis_analysis",
        inputs={"ticker": "PETR4"},
        output={"score": 0.9},
        confidence=0.9,
    )
    engine.record_outcome(rec.id, {"positive": False}, is_synthetic=True)

    with pytest.raises(CalibrationGateError, match="brier_score_too_high"):
        gate.require_calibration("thesis_analysis", min_records=1, max_brier_score=0.2)


def test_gate_override_flow():
    engine = CalibrationEngine()
    gate = ProductionGate(engine)

    with pytest.raises(CalibrationGateError):
        gate.require_calibration("portfolio_ranking", min_records=100)

    override = gate.override_gate(
        "portfolio_ranking",
        reason="emergency_deploy",
        duration_hours=24,
        requested_by="admin",
    )

    assert override.component == "portfolio_ranking"
    assert override.reason == "emergency_deploy"
    assert override.requested_by == "admin"

    gate.require_calibration("portfolio_ranking", min_records=100)

    status = gate.get_gate_status()
    assert status["portfolio_ranking"]["overridden"] is True


def test_override_log_append_only():
    log = GateOverrideLog()
    from ia_investing.application.production_gate import GateOverride

    override1 = GateOverride(
        id=UUID("00000000-0000-0000-0000-000000000001"),
        component="risk_assessment",
        reason="test",
        requested_by="admin",
        created_at=datetime.now(UTC),
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    log.append(override1)
    assert len(log.all()) == 1

    override2 = GateOverride(
        id=UUID("00000000-0000-0000-0000-000000000002"),
        component="market_prediction",
        reason="test2",
        requested_by="admin",
        created_at=datetime.now(UTC),
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    log.append(override2)
    assert len(log.all()) == 2


def test_reliability_data():
    engine = CalibrationEngine()
    for conf in [0.1, 0.3, 0.5, 0.7, 0.9]:
        for _ in range(5):
            rec = engine.record_prediction(
                component="risk_assessment",
                inputs={"test": True},
                output={"risk": conf},
                confidence=conf,
            )
            outcome = conf >= 0.5
            engine.record_outcome(rec.id, {"positive": outcome}, is_synthetic=True)

    reliability = engine.generate_reliability_data("risk_assessment")
    assert len(reliability) == 5
    for entry in reliability:
        assert entry["n_samples"] == 5
        if entry["confidence_bin"] >= 0.5:
            assert entry["actual_frequency"] >= 0.5


def test_calibration_summary_covers_all_components():
    engine = CalibrationEngine()
    for _ in range(10):
        rec = engine.record_prediction(
            component="political_intelligence",
            inputs={"test": True},
            output={"score": 0.5},
            confidence=0.5,
        )
        engine.record_outcome(rec.id, {"positive": True}, is_synthetic=True)

    summary = engine.get_calibration_summary()
    for component in ComponentName:
        assert component in summary
    assert summary["political_intelligence"]["n_records"] == 10


def test_get_uncalibrated_components():
    engine = CalibrationEngine()
    for _ in range(150):
        rec = engine.record_prediction(
            component="portfolio_ranking",
            inputs={"test": True},
            output={"score": 0.5},
            confidence=0.5,
        )
        engine.record_outcome(rec.id, {"positive": True}, is_synthetic=True)

    uncalibrated = engine.get_uncalibrated_components()
    portfolio_status = [u for u in uncalibrated if u["component"] == "portfolio_ranking"]
    assert len(portfolio_status) == 0 or portfolio_status[0]["needs_calibration"] is False


def test_gate_status_matrix():
    engine = CalibrationEngine()
    gate = ProductionGate(engine)

    status = gate.get_gate_status()
    for component in ComponentName:
        assert str(component) in status

    gate.override_gate("political_intelligence", "maintenance", requested_by="ops")
    status = gate.get_gate_status()
    assert status["political_intelligence"]["overridden"] is True


def test_record_outcome_nonexistent():
    engine = CalibrationEngine()
    result = engine.record_outcome(UUID(int=0), {"positive": True})
    assert result is None


def test_calibration_record_model():
    record = CalibrationRecord(
        component=ComponentName.PORTFOLIO_RANKING,
        inputs_hash="a" * 64,
        output_summary={"score": 0.85},
        confidence_score=0.85,
    )
    assert record.component == ComponentName.PORTFOLIO_RANKING
    assert record.calibration_status.value == "pending"
    assert record.drift_score is None
    assert record.calibration_window == 30
    assert record.is_synthetic is False
