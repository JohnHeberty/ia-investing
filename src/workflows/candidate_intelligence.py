from __future__ import annotations

from datetime import datetime, timedelta
from uuid import UUID

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from ia_investing.orchestration.activities.candidate_intelligence import (
        CandidateCheckpoint,
        CandidateSourceValidationInput,
        CandidateSourceValidationResult,
        CandidateWorkflowInput,
        CandidateWorkflowResult,
        ExplorationWorkflowInput,
        ExplorationWorkflowResult,
        collect_candidate_documents,
        complete_candidate_analysis_run,
        create_committee_pack,
        discover_candidate_sources,
        evaluate_candidate_readiness,
        persist_candidate_sources_and_gaps,
        persist_exploration_suggestions,
        resolve_candidate_identity,
        run_candidate_fundamental_analysis,
        run_candidate_risk_analysis,
        run_equity_explorer_agent,
        screen_equity_universe,
        validate_candidate_financial_data,
        validate_candidate_sources,
        validate_supplied_candidate_source,
    )

FAST_RETRY = RetryPolicy(
    initial_interval=timedelta(seconds=2),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(minutes=1),
    maximum_attempts=5,
)

NETWORK_RETRY = RetryPolicy(
    initial_interval=timedelta(seconds=5),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(minutes=5),
    maximum_attempts=8,
)

AGENT_RETRY = RetryPolicy(
    initial_interval=timedelta(seconds=10),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(minutes=10),
    maximum_attempts=3,
)


@workflow.defn(name="CandidateAnalysisWorkflow")
class CandidateAnalysisWorkflow:
    @workflow.run
    async def run(self, command: CandidateWorkflowInput) -> CandidateWorkflowResult:
        identity = await workflow.execute_activity(
            resolve_candidate_identity,
            command,
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=NETWORK_RETRY,
        )
        if identity.blocked:
            return await self._complete(command, identity)

        discovery = await workflow.execute_activity(
            discover_candidate_sources,
            command,
            start_to_close_timeout=timedelta(minutes=15),
            retry_policy=AGENT_RETRY,
        )
        await workflow.execute_activity(
            persist_candidate_sources_and_gaps,
            discovery,
            start_to_close_timeout=timedelta(minutes=2),
            retry_policy=FAST_RETRY,
        )
        readiness = await workflow.execute_activity(
            evaluate_candidate_readiness,
            command,
            start_to_close_timeout=timedelta(minutes=2),
            retry_policy=FAST_RETRY,
        )
        if readiness.blocked and not command.allow_incomplete:
            return await self._complete(command, readiness)

        source_validation = await workflow.execute_activity(
            validate_candidate_sources,
            command,
            start_to_close_timeout=timedelta(minutes=15),
            retry_policy=NETWORK_RETRY,
        )
        if source_validation.blocked and not command.allow_incomplete:
            return await self._complete(command, source_validation)

        collection = await workflow.execute_activity(
            collect_candidate_documents,
            command,
            start_to_close_timeout=timedelta(hours=1),
            heartbeat_timeout=timedelta(minutes=2),
            retry_policy=NETWORK_RETRY,
        )
        if collection.blocked:
            return await self._complete(command, collection)

        quality = await workflow.execute_activity(
            validate_candidate_financial_data,
            command,
            start_to_close_timeout=timedelta(minutes=30),
            retry_policy=FAST_RETRY,
        )
        if quality.blocked:
            return await self._complete(command, quality)

        research = await workflow.execute_activity(
            run_candidate_fundamental_analysis,
            command,
            start_to_close_timeout=timedelta(hours=1),
            heartbeat_timeout=timedelta(minutes=2),
            retry_policy=AGENT_RETRY,
        )
        if research.blocked or research.decision == "reject":
            return await self._complete(command, research)

        risk = await workflow.execute_activity(
            run_candidate_risk_analysis,
            command,
            start_to_close_timeout=timedelta(minutes=30),
            retry_policy=FAST_RETRY,
        )
        if risk.blocked or risk.decision == "reject":
            return await self._complete(command, risk)

        committee = await workflow.execute_activity(
            create_committee_pack,
            command,
            start_to_close_timeout=timedelta(minutes=30),
            retry_policy=AGENT_RETRY,
        )
        return await self._complete(command, committee)

    async def _complete(
        self,
        command: CandidateWorkflowInput,
        checkpoint: CandidateCheckpoint,
    ) -> CandidateWorkflowResult:
        return await workflow.execute_activity(
            complete_candidate_analysis_run,
            (command, checkpoint),
            start_to_close_timeout=timedelta(minutes=2),
            retry_policy=FAST_RETRY,
        )


@workflow.defn(name="CandidateSourceValidationWorkflow")
class CandidateSourceValidationWorkflow:
    @workflow.run
    async def run(
        self,
        command: CandidateSourceValidationInput,
    ) -> CandidateSourceValidationResult:
        return await workflow.execute_activity(
            validate_supplied_candidate_source,
            command,
            start_to_close_timeout=timedelta(minutes=15),
            retry_policy=NETWORK_RETRY,
        )


@workflow.defn(name="AutonomousEquityExplorationWorkflow")
class AutonomousEquityExplorationWorkflow:
    @workflow.run
    async def run(self, command: ExplorationWorkflowInput) -> ExplorationWorkflowResult:
        shortlist = await workflow.execute_activity(
            screen_equity_universe,
            command,
            start_to_close_timeout=timedelta(minutes=30),
            retry_policy=NETWORK_RETRY,
        )
        findings = await workflow.execute_activity(
            run_equity_explorer_agent,
            shortlist,
            start_to_close_timeout=timedelta(hours=1),
            heartbeat_timeout=timedelta(minutes=2),
            retry_policy=AGENT_RETRY,
        )
        return await workflow.execute_activity(
            persist_exploration_suggestions,
            findings,
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=FAST_RETRY,
        )


@workflow.defn(name="ScheduledEquityExplorationWorkflow")
class ScheduledEquityExplorationWorkflow:
    @workflow.run
    async def run(self, command: dict[str, object]) -> ExplorationWorkflowResult:
        created = await workflow.execute_activity(
            "create_scheduled_exploration_run",
            command,
            start_to_close_timeout=timedelta(minutes=2),
            retry_policy=FAST_RETRY,
        )
        child_input = ExplorationWorkflowInput(
            exploration_run_id=UUID(str(created["exploration_run_id"])),
            organization_id=UUID(str(created["organization_id"])),
            data_as_of=datetime.fromisoformat(str(created["data_as_of"])),
            correlation_id=UUID(str(created["correlation_id"])),
        )
        return await workflow.execute_child_workflow(
            AutonomousEquityExplorationWorkflow.run,
            child_input,
            id=f"equity-exploration-{child_input.exploration_run_id}",
            task_queue="research-agents",
        )
