from __future__ import annotations

from typing import Any

from temporalio import activity
from temporalio.exceptions import ApplicationError

from ia_investing.application.audit import emit_security_event
from ia_investing.domain.base_machine import BaseMachineModel, InvalidTransitionError
from ia_investing.domain.committee_machine import CommitteeMachineModel, create_committee_machine
from ia_investing.domain.execution_machine import ExecutionMachineModel, create_execution_machine
from ia_investing.domain.portfolio_machine import PortfolioMachineModel, create_portfolio_machine
from ia_investing.domain.risk_machine import RiskMachineModel, create_risk_machine
from ia_investing.domain.thesis_machine import ThesisMachineModel, create_thesis_machine
from ia_investing.orchestration.activities._telemetry import activity_span

_MACHINES: dict[str, tuple[type[BaseMachineModel], Any]] = {
    "thesis": (ThesisMachineModel, create_thesis_machine),
    "committee": (CommitteeMachineModel, create_committee_machine),
    "portfolio": (PortfolioMachineModel, create_portfolio_machine),
    "risk": (RiskMachineModel, create_risk_machine),
    "execution": (ExecutionMachineModel, create_execution_machine),
}


@activity.defn(name="apply_state_transition")
async def apply_state_transition(
    entity_type: str,
    model_data: dict,
    trigger: str,
    reason: str | None = None,
    **kwargs,
) -> dict:
    with activity_span("apply_state_transition"):
        entry = _MACHINES.get(entity_type)
        if entry is None:
            raise ApplicationError(
                f"Unknown state machine entity type: {entity_type}",
                non_retryable=True,
            )
        model_class, factory = entry
        model = model_class(**model_data)
        machine = factory(model)

        try:
            new_state = machine.apply(trigger, reason=reason, **kwargs)
        except InvalidTransitionError as exc:
            emit_security_event(
                "state_transition_failure",
                resource=f"{entity_type}:{model.id}",
                action=f"{entity_type}:{trigger}",
                outcome="deny",
                detail=str(exc),
            )
            raise ApplicationError(str(exc), type="StateTransitionError", non_retryable=True) from exc

        emit_security_event(
            "state_transition",
            resource=f"{entity_type}:{model.id}",
            action=f"{entity_type}:{trigger}",
            outcome="allow",
            detail=f"{entity_type} transitioned to {new_state}",
        )

        return machine.to_dict()


STATE_MACHINE_ACTIVITIES = (apply_state_transition,)
