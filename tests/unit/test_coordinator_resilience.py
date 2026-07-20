from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from ia_investing.ai.contracts import (
    AgentFinding,
    Citation,
    ResearchPlan,
    SpecialistOutput,
)
from ia_investing.ai.coordinator import ResearchCoordinator
from ia_investing.ai.guardrails import (
    BudgetUsage,
    GuardrailViolationError,
    RunBudget,
    enforce_budget,
)

CUTOFF = datetime(2026, 1, 1, tzinfo=UTC)


def _budget(
    *,
    max_tool_calls: int = 10,
    max_turns: int = 10,
    max_cost_usd: str = "999",
    max_prompt_tokens: int = 100_000,
    max_completion_tokens: int = 100_000,
    max_duration_ms: int = 600_000,
) -> RunBudget:
    return RunBudget(
        max_prompt_tokens=max_prompt_tokens,
        max_completion_tokens=max_completion_tokens,
        max_cost_usd=Decimal(max_cost_usd),
        max_turns=max_turns,
        max_tool_calls=max_tool_calls,
        max_duration_ms=max_duration_ms,
    )


def _plan(steps: list[dict[str, object]]) -> ResearchPlan:
    return ResearchPlan(
        objective="test objective",
        steps=steps,  # type: ignore[arg-type]
        data_as_of=CUTOFF,
        knowledge_cutoff=CUTOFF,
    )


def _output(
    capability: str,
    *,
    findings: list[AgentFinding] | None = None,
    contradictions: list[str] | None = None,
) -> SpecialistOutput:
    return SpecialistOutput(
        capability=capability,  # type: ignore[arg-type]
        summary=f"{capability} summary",
        findings=findings or [],
        contradictions=contradictions or [],
        uncertainty=[],
        materiality="low",
        knowledge_cutoff=CUTOFF,
    )


def _fact(statement: str, confidence: str = "0.8") -> AgentFinding:
    return AgentFinding(
        statement=statement,
        kind="fact",
        confidence=Decimal(confidence),
        citations=[Citation(evidence_id=_uuid(), claim="source")],
    )


def _uuid() -> UUID:
    return uuid4()


# ---------------------------------------------------------------------------
# F4-PR09.5 — Partial failure, retry, budget, cancellation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_partial_failure_records_all_failed_capabilities() -> None:
    """4 steps, 2 fail → partial_failure_capabilities has both."""

    async def executor(capability: str, question: str) -> SpecialistOutput:
        del question
        if capability in {"news", "macro"}:
            raise RuntimeError(f"{capability} unavailable")
        return _output(capability)

    plan = _plan([
        {"capability": "filing", "question": "q1", "required": True},
        {"capability": "news", "question": "q2", "required": False},
        {"capability": "macro", "question": "q3", "required": False},
        {"capability": "political", "question": "q4", "required": False},
    ])
    result = await ResearchCoordinator(executor, _budget()).execute(plan)

    assert sorted(result.partial_failure_capabilities) == ["macro", "news"]
    assert len(result.specialist_outputs) == 2
    caps = {o.capability for o in result.specialist_outputs}
    assert caps == {"filing", "political"}


@pytest.mark.asyncio
async def test_required_step_failure_does_not_block_optional_steps() -> None:
    """Required filing fails, optional news succeeds → news appears in outputs."""

    async def executor(capability: str, question: str) -> SpecialistOutput:
        del question
        if capability == "filing":
            raise RuntimeError("filing service down")
        return _output(capability)

    plan = _plan([
        {"capability": "filing", "question": "q1", "required": True},
        {"capability": "news", "question": "q2", "required": False},
    ])
    result = await ResearchCoordinator(executor, _budget()).execute(plan)

    assert result.partial_failure_capabilities == ["filing"]
    assert len(result.specialist_outputs) == 1
    assert result.specialist_outputs[0].capability == "news"


@pytest.mark.asyncio
async def test_optional_step_failure_is_benign() -> None:
    """All optional steps fail → empty outputs but no exception."""

    async def executor(capability: str, question: str) -> SpecialistOutput:
        del capability, question
        raise RuntimeError("transient failure")

    plan = _plan([
        {"capability": "news", "question": "q1", "required": False},
        {"capability": "macro", "question": "q2", "required": False},
        {"capability": "political", "question": "q3", "required": False},
    ])
    result = await ResearchCoordinator(executor, _budget()).execute(plan)

    assert result.specialist_outputs == []
    assert result.consolidated_findings == []
    assert result.confidence == Decimal(0)
    assert sorted(result.partial_failure_capabilities) == ["macro", "news", "political"]


