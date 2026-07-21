from typing import Any

from temporalio import activity as temporal_activity

from apps.worker.main import ACTIVITIES_BY_CAPABILITY, WORKFLOWS_BY_CAPABILITY
from ia_investing.orchestration import TASK_QUEUES, Capability


def test_every_capability_has_a_task_queue() -> None:
    assert set(TASK_QUEUES) == set(Capability)


def test_every_capability_has_registered_items() -> None:
    for cap in Capability:
        wfs = WORKFLOWS_BY_CAPABILITY[cap]
        acts = ACTIVITIES_BY_CAPABILITY[cap]
        if cap is Capability.DOCUMENT_PROCESSING:
            continue
        assert wfs or acts, f"capability {cap} has no workflows or activities"


def test_all_activities_have_temporal_decoration() -> None:
    bad: list[str] = []
    for cap, acts in ACTIVITIES_BY_CAPABILITY.items():
        for act in acts:
            if not hasattr(act, "__temporal_activity_definition"):
                bad.append(f"{act.__name__} in {cap}")
    assert not bad, f"activities missing Temporal decoration: {bad}"


def test_activity_names_are_unique_within_capability() -> None:
    bad: list[str] = []
    for cap, acts in ACTIVITIES_BY_CAPABILITY.items():
        seen: set[str] = set()
        for act in acts:
            name: str = act.__temporal_activity_definition.name
            if name in seen:
                bad.append(f"{name} in {cap}")
            seen.add(name)
    assert not bad, f"duplicate activity names within same capability: {bad}"


def test_all_workflows_have_temporal_decoration() -> None:
    for cap, wfs in WORKFLOWS_BY_CAPABILITY.items():
        for wf in wfs:
            assert hasattr(wf, "__temporal_workflow_definition"), (
                f"{wf.__name__} in {cap} is not a Temporal workflow"
            )


def test_workflow_names_are_unique_across_capabilities() -> None:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for wfs in WORKFLOWS_BY_CAPABILITY.values():
        for wf in wfs:
            name: str = wf.__temporal_workflow_definition.name
            if name in seen:
                duplicates.add(name)
            seen.add(name)
    assert not duplicates, f"duplicate workflow names: {duplicates}"


def test_research_agents_has_expected_activity_count() -> None:
    acts = ACTIVITIES_BY_CAPABILITY[Capability.RESEARCH_AGENTS]
    assert len(acts) >= 18  # research_mock(12) + thesis_review(6)


def test_portfolio_risk_includes_run_scorecard_and_validate_constraints() -> None:
    names = {a.__temporal_activity_definition.name for a in ACTIVITIES_BY_CAPABILITY[Capability.PORTFOLIO_RISK]}
    assert "run_scorecard" in names
    assert "validate_proposal_constraints" in names
