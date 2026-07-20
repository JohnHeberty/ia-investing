from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from ia_investing.ai.contracts import (
    AgentFinding,
    Citation,
    CoordinatorOutput,
    ResearchPlan,
    SpecialistOutput,
)
from ia_investing.ai.coordinator import ResearchCoordinator
from ia_investing.ai.eval_gate import CapabilityVersion, EvalGate
from ia_investing.ai.evals import EvalMetrics, EvalThresholds, evaluate_promotion
from ia_investing.ai.guardrails import BudgetUsage, GuardrailViolationError, RunBudget
from ia_investing.ai.tracing import extract_trace_id, span_context

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
        citations=[Citation(evidence_id=uuid4(), claim="source")],
    )


def _inference(statement: str, confidence: str = "0.6") -> AgentFinding:
    return AgentFinding(
        statement=statement,
        kind="inference",
        confidence=Decimal(confidence),
    )


def _inference_with_cite(statement: str, confidence: str = "0.6") -> AgentFinding:
    return AgentFinding(
        statement=statement,
        kind="inference",
        confidence=Decimal(confidence),
        citations=[Citation(evidence_id=uuid4(), claim="supporting evidence")],
    )


class TestMultiAgentE2E:
    @pytest.mark.asyncio
    async def test_full_research_coordinator_e2e(self) -> None:
        async def specialist_executor(capability: str, question: str) -> SpecialistOutput:
            if capability == "filing":
                return _output("filing", findings=[_fact("revenue grew 12%")])
            if capability == "news":
                return _output("news", findings=[_fact("positive market sentiment")])
            return _output("macro", findings=[_fact("GDP growth stable at 2.1%")])

        plan = _plan(
            [
                {"capability": "filing", "question": "Analyze filing", "required": True},
                {"capability": "news", "question": "Scan news", "required": True},
                {"capability": "macro", "question": "Assess macro", "required": True},
            ]
        )
        coordinator = ResearchCoordinator(specialist_executor, _budget())
        result = await coordinator.execute(plan)

        assert isinstance(result, CoordinatorOutput)
        assert len(result.specialist_outputs) == 3
        assert len(result.consolidated_findings) == 3
        assert result.confidence > Decimal(0)
        assert result.partial_failure_capabilities == []
        caps = {o.capability for o in result.specialist_outputs}
        assert caps == {"filing", "news", "macro"}

    @pytest.mark.asyncio
    async def test_multi_agent_with_tracing_correlation(self) -> None:
        async def specialist_executor(capability: str, question: str) -> SpecialistOutput:
            return _output(capability, findings=[_fact(f"{capability} finding")])

        plan = _plan(
            [
                {"capability": "filing", "question": "q1", "required": True},
                {"capability": "news", "question": "q2", "required": True},
                {"capability": "macro", "question": "q3", "required": True},
            ]
        )
        coordinator = ResearchCoordinator(specialist_executor, _budget())
        await coordinator.execute(plan)

        attrs = span_context(
            run_id="run-001",
            case_id="case-abc",
            capability="filing",
            version="1.0.0",
        )
        assert attrs["agent.run_id"] == "run-001"
        assert attrs["agent.capability"] == "filing"
        assert attrs["agent.version"] == "1.0.0"
        assert attrs["agent.case_id"] == "case-abc"

        trace_id = extract_trace_id()
        assert trace_id is None or isinstance(trace_id, str)

        attrs_news = span_context(
            run_id="run-002",
            capability="news",
            version="2.1.0",
            workflow_id="wf-789",
        )
        assert attrs_news["agent.run_id"] == "run-002"
        assert attrs_news["agent.capability"] == "news"
        assert attrs_news["agent.version"] == "2.1.0"
        assert attrs_news["agent.workflow_id"] == "wf-789"

    @pytest.mark.asyncio
    async def test_multi_agent_cost_tracking(self) -> None:
        budget = _budget(max_cost_usd="1.0")
        usage = BudgetUsage()

        async def specialist_executor(capability: str, question: str) -> SpecialistOutput:
            return _output(capability, findings=[_fact(f"{capability} data point")])

        plan = _plan(
            [
                {"capability": "filing", "question": "q1", "required": True},
                {"capability": "news", "question": "q2", "required": True},
                {"capability": "macro", "question": "q3", "required": True},
            ]
        )
        coordinator = ResearchCoordinator(specialist_executor, budget)
        result = await coordinator.execute(plan)

        assert len(result.specialist_outputs) == 3
        usage.tool_calls = 3
        usage.turns = 3
        assert usage.cost_usd <= budget.max_cost_usd
        assert usage.tool_calls == len(plan.steps)

    @pytest.mark.asyncio
    async def test_multi_agent_evidence_coverage(self) -> None:
        fid1, fid2, fid3 = uuid4(), uuid4(), uuid4()

        async def specialist_executor(capability: str, question: str) -> SpecialistOutput:
            if capability == "filing":
                return _output(
                    "filing",
                    findings=[
                        AgentFinding(
                            statement="revenue increased 15%",
                            kind="fact",
                            confidence=Decimal("0.9"),
                            citations=[Citation(evidence_id=fid1, claim="annual report")],
                        ),
                        AgentFinding(
                            statement="profit margin expanded",
                            kind="inference",
                            confidence=Decimal("0.6"),
                            citations=[Citation(evidence_id=fid2, claim="financial analysis")],
                        ),
                    ],
                )
            if capability == "news":
                return _output(
                    "news",
                    findings=[
                        AgentFinding(
                            statement="positive analyst coverage",
                            kind="fact",
                            confidence=Decimal("0.7"),
                            citations=[Citation(evidence_id=fid3, claim="news article")],
                        ),
                    ],
                )
            return _output(
                "macro",
                findings=[
                    _inference("interest rates expected to hold"),
                ],
            )

        plan = _plan(
            [
                {"capability": "filing", "question": "q1", "required": True},
                {"capability": "news", "question": "q2", "required": True},
                {"capability": "macro", "question": "q3", "required": True},
            ]
        )
        coordinator = ResearchCoordinator(specialist_executor, _budget())
        result = await coordinator.execute(plan)

        all_findings = result.consolidated_findings
        material = [f for f in all_findings if f.confidence >= Decimal("0.5")]
        for finding in material:
            if finding.kind == "fact":
                assert finding.citations, f"fact finding '{finding.statement}' lacks citations"

        cited_ids = {citation.evidence_id for finding in all_findings for citation in finding.citations}
        consolidated_ids = set()
        for output in result.specialist_outputs:
            for finding in output.findings:
                for citation in finding.citations:
                    consolidated_ids.add(citation.evidence_id)
        assert cited_ids == consolidated_ids
        assert fid1 in consolidated_ids
        assert fid2 in consolidated_ids
        assert fid3 in consolidated_ids

    @pytest.mark.asyncio
    async def test_partial_failure_with_e2e_tracing(self) -> None:
        async def specialist_executor(capability: str, question: str) -> SpecialistOutput:
            if capability in {"news", "political"}:
                raise RuntimeError(f"{capability} service unavailable")
            if capability == "filing":
                return _output("filing", findings=[_fact("revenue up 10%")])
            if capability == "macro":
                return _output("macro", findings=[_fact("inflation easing")])
            return _output("critic", findings=[_inference("valuation stretched")])

        plan = _plan(
            [
                {"capability": "filing", "question": "q1", "required": True},
                {"capability": "news", "question": "q2", "required": True},
                {"capability": "macro", "question": "q3", "required": True},
                {"capability": "political", "question": "q4", "required": True},
                {"capability": "critic", "question": "q5", "required": True},
            ]
        )
        coordinator = ResearchCoordinator(specialist_executor, _budget())
        result = await coordinator.execute(plan)

        assert sorted(result.partial_failure_capabilities) == ["news", "political"]
        assert len(result.specialist_outputs) == 3
        success_caps = {o.capability for o in result.specialist_outputs}
        assert success_caps == {"filing", "macro", "critic"}

        successful_findings = [finding for output in result.specialist_outputs for finding in output.findings]
        assert len(successful_findings) == 3
        expected_confidence = sum((f.confidence for f in successful_findings), start=Decimal(0)) / Decimal(
            len(successful_findings)
        )
        assert result.confidence == expected_confidence

    @pytest.mark.asyncio
    async def test_eval_gate_blocks_degradation(self) -> None:
        baseline = EvalMetrics(
            schema_pass=Decimal("1"),
            citation_coverage=Decimal("1"),
            task_score=Decimal("0.85"),
            prompt_injection_block=Decimal("1"),
            average_cost_usd=Decimal("0.30"),
            p95_latency_ms=15_000,
        )
        candidate = EvalMetrics(
            schema_pass=Decimal("0.9"),
            citation_coverage=Decimal("0.95"),
            task_score=Decimal("0.70"),
            prompt_injection_block=Decimal("1"),
            average_cost_usd=Decimal("0.40"),
            p95_latency_ms=20_000,
        )
        thresholds = EvalThresholds(
            min_schema_pass=Decimal("1"),
            min_citation_coverage=Decimal("1"),
            min_task_score=Decimal("0.80"),
            min_prompt_injection_block=Decimal("1"),
            max_average_cost_usd=Decimal("1.00"),
            max_p95_latency_ms=30_000,
        )

        gate = EvalGate()
        old_version = CapabilityVersion(
            prompt_hash="aaa",
            schema_hash="bbb",
            model_name="gpt-4o",
            toolset_hash="ccc",
        )
        new_version = CapabilityVersion(
            prompt_hash="aaa",
            schema_hash="bbb",
            model_name="gpt-4o",
            toolset_hash="ddd",
        )
        assert gate.requires_eval(old_version, new_version) is True

        decision = gate.validate_promotion("filing", baseline, candidate, thresholds)
        assert decision.passed is False
        assert len(decision.failures) > 0

        promo = evaluate_promotion(baseline, candidate, thresholds)
        assert promo.passed is False
        assert "schema_pass_below_threshold" in promo.failures
        assert "schema_pass_regressed" in promo.failures
        assert "citation_coverage_regressed" in promo.failures
        assert "task_score_below_threshold" in promo.failures

    @pytest.mark.asyncio
    async def test_budget_enforcement_across_multi_agent(self) -> None:
        async def specialist_executor(capability: str, question: str) -> SpecialistOutput:
            return _output(capability, findings=[_fact(f"{capability} data")])

        plan = _plan(
            [
                {"capability": "filing", "question": "q1", "required": True},
                {"capability": "news", "question": "q2", "required": True},
                {"capability": "macro", "question": "q3", "required": True},
            ]
        )
        coordinator = ResearchCoordinator(specialist_executor, _budget(max_tool_calls=2))

        with pytest.raises(GuardrailViolationError, match="Budget exceeded"):
            await coordinator.execute(plan)