@pytest.mark.asyncio
async def test_budget_exceeded_stops_delegation() -> None:
    """budget max_tool_calls=2, plan has 3 steps → third step blocked by budget."""

    async def executor(capability: str, question: str) -> SpecialistOutput:
        del question
        return _output(capability)

    plan = _plan([
        {"capability": "filing", "question": "q1", "required": True},
        {"capability": "news", "question": "q2", "required": True},
        {"capability": "macro", "question": "q3", "required": True},
    ])

    with pytest.raises(GuardrailViolationError, match="budget_exceeded"):
        await ResearchCoordinator(executor, _budget(max_tool_calls=2)).execute(plan)


@pytest.mark.asyncio
async def test_budget_cost_exceeded_mid_run() -> None:
    """BudgetUsage with cost_usd exceeding max_cost_usd triggers budget_exceeded.

    The coordinator tracks tool_calls and turns; cost_usd is validated by
    enforce_budget which the coordinator calls each iteration.
    """
    budget = _budget(max_cost_usd="1.0")
    usage = BudgetUsage(cost_usd=Decimal("0.6"))
    enforce_budget(budget, usage)

    usage.cost_usd = Decimal("1.2")
    with pytest.raises(GuardrailViolationError, match="budget_exceeded"):
        enforce_budget(budget, usage)


@pytest.mark.asyncio
async def test_capability_not_in_allowlist_raises() -> None:
    """Step with 'shell' capability → PermissionError."""

    async def executor(capability: str, question: str) -> SpecialistOutput:
        del question
        return _output(capability)

    plan = _plan([
        {"capability": "filing", "question": "q1", "required": True},
    ])
    plan.steps[0].capability = "shell"  # type: ignore[assignment]

    with pytest.raises(PermissionError, match="shell"):
        await ResearchCoordinator(executor, _budget()).execute(plan)


@pytest.mark.asyncio
async def test_specialist_capability_mismatch_detected() -> None:
    """Specialist returns wrong capability → ValueError."""

    async def executor(capability: str, question: str) -> SpecialistOutput:
        del question
        return _output("news")

    plan = _plan([
        {"capability": "filing", "question": "q1", "required": True},
    ])

    with pytest.raises(ValueError, match="specialist changed"):
        await ResearchCoordinator(executor, _budget()).execute(plan)


@pytest.mark.asyncio
async def test_knowledge_cutoff_drift_detected() -> None:
    """Specialist returns different knowledge_cutoff → ValueError."""

    async def executor(capability: str, question: str) -> SpecialistOutput:
        del question
        return SpecialistOutput(
            capability="filing",  # type: ignore[arg-type]
            summary="ok",
            findings=[],
            materiality="low",
            knowledge_cutoff=datetime(2025, 6, 1, tzinfo=UTC),
        )

    plan = _plan([
        {"capability": "filing", "question": "q1", "required": True},
    ])

    with pytest.raises(ValueError, match="specialist changed"):
        await ResearchCoordinator(executor, _budget()).execute(plan)


@pytest.mark.asyncio
async def test_single_required_failure_still_aggregates() -> None:
    """1 required fails, 1 succeeds → partial_failure declared but findings preserved."""

    async def executor(capability: str, question: str) -> SpecialistOutput:
        del question
        if capability == "filing":
            raise RuntimeError("filing down")
        finding = _fact("revenue grew 12%")
        return _output(capability, findings=[finding])

    plan = _plan([
        {"capability": "filing", "question": "q1", "required": True},
        {"capability": "news", "question": "q2", "required": True},
    ])
    result = await ResearchCoordinator(executor, _budget()).execute(plan)

    assert result.partial_failure_capabilities == ["filing"]
    assert len(result.specialist_outputs) == 1
    assert result.specialist_outputs[0].capability == "news"
    assert len(result.consolidated_findings) == 1
    assert result.consolidated_findings[0].statement == "revenue grew 12%"
    assert result.confidence == Decimal("0.8")


@pytest.mark.asyncio
async def test_budget_turns_exceeded() -> None:
    """max_turns=1, 2 steps → second step blocked by budget."""

    async def executor(capability: str, question: str) -> SpecialistOutput:
        del question
        return _output(capability)

    plan = _plan([
        {"capability": "filing", "question": "q1", "required": True},
        {"capability": "news", "question": "q2", "required": True},
    ])

    with pytest.raises(GuardrailViolationError, match="budget_exceeded"):
        await ResearchCoordinator(executor, _budget(max_turns=1)).execute(plan)
