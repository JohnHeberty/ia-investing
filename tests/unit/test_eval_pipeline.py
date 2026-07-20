from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from ia_investing.ai.eval_gate import CapabilityVersion
from ia_investing.ai.eval_pipeline import ArtifactChange, EvalPipeline
from ia_investing.ai.eval_runner import EvalCaseResult, EvalRunResult
from ia_investing.ai.evals import EvalMetrics


def _same_version() -> CapabilityVersion:
    return CapabilityVersion(prompt_hash="a", schema_hash="b", model_name="gpt-4o", toolset_hash="c")


def _model_changed_version() -> CapabilityVersion:
    return CapabilityVersion(prompt_hash="a", schema_hash="b", model_name="gpt-4.1", toolset_hash="c")


def _make_eval_result(capability: str = "filing") -> EvalRunResult:
    return EvalRunResult(
        dataset_version=1,
        capability=capability,
        case_results=[
            EvalCaseResult("k1", capability, True, 1, 1, 1.0, False, 0.01, 100),
        ],
        aggregate_metrics=EvalMetrics(
            schema_pass=Decimal("1"),
            citation_coverage=Decimal("1"),
            task_score=Decimal("1"),
            prompt_injection_block=Decimal("1"),
            average_cost_usd=Decimal("0.01"),
            p95_latency_ms=100,
        ),
        total_cost_usd=0.01,
        total_latency_ms=100,
    )


def _make_bad_eval_result(capability: str = "filing") -> EvalRunResult:
    return EvalRunResult(
        dataset_version=1,
        capability=capability,
        case_results=[
            EvalCaseResult("k1", capability, False, 0, 1, 0.5, False, 10.0, 60_000),
        ],
        aggregate_metrics=EvalMetrics(
            schema_pass=Decimal("0.5"),
            citation_coverage=Decimal("0.5"),
            task_score=Decimal("0.5"),
            prompt_injection_block=Decimal("0.5"),
            average_cost_usd=Decimal("10"),
            p95_latency_ms=60_000,
        ),
        total_cost_usd=10.0,
        total_latency_ms=60_000,
    )


@pytest.mark.asyncio
async def test_validate_change_no_change_returns_not_required() -> None:
    pipeline = EvalPipeline(provider=AsyncMock(), dataset_path=Path("dummy.json"))
    change = ArtifactChange(capability="filing", old_version=_same_version(), new_version=_same_version())
    result = await pipeline.validate_change(change, {}, "gpt-4o", {})
    assert result.requires_eval is False
    assert result.eval_result is None
    assert result.promotion is None
    assert result.promoted is False


@pytest.mark.asyncio
async def test_validate_change_model_change_triggers_eval() -> None:
    mock_runner = AsyncMock()
    mock_runner.run_eval_dataset = AsyncMock(return_value={"filing": _make_eval_result()})
    mock_dataset = AsyncMock()
    mock_dataset.capabilities = {"filing": []}
    mock_dataset.version = 1

    with (
        patch("ia_investing.ai.eval_pipeline.load_eval_dataset", return_value=(mock_dataset, "hash")),
        patch("ia_investing.ai.eval_pipeline.EvalRunner", return_value=mock_runner),
    ):
        pipeline = EvalPipeline(provider=AsyncMock(), dataset_path=Path("dummy.json"))
        change = ArtifactChange(capability="filing", old_version=_same_version(), new_version=_model_changed_version())
        result = await pipeline.validate_change(
            change,
            {"filing": "inst"},
            "gpt-4o",
            {"filing": "{}"},
        )
        assert result.requires_eval is True
        assert result.eval_result is not None
        mock_runner.run_eval_dataset.assert_awaited_once()


@pytest.mark.asyncio
async def test_validate_change_passing_metrics_promotes() -> None:
    mock_runner = AsyncMock()
    mock_runner.run_eval_dataset = AsyncMock(return_value={"filing": _make_eval_result()})
    mock_dataset = AsyncMock()
    mock_dataset.capabilities = {"filing": []}
    mock_dataset.version = 1

    with (
        patch("ia_investing.ai.eval_pipeline.load_eval_dataset", return_value=(mock_dataset, "hash")),
        patch("ia_investing.ai.eval_pipeline.EvalRunner", return_value=mock_runner),
    ):
        pipeline = EvalPipeline(provider=AsyncMock(), dataset_path=Path("dummy.json"))
        change = ArtifactChange(capability="filing", old_version=_same_version(), new_version=_model_changed_version())
        result = await pipeline.validate_change(
            change,
            {"filing": "inst"},
            "gpt-4o",
            {"filing": "{}"},
        )
        assert result.promotion is not None
        assert result.promotion.passed is True
        assert result.promoted is True


@pytest.mark.asyncio
async def test_validate_change_failing_metrics_blocks_promotion() -> None:
    mock_runner = AsyncMock()
    mock_runner.run_eval_dataset = AsyncMock(return_value={"filing": _make_bad_eval_result()})
    mock_dataset = AsyncMock()
    mock_dataset.capabilities = {"filing": []}
    mock_dataset.version = 1

    with (
        patch("ia_investing.ai.eval_pipeline.load_eval_dataset", return_value=(mock_dataset, "hash")),
        patch("ia_investing.ai.eval_pipeline.EvalRunner", return_value=mock_runner),
    ):
        pipeline = EvalPipeline(provider=AsyncMock(), dataset_path=Path("dummy.json"))
        change = ArtifactChange(capability="filing", old_version=_same_version(), new_version=_model_changed_version())
        result = await pipeline.validate_change(
            change,
            {"filing": "inst"},
            "gpt-4o",
            {"filing": "{}"},
        )
        assert result.promotion is not None
        assert result.promotion.passed is False
        assert result.promoted is False
        assert len(result.promotion.failures) > 0


def test_validate_batch_filters_only_changed() -> None:
    same = _same_version()
    diff = _model_changed_version()
    pipeline = EvalPipeline(provider=AsyncMock(), dataset_path=Path("dummy.json"))
    changes = [
        ArtifactChange(capability="filing", old_version=same, new_version=same),
        ArtifactChange(capability="news", old_version=same, new_version=diff),
        ArtifactChange(capability="macro", old_version=diff, new_version=same),
        ArtifactChange(capability="political", old_version=same, new_version=same),
    ]
    result = pipeline.validate_batch(changes)
    assert len(result) == 2
    assert result[0].capability == "news"
    assert result[1].capability == "macro"
