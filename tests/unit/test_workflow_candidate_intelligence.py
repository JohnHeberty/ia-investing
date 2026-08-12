"""Unit tests for workflows.candidate_intelligence — dataclasses, retry policies, and workflow structure."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from workflows.candidate_intelligence import (
    AGENT_RETRY,
    FAST_RETRY,
    NETWORK_RETRY,
    AutonomousEquityExplorationWorkflow,
    CandidateAnalysisWorkflow,
    CandidateSourceValidationWorkflow,
    ScheduledEquityExplorationWorkflow,
)

from ia_investing.orchestration.activities.candidate_intelligence import (
    CandidateCheckpoint,
    CandidateSourceValidationInput,
    CandidateSourceValidationResult,
    CandidateWorkflowInput,
    CandidateWorkflowResult,
    ExplorationShortlist,
    ExplorationWorkflowInput,
    ExplorationWorkflowResult,
    ExplorationFindings,
    ExplorationShortlist,
)


@pytest.mark.unit
class TestRetryPolicies:
    def test_fast_retry(self):
        assert FAST_RETRY.initial_interval == timedelta(seconds=2)
        assert FAST_RETRY.backoff_coefficient == 2.0
        assert FAST_RETRY.maximum_interval == timedelta(minutes=1)
        assert FAST_RETRY.maximum_attempts == 5

    def test_network_retry(self):
        assert NETWORK_RETRY.initial_interval == timedelta(seconds=5)
        assert NETWORK_RETRY.backoff_coefficient == 2.0
        assert NETWORK_RETRY.maximum_interval == timedelta(minutes=5)
        assert NETWORK_RETRY.maximum_attempts == 8

    def test_agent_retry(self):
        assert AGENT_RETRY.initial_interval == timedelta(seconds=10)
        assert AGENT_RETRY.backoff_coefficient == 2.0
        assert AGENT_RETRY.maximum_interval == timedelta(minutes=10)
        assert AGENT_RETRY.maximum_attempts == 3


@pytest.mark.unit
class TestCandidateDataclasses:
    def test_candidate_workflow_input(self):
        inp = CandidateWorkflowInput(
            candidate_id=uuid4(),
            analysis_run_id=uuid4(),
            organization_id=uuid4(),
            data_as_of=datetime.now(timezone.utc),
        )
        assert inp.allow_incomplete is False
        assert inp.correlation_id is None

    def test_candidate_workflow_input_with_optionals(self):
        cid = uuid4()
        inp = CandidateWorkflowInput(
            candidate_id=cid,
            analysis_run_id=uuid4(),
            organization_id=uuid4(),
            data_as_of=datetime.now(timezone.utc),
            allow_incomplete=True,
            correlation_id=uuid4(),
        )
        assert inp.allow_incomplete is True
        assert inp.correlation_id is not None

    def test_candidate_checkpoint(self):
        cp = CandidateCheckpoint(
            candidate_id=uuid4(),
            stage="identity",
            blocked=True,
            decision="pending",
            reason="Need more data",
        )
        assert cp.blocker_codes == ()
        assert cp.payload is None

    def test_candidate_checkpoint_with_blockers(self):
        cp = CandidateCheckpoint(
            candidate_id=uuid4(),
            stage="readiness",
            blocked=True,
            decision="pending",
            reason="Missing sources",
            blocker_codes=("investor_relations", "financial_reports"),
            payload={"key": "value"},
        )
        assert len(cp.blocker_codes) == 2
        assert cp.payload == {"key": "value"}

    def test_candidate_workflow_result(self):
        r = CandidateWorkflowResult(
            candidate_id=uuid4(),
            analysis_run_id=uuid4(),
            status="approved",
            decision="approve",
            reason="Strong fundamentals",
            blocker_codes=(),
        )
        assert r.status == "approved"

    def test_candidate_source_validation_input(self):
        inp = CandidateSourceValidationInput(
            candidate_id=uuid4(),
            source_id=uuid4(),
            organization_id=uuid4(),
        )
        assert inp.correlation_id is None

    def test_candidate_source_validation_result(self):
        r = CandidateSourceValidationResult(
            candidate_id=uuid4(),
            source_id=uuid4(),
            status="verified",
            official=True,
            reason="Cross-source match",
        )
        assert r.resolved_gap_codes == ()

    def test_exploration_workflow_input(self):
        inp = ExplorationWorkflowInput(
            exploration_run_id=uuid4(),
            organization_id=uuid4(),
            data_as_of=datetime.now(timezone.utc),
        )
        assert inp.correlation_id is None

    def test_exploration_workflow_result(self):
        r = ExplorationWorkflowResult(
            exploration_run_id=uuid4(),
            status="completed",
            universe_size=100,
            eligible_size=20,
            suggestion_count=5,
        )
        assert r.suggestion_count == 5

    def test_exploration_shortlist(self):
        cmd = ExplorationWorkflowInput(
            exploration_run_id=uuid4(),
            organization_id=uuid4(),
            data_as_of=datetime.now(timezone.utc),
        )
        sl = ExplorationShortlist(
            command=cmd,
            securities=({"ticker": "PETR4"},),
            universe_size=50,
            eligible_size=10,
        )
        assert len(sl.securities) == 1

    def test_exploration_findings(self):
        cmd = ExplorationWorkflowInput(
            exploration_run_id=uuid4(),
            organization_id=uuid4(),
            data_as_of=datetime.now(timezone.utc),
        )
        sl = ExplorationShortlist(
            command=cmd,
            securities=(),
            universe_size=0,
            eligible_size=0,
        )
        findings = ExplorationFindings(
            shortlist=sl,
            suggestions=({"ticker": "PETR4", "score": 0.9},),
            limitations=("low_data",),
        )
        assert len(findings.suggestions) == 1
        assert findings.limitations == ("low_data",)


@pytest.mark.unit
class TestWorkflowClassStructure:
    def test_candidate_analysis_workflow_has_cancel_signal(self):
        assert hasattr(CandidateAnalysisWorkflow, "cancel")

    def test_candidate_source_validation_workflow_class_name(self):
        defn = getattr(CandidateSourceValidationWorkflow, "__temporal_workflow_definition")
        assert defn.name == "CandidateSourceValidationWorkflow"

    def test_autonomous_exploration_workflow_class_name(self):
        defn = getattr(AutonomousEquityExplorationWorkflow, "__temporal_workflow_definition")
        assert defn.name == "AutonomousEquityExplorationWorkflow"

    def test_scheduled_exploration_workflow_class_name(self):
        defn = getattr(ScheduledEquityExplorationWorkflow, "__temporal_workflow_definition")
        assert defn.name == "ScheduledEquityExplorationWorkflow"
