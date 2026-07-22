from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from statistics import mean
from typing import Any
from uuid import UUID

from ia_investing.domain.calibration import (
    CalibrationRecord,
    CalibrationStatus,
    ComponentName,
)


class CalibrationEngine:
    def __init__(self) -> None:
        self._records: dict[UUID, CalibrationRecord] = {}
        self._component_records: dict[ComponentName, list[UUID]] = defaultdict(list)

    def record_prediction(
        self,
        component: ComponentName | str,
        inputs: dict[str, Any],
        output: dict[str, Any],
        confidence: float,
        tags: list[str] | None = None,
    ) -> CalibrationRecord:
        component = ComponentName(component)
        inputs_hash = hashlib.sha256(json.dumps(inputs, sort_keys=True).encode()).hexdigest()
        record = CalibrationRecord(
            component=component,
            inputs_hash=inputs_hash,
            output_summary=output,
            confidence_score=confidence,
            tags=tags or [],
        )
        self._records[record.id] = record
        self._component_records[component].append(record.id)
        return record

    def record_outcome(
        self,
        record_id: UUID,
        ground_truth: dict[str, Any],
        is_synthetic: bool = False,
    ) -> CalibrationRecord | None:
        record = self._records.get(record_id)
        if record is None:
            return None
        updated = record.model_copy(
            update={
                "ground_truth": ground_truth,
                "is_synthetic": is_synthetic,
                "calibration_status": CalibrationStatus.CALIBRATED,
                "last_calibrated_at": datetime.now(UTC),
            }
        )
        self._records[record_id] = updated
        self._update_drift(record_id)
        return updated

    def _update_drift(self, record_id: UUID) -> None:
        record = self._records.get(record_id)
        if record is None or record.ground_truth is None:
            return
        truth = record.ground_truth
        diffs: list[float] = []
        for key, actual in truth.items():
            if isinstance(actual, (int, float)) and key in record.output_summary:
                predicted = record.output_summary[key]
                if isinstance(predicted, (int, float)):
                    diffs.append(abs(float(predicted) - float(actual)))
        drift = mean(diffs) if diffs else 0.0
        self._records[record_id] = record.model_copy(update={"drift_score": drift})

    def _component_calibrated_records(self, component: ComponentName) -> list[CalibrationRecord]:
        return [
            self._records[rid]
            for rid in self._component_records.get(component, [])
            if rid in self._records and self._records[rid].ground_truth is not None
        ]

    def calculate_calibration_score(self, component: ComponentName | str) -> dict[str, Any]:
        component = ComponentName(component)
        records = self._component_calibrated_records(component)
        if not records:
            return {"brier_score": None, "n_records": 0}

        scores: list[float] = []
        for r in records:
            f = r.confidence_score
            o = 1.0 if self._outcome_positive(r.ground_truth) else 0.0
            scores.append((f - o) ** 2)
        brier = mean(scores)

        return {
            "brier_score": round(brier, 6),
            "n_records": len(records),
            "component": component,
        }

    @staticmethod
    def _outcome_positive(ground_truth: dict[str, Any] | None) -> bool:
        if ground_truth is None:
            return False
        for v in ground_truth.values():
            if isinstance(v, bool):
                return v
            if isinstance(v, str) and v.lower() in {"true", "yes", "passed", "success"}:
                return True
            if isinstance(v, str) and v.lower() in {"false", "no", "failed"}:
                return False
        return False

    def detect_drift(
        self,
        component: ComponentName | str,
        window_days: int = 30,
    ) -> dict[str, Any]:
        component = ComponentName(component)
        records = self._component_calibrated_records(component)
        cutoff = datetime.now(UTC) - timedelta(days=window_days)

        recent = [r for r in records if r.last_calibrated_at >= cutoff]
        historical = [r for r in records if r.last_calibrated_at < cutoff]

        if not recent or not historical:
            return {
                "drift_detected": False,
                "recent_brier": None,
                "historical_brier": None,
                "n_recent": len(recent),
                "n_historical": len(historical),
                "component": component,
            }

        def _brier(rs: list[CalibrationRecord]) -> float:
            vals: list[float] = []
            for r in rs:
                f = r.confidence_score
                o = 1.0 if self._outcome_positive(r.ground_truth) else 0.0
                vals.append((f - o) ** 2)
            return mean(vals)

        recent_brier = _brier(recent)
        historical_brier = _brier(historical)
        drift_detected = recent_brier > historical_brier * 1.5

        return {
            "drift_detected": drift_detected,
            "recent_brier": round(recent_brier, 6),
            "historical_brier": round(historical_brier, 6),
            "n_recent": len(recent),
            "n_historical": len(historical),
            "component": component,
        }

    def get_uncalibrated_components(self) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for component in ComponentName:
            records = self._component_calibrated_records(component)
            if len(records) < 100:
                result.append(
                    {
                        "component": component,
                        "n_records": len(records),
                        "needs_calibration": True,
                    }
                )
        return result

    def generate_reliability_data(self, component: ComponentName | str) -> list[dict[str, Any]]:
        component = ComponentName(component)
        records = self._component_calibrated_records(component)
        bins: dict[str, list[float]] = defaultdict(list)

        for r in records:
            confidence = round(r.confidence_score, 1)
            bin_key = f"{confidence:.1f}"
            outcome = 1.0 if self._outcome_positive(r.ground_truth) else 0.0
            bins[bin_key].append(outcome)

        reliability: list[dict[str, Any]] = []
        for bin_key in sorted(bins.keys(), key=float):
            outcomes = bins[bin_key]
            reliability.append(
                {
                    "confidence_bin": float(bin_key),
                    "n_samples": len(outcomes),
                    "actual_frequency": round(mean(outcomes), 4),
                }
            )
        return reliability

    def get_calibration_summary(self) -> dict[str, Any]:
        summary: dict[str, Any] = {}
        for component in ComponentName:
            score = self.calculate_calibration_score(component)
            drift = self.detect_drift(component)
            records = self._component_calibrated_records(component)
            summary[component] = {
                "brier_score": score["brier_score"],
                "n_records": score["n_records"],
                "drift_detected": drift.get("drift_detected", False),
                "calibrated_count": len(records),
            }
        return summary
