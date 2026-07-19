from __future__ import annotations

import asyncio
from argparse import ArgumentParser
from uuid import uuid4

from temporalio.client import Client

from ia_investing.domain.portfolio_decision import CommitteeVote, PortfolioDecisionInputs
from ia_investing.orchestration import TASK_QUEUES, Capability
from workflows import (
    PaperRebalanceInput,
    PaperRebalanceWorkflow,
    PaperReconciliationInput,
    PaperReconciliationWorkflow,
    PolicyEventInput,
    PolicyEventWorkflow,
    PortfolioConstructionInput,
    PortfolioConstructionWorkflow,
)


async def verify(portfolio_id: str | None, organization_id: str | None, temporal_address: str) -> None:
    client = await Client.connect(temporal_address, namespace="default")
    suffix = uuid4().hex
    policy = await client.start_workflow(
        PolicyEventWorkflow.run,
        PolicyEventInput("policy-1", 1, "a" * 64, True, 30),
        id=f"verify-policy-{suffix}",
        task_queue=TASK_QUEUES[Capability.RESEARCH_AGENTS],
    )
    if await policy.query(PolicyEventWorkflow.state) != "awaiting_review":
        raise RuntimeError("material policy workflow did not pause for review")
    await policy.signal(PolicyEventWorkflow.review, "approved")
    policy_result = await policy.result()
    if policy_result.decision != "approved" or policy_result.thesis_changed:
        raise RuntimeError("policy review result violated the no-automatic-thesis-change contract")

    rebalance = await client.start_workflow(
        PaperRebalanceWorkflow.run,
        PaperRebalanceInput("portfolio-1", "version-1", "b" * 64, 30),
        id=f"verify-paper-{suffix}",
        task_queue=TASK_QUEUES[Capability.PORTFOLIO_RISK],
    )
    if await rebalance.query(PaperRebalanceWorkflow.state) != "awaiting_approval":
        raise RuntimeError("paper rebalance workflow did not pause for approval")
    await rebalance.signal(PaperRebalanceWorkflow.decide, "approved_for_paper")
    rebalance_result = await rebalance.result()
    if rebalance_result.state != "approved_for_paper" or rebalance_result.execution_environment != "paper":
        raise RuntimeError("rebalance workflow escaped the paper-only boundary")

    construction = await client.start_workflow(
        PortfolioConstructionWorkflow.run,
        PortfolioConstructionInput(
            PortfolioDecisionInputs(
                "portfolio-1",
                "analyst",
                "c" * 64,
                "d" * 64,
                "approved",
                "approved",
                "optimal",
                True,
                False,
            ),
            30,
        ),
        id=f"verify-construction-{suffix}",
        task_queue=TASK_QUEUES[Capability.PORTFOLIO_RISK],
    )
    await construction.signal(
        PortfolioConstructionWorkflow.vote,
        CommitteeVote("manager", "portfolio_manager", "approved", "approved", "e" * 64),
    )
    await construction.signal(
        PortfolioConstructionWorkflow.vote,
        CommitteeVote("risk", "risk_officer", "approved", "risk approved", "f" * 64),
    )
    construction_result = await construction.result()
    if construction_result.state != "approved" or construction_result.execution_environment != "paper":
        raise RuntimeError("portfolio construction decision did not remain paper-only")

    reconciliation_summary = "reconciliation=skipped"
    if portfolio_id and organization_id:
        reconciliation = await client.start_workflow(
            PaperReconciliationWorkflow.run,
            PaperReconciliationInput(portfolio_id, organization_id),
            id=f"verify-reconciliation-{suffix}",
            task_queue=TASK_QUEUES[Capability.PORTFOLIO_RISK],
        )
        reconciliation_result = await reconciliation.result()
        if reconciliation_result.environment != "paper":
            raise RuntimeError("reconciliation escaped the paper-only boundary")
        reconciliation_summary = (
            f"reconciliation=ok breaks={reconciliation_result.break_count} "
            f"blocking={reconciliation_result.blocking_count}"
        )
    print(
        "policy-paper-workflows-ok "
        f"policy={policy_result.decision} thesis_changed={policy_result.thesis_changed} "
        f"rebalance={rebalance_result.state} construction={construction_result.state} "
        f"environment={rebalance_result.execution_environment} {reconciliation_summary}"
    )


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("--portfolio-id")
    parser.add_argument("--organization-id")
    parser.add_argument("--temporal-address", default="localhost:7233")
    arguments = parser.parse_args()
    if bool(arguments.portfolio_id) != bool(arguments.organization_id):
        parser.error("--portfolio-id and --organization-id must be supplied together")
    asyncio.run(verify(arguments.portfolio_id, arguments.organization_id, arguments.temporal_address))
