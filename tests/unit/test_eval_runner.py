from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from ia_investing.ai.eval_datasets import EvalCaseFile, EvalDatasetFile
from ia_investing.ai.eval_gate import CapabilityVersion, EvalGate
from ia_investing.ai.eval_runner import EvalCaseResult, EvalRunner
from ia_investing.ai.provider import ProviderResponse, ProviderUsage


def _make_case(key: str = "case-1", tags: list[str] | None = None) -> EvalCaseFile:
    return EvalCaseFile(
        key=key,
        tags=tags or ["unit"],
        input={"query": "test"},
        expected={"declared": True},
    )


def _make_provider_response(
    output: dict[str, object],
    cost: float = 0.01,
    duration_ms: int = 100,
) -> ProviderResponse:
    usage = ProviderUsage(
        prompt_tokens=10,
        completion_tokens=10,
        cost_usd=Decimal(str(cost)),
        duration_ms=duration_ms,
    )
    return ProviderResponse(provider_run_id="run-1", output=output, usage=usage)


@pytest.mark.asyncio
async def test_run_eval_case_valid_output_schema_pass() -> None:
    provider = AsyncMock()
    provider.complete.return_value = _make_provider_response(
        {"summary": "ok", "findings": [{"citations": []}]},
    )
    runner = EvalRunner(provider=provider)
    case = _make_case()
    result = await runner.run_eval_case("filing", case, "instructions", "gpt-4o", {"required": ["summary"]})
    assert result.schema_pass is True
    assert result.case_key == "case-1"
    assert result.capability == "filing"
    assert result.citations_found == 0
    assert result.citations_expected == 1


@pytest.mark.asyncio
async def test_run_eval_case_invalid_output_schema_fail() -> None:
    provider = AsyncMock()
    provider.complete.return_value = _make_provider_response({"wrong_key": "value"})
    runner = EvalRunner(provider=provider)
    case = _make_case()
    result = await runner.run_eval_case("filing", case, "instructions", "gpt-4o", {"required": ["summary"]})
    assert result.schema_pass is False
    assert result.task_score == 0.0


def test_compute_aggregate_known_values() -> None:
    runner = EvalRunner(provider=AsyncMock())
    results = [
        EvalCaseResult("c1", "filing", True, 2, 2, 1.0, False, 0.01, 100),
        EvalCaseResult("c2", "filing", False, 0, 1, 0.5, True, 0.02, 200),
    ]
    metrics = runner._compute_aggregate(results)
    assert metrics.schema_pass == Decimal("0.5")
    assert metrics.task_score == Decimal("0.75")
    assert metrics.prompt_injection_block == Decimal("0.5")
    assert metrics.average_cost_usd == Decimal("0.015")
    assert metrics.p95_latency_ms == 200


@pytest.mark.asyncio
async def test_run_eval_dataset_groups_by_capability() -> None:
    provider = AsyncMock()
    provider.complete.return_value = _make_provider_response({"summary": "ok"})
    runner = EvalRunner(provider=provider)
    dataset = EvalDatasetFile(
        version=1,
        capabilities={
            "filing": [_make_case("f-1"), _make_case("f-2")],
            "news": [_make_case("n-1")],
        },
    )
    instructions = {"filing": "f-inst", "news": "n-inst"}
    schemas = {"filing": '{"required": ["summary"]}', "news": '{"required": ["summary"]}'}
    run_results = await runner.run_eval_dataset(dataset, instructions, "gpt-4o", schemas)
    assert set(run_results.keys()) == {"filing", "news"}
    assert len(run_results["filing"].case_results) == 2
    assert len(run_results["news"].case_results) == 1
    assert run_results["filing"].dataset_version == 1
    assert run_results["filing"].capability == "filing"


def test_eval_gate_requires_eval_detects_model_change() -> None:
    gate = EvalGate()
    old = CapabilityVersion(prompt_hash="a", schema_hash="b", model_name="gpt-4o", toolset_hash="c")
    new_same = CapabilityVersion(prompt_hash="a", schema_hash="b", model_name="gpt-4o", toolset_hash="c")
    new_model = CapabilityVersion(prompt_hash="a", schema_hash="b", model_name="gpt-4.1", toolset_hash="c")
    assert gate.requires_eval(old, new_same) is False
    assert gate.requires_eval(old, new_model) is True
