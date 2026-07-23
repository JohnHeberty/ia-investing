from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.execution import Execution
from database.models.operations import OperationDispatchOutbox
from ia_investing.application.audit_service import AuditService
from ia_investing.domain.base_machine import InvalidTransitionError
from ia_investing.domain.execution_machine import ExecutionMachineModel, create_execution_machine


class InsufficientBalanceError(ValueError):
    pass


class ExecutionService:
    def __init__(self, session: AsyncSession, audit: AuditService) -> None:
        self._session = session
        self._audit = audit

    async def create_execution(
        self,
        order_id: str,
        portfolio_id: UUID,
        action: str,
        quantity: Decimal,
        price_limit: Decimal | None = None,
        actor_id: UUID | None = None,
    ) -> Execution:
        execution = Execution(
            order_id=order_id,
            portfolio_id=portfolio_id,
            action=action,
            quantity=quantity,
            price_limit=price_limit,
            state="pending",
        )
        self._session.add(execution)
        await self._session.flush()

        await self._audit.log(
            actor_id=actor_id,
            action="create",
            resource_type="execution",
            resource_id=execution.id,  # type: ignore[arg-type]
            changes={
                "order_id": order_id,
                "portfolio_id": str(portfolio_id),
                "action": action,
                "quantity": str(quantity),
            },
        )
        return execution

    async def _transition(
        self,
        execution_id: UUID,
        trigger: str,
        reason: str | None = None,
        actor_id: UUID | None = None,
        **kwargs: Any,
    ) -> Execution:
        execution = await self._session.get(Execution, execution_id)
        if execution is None:
            raise LookupError(f"Execution {execution_id} not found")

        model = ExecutionMachineModel(
            id=execution.id,  # type: ignore[arg-type]
            state=execution.state,  # type: ignore[arg-type]
            available_balance=float(execution.available_balance or 0),
            required_amount=float(execution.required_amount or 0),
            alert_triggered=execution.alert_triggered,  # type: ignore[arg-type]
        )
        machine = create_execution_machine(model)

        try:
            new_state = machine.apply(trigger, reason=reason, **kwargs)
        except InvalidTransitionError as exc:
            raise InvalidTransitionError(str(exc)) from exc

        execution.state = new_state  # type: ignore[assignment]
        execution.available_balance = Decimal(str(model.available_balance))  # type: ignore[assignment]
        execution.required_amount = Decimal(str(model.required_amount))  # type: ignore[assignment]
        execution.alert_triggered = model.alert_triggered  # type: ignore[assignment]

        await self._audit.log(
            actor_id=actor_id,
            action=f"execution:{trigger}",
            resource_type="execution",
            resource_id=execution_id,
            changes={
                "from_state": model.state_history[-2].from_state if len(model.state_history) >= 2 else None,
                "to_state": new_state,
            },
        )
        return execution

    async def validate_execution(
        self,
        execution_id: UUID,
        available_balance: Decimal | None = None,
        required_amount: Decimal | None = None,
        actor_id: UUID | None = None,
    ) -> Execution:
        execution = await self._session.get(Execution, execution_id)
        if execution is None:
            raise LookupError(f"Execution {execution_id} not found")

        if available_balance is not None:
            execution.available_balance = available_balance  # type: ignore[assignment]
        if required_amount is not None:
            execution.required_amount = required_amount  # type: ignore[assignment]

        return await self._transition(execution_id, "run_validation", actor_id=actor_id)

    async def queue_execution(
        self,
        execution_id: UUID,
        actor_id: UUID | None = None,
    ) -> Execution:
        return await self._transition(execution_id, "queue", actor_id=actor_id)

    async def dispatch_execution(
        self,
        execution_id: UUID,
        actor_id: UUID | None = None,
    ) -> Execution:
        execution = await self._session.get(Execution, execution_id)
        if execution is None:
            raise LookupError(f"Execution {execution_id} not found")

        if execution.available_balance < execution.required_amount:
            raise InsufficientBalanceError(
                f"Insufficient balance: {execution.available_balance} available, {execution.required_amount} required"
            )

        result = await self._transition(execution_id, "dispatch", actor_id=actor_id)
        result.dispatched_at = datetime.now(UTC)  # type: ignore[assignment]

        # write to operation dispatch outbox for broker/exchange
        outbox = OperationDispatchOutbox(
            organization_id=UUID(int=0),
            operation_id=execution_id,
            topic="execution.dispatch",
            state="pending",
        )
        self._session.add(outbox)

        await self._audit.log(
            actor_id=actor_id,
            action="execution:dispatch",
            resource_type="execution_dispatch_outbox",
            resource_id=outbox.id,  # type: ignore[arg-type]
            changes={"execution_id": str(execution_id)},
        )
        return result

    async def confirm_execution(
        self,
        execution_id: UUID,
        filled_quantity: Decimal,
        avg_price: Decimal,
        actor_id: UUID | None = None,
    ) -> Execution:
        result = await self._transition(execution_id, "confirm", actor_id=actor_id)
        result.filled_quantity = filled_quantity  # type: ignore[assignment]
        result.avg_price = avg_price  # type: ignore[assignment]
        result.confirmed_at = datetime.now(UTC)  # type: ignore[assignment]

        await self._audit.log(
            actor_id=actor_id,
            action="execution:confirm",
            resource_type="execution",
            resource_id=execution_id,
            changes={"filled_quantity": str(filled_quantity), "avg_price": str(avg_price)},
        )
        return result

    async def fail_execution(
        self,
        execution_id: UUID,
        reason: str,
        actor_id: UUID | None = None,
    ) -> Execution:
        result = await self._transition(execution_id, "fail", reason=reason, actor_id=actor_id)
        result.reason = reason  # type: ignore[assignment]

        await self._audit.log(
            actor_id=actor_id,
            action="execution:fail",
            resource_type="execution",
            resource_id=execution_id,
            changes={"reason": reason},
        )
        return result

    async def settle_execution(
        self,
        execution_id: UUID,
        actor_id: UUID | None = None,
    ) -> Execution:
        execution = await self._session.get(Execution, execution_id)
        if execution is None:
            raise LookupError(f"Execution {execution_id} not found")

        if execution.state == "settled":
            return execution

        result = await self._transition(execution_id, "settle", actor_id=actor_id)
        result.settled_at = datetime.now(UTC)  # type: ignore[assignment]
        return result

    async def get_execution(self, execution_id: UUID) -> dict[str, Any]:
        execution = await self._session.get(Execution, execution_id)
        if execution is None:
            raise LookupError(f"Execution {execution_id} not found")

        model = ExecutionMachineModel(
            state=execution.state,  # type: ignore[arg-type]
            available_balance=float(execution.available_balance or 0),
            required_amount=float(execution.required_amount or 0),
            alert_triggered=execution.alert_triggered,  # type: ignore[arg-type]
        )
        machine = create_execution_machine(model)

        return {
            "id": str(execution.id),
            "order_id": execution.order_id,
            "portfolio_id": str(execution.portfolio_id),
            "action": execution.action,
            "quantity": str(execution.quantity),
            "price_limit": str(execution.price_limit) if execution.price_limit else None,
            "state": execution.state,
            "available_balance": str(execution.available_balance),
            "required_amount": str(execution.required_amount),
            "alert_triggered": execution.alert_triggered,
            "filled_quantity": str(execution.filled_quantity) if execution.filled_quantity else None,
            "avg_price": str(execution.avg_price) if execution.avg_price else None,
            "reason": execution.reason,
            "dispatched_at": execution.dispatched_at.isoformat() if execution.dispatched_at else None,
            "confirmed_at": execution.confirmed_at.isoformat() if execution.confirmed_at else None,
            "settled_at": execution.settled_at.isoformat() if execution.settled_at else None,
            "created_at": execution.created_at.isoformat() if execution.created_at else None,
            "updated_at": execution.updated_at.isoformat() if execution.updated_at else None,
            "allowed_transitions": machine.get_allowed_transitions(),
            "state_history": machine.get_state_history(),
        }

    async def list_executions(
        self,
        portfolio_id: UUID | None = None,
        state: str | None = None,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Execution], int]:
        stmt = sa.select(Execution)

        if portfolio_id:
            stmt = stmt.where(Execution.portfolio_id == portfolio_id)
        if state:
            stmt = stmt.where(Execution.state == state)
        if from_date:
            stmt = stmt.where(Execution.created_at >= from_date)
        if to_date:
            stmt = stmt.where(Execution.created_at <= to_date)

        count_stmt = sa.select(sa.func.count()).select_from(stmt.subquery())
        total = await self._session.scalar(count_stmt) or 0

        stmt = stmt.order_by(Execution.created_at.desc()).offset(offset).limit(limit)
        result = await self._session.execute(stmt)
        rows = list(result.scalars().all())
        return rows, total
