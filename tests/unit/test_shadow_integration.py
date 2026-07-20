from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from ia_investing.ai.eval_datasets import EvalCaseFile, EvalDatasetFile
from ia_investing.ai.evals import EvalThresholds
from ia_investing.ai.provider import ProviderResponse, ProviderUsage
from ia_investing.ai.shadow_integration import ShadowGate, ShadowGateConfig


def _provider_response(output: dict[str, object]) -> ProviderResponse:
    return ProviderResponse(
        provider_run_id="run-1",
        output=output,
        usage=ProviderUsage(
            prompt_tokens=10,
            completion_tokens=10,
            cost_usd=Decimal("0.01"),
            duration_ms=100,
        ),
    )


def _make_config(
    baseline_model: str = "gpt-4o",
    candidate_model: str = "gpt-4o-mini",
    instructions_by_capability: dict[str, str] | None = None,
    schemas_by_capability: dict[str, dict[str, object]] | None = None,
    eval_dataset: EvalDatasetFile | None = None,
    thresholds: EvalThresholds | None = None,
) -> ShadowGateConfig:
    return ShadowGateConfig(
        baseline_model=baseline_model,
        candidate_model=candidate_model,
        instructions_by_capability=instructions_by_capability or {"filing": "Analyze filing"},
        schemas_by_capability=schemas_by_capability or {"filing": {"required": ["summary"]}},
        eval_dataset=eval_dataset,
        thresholds=thresholds or EvalThresholds(),
    )


def _make_dataset(capability: str = "filing") -> EvalDatasetFile:
    return EvalDatasetFile(
        version=1,
        capabilities={
            capability: [
                EvalCaseFile(
                    key="c1",
                    tags=["unit"],
                    input={"query": "test"},
                    expected={"declared": True},
                ),
            ],
        },
    )


@pytest.mark.asyncio
async def test_shadow_gate_agreeing_outputs_opens_gate() -> None:
    provider = AsyncMock()
    provider.complete.return_value = _provider_response({"summary": "ok"})
    gate = ShadowGate(provider=provider)
    config = _make_config()
    result = await gate.run_shadow_gate("filing/case-1", {"data": 1}, config)
    assert result.gate_open is True
    assert result.shadow_result.outputs_agree is True
    assert result.eval_passed is True


@pytest.mark.asyncio
async def test_shadow_gate_disagreeing_outputs_closes_gate() -> None:
    provider = AsyncMock()
    provider.complete.side_effect = [
        _provider_response({"summary": "baseline"}),
        _provider_response({"summary": "candidate"}),
    ]
    gate = ShadowGate(provider=provider)
    config = _make_config()
    result = await gate.run_shadow_gate("filing/case-1", {"data": 1}, config)
    assert result.gate_open is False
    assert result.shadow_result.outputs_agree is False


@pytest.mark.asyncio
async def test_shadow_gate_eval_failure_closes_gate() -> None:
    provider = AsyncMock()
    provider.complete.return_value = _provider_response({"summary": "ok"})
    dataset = _make_dataset()
    thresholds = EvalThresholds(min_schema_pass=Decimal("1"))
    config = _make_config(eval_dataset=dataset, thresholds=thresholds)
    gate = ShadowGate(provider=provider)
    result = await gate.run_shadow_gate("filing/case-1", {"data": 1}, config)
    assert result.gate_open is False
    assert result.eval_passed is False
    assert result.promotion_decision is not None
    assert result.promotion_decision.passed is False


@pytest.mark.asyncio
async def test_batch_shadow_gate_processes_all_cases() -> None:
    provider = AsyncMock()
    provider.complete.return_value = _provider_response({"summary": "ok"})
    gate = ShadowGate(provider=provider)
    config = _make_config()
    cases = [
        ("filing/case-1", {"data": 1}),
        ("filing/case-2", {"data": 2}),
        ("filing/case-3", {"data": 3}),
    ]
    results = await gate.batch_shadow_gate(cases, config)
    assert len(results) == 3
    assert all(r.gate_open for r in results)
    assert [r.capability for r in results] == ["filing", "filing", "filing"]


@pytest.mark.asyncio
async def test_shadow_gate_without_eval_dataset_gate_open_based_on_agreement() -> None:
    provider = AsyncMock()
    provider.complete.return_value = _provider_response({"summary": "ok"})
    gate = ShadowGate(provider=provider)
    config = _make_config(eval_dataset=None)
    result = await gate.run_shadow_gate("filing/case-1", {"data": 1}, config)
    assert result.gate_open is True
    assert result.eval_passed is True
    assert result.promotion_decision is None
    assert result.shadow_result.outputs_agree is True
