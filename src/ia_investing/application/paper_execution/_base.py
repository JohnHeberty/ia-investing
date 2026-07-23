from __future__ import annotations

from decimal import Decimal
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.agents import AuditLog
from database.models.paper_execution import PaperKillSwitch, PaperOrder, ReconciliationBreak, TradeIntent
from database.models.portfolio_domain import ModelPortfolio
from database.models.research import DomainOutboxEvent
from ia_investing.domain.paper_execution import ExecutionConfiguration


async def require_operations_enabled(session: AsyncSession, portfolio: ModelPortfolio) -> None:
    kill_switch = await session.scalar(
        sa.select(sa.func.count(PaperKillSwitch.id)).where(
            PaperKillSwitch.organization_id == portfolio.organization_id,
            PaperKillSwitch.active.is_(True),
            sa.or_(PaperKillSwitch.portfolio_id.is_(None), PaperKillSwitch.portfolio_id == portfolio.id),
        )
    )
    blocking_break = await session.scalar(
        sa.select(sa.func.count(ReconciliationBreak.id)).where(
            ReconciliationBreak.portfolio_id == portfolio.id,
            ReconciliationBreak.blocking.is_(True),
            ReconciliationBreak.status.in_(("open", "acknowledged")),
        )
    )
    if kill_switch:
        raise PermissionError("paper kill switch is active")
    if blocking_break:
        raise PermissionError("critical reconciliation break blocks paper execution")


def configuration(model: object) -> ExecutionConfiguration:
    payload = model.configuration  # type: ignore[attr-defined]
    return ExecutionConfiguration(
        version=f"{model.logical_id}:{model.version}",  # type: ignore[attr-defined]
        lot_size=Decimal(str(payload["lot_size"])),
        max_participation=Decimal(str(payload["max_participation"])),
        spread_bps=Decimal(str(payload["spread_bps"])),
        impact_bps_at_full_participation=Decimal(str(payload["impact_bps_at_full_participation"])),
        fee_bps=Decimal(str(payload["fee_bps"])),
        tax_bps=Decimal(str(payload["tax_bps"])),
        latency_ms=int(payload["latency_ms"]),
    )


def record(
    session: AsyncSession,
    intent: TradeIntent,
    event_type: str,
    action: str,
    actor: str,
    correlation_id: UUID,
) -> None:
    event_id = uuid4()
    session.add(
        DomainOutboxEvent(
            aggregate_type="paper_trade_intent",
            aggregate_id=intent.id,
            aggregate_version=1,
            event_type=event_type,
            payload={"status": intent.status, "environment": "paper"},
            correlation_id=correlation_id,
            idempotency_key=f"paper-intent:{intent.id}:{event_type}:{event_id}",
        )
    )
    audit_entity(
        session,
        action,
        "paper_trade_intent",
        intent.id,
        actor,
        intent.organization_id,
        correlation_id,
        {"event_type": event_type, "status": intent.status, "environment": "paper"},
    )


def record_order(
    session: AsyncSession,
    order: PaperOrder,
    event_type: str,
    action: str,
    actor: str,
    organization_id: UUID,
    correlation_id: UUID,
) -> None:
    event_id = uuid4()
    session.add(
        DomainOutboxEvent(
            aggregate_type="paper_order",
            aggregate_id=order.id,
            aggregate_version=1,
            event_type=event_type,
            payload={
                "status": order.status,
                "environment": "paper",
                "filled_quantity": str(order.filled_quantity),
                "requested_quantity": str(order.requested_quantity),
            },
            correlation_id=correlation_id,
            idempotency_key=f"paper-order:{order.id}:{event_type}:{event_id}",
        )
    )
    audit_entity(
        session,
        action,
        "paper_order",
        order.id,
        actor,
        organization_id,
        correlation_id,
        {"event_type": event_type, "status": order.status, "environment": "paper"},
    )


def audit_entity(
    session: AsyncSession,
    action: str,
    entity_type: str,
    entity_id: UUID,
    actor: str,
    organization_id: UUID,
    correlation_id: UUID,
    details: dict[str, object],
) -> None:
    session.add(
        AuditLog(
            actor_type="human",
            actor_id=actor,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            correlation_id=correlation_id,
            details={**details, "organization_id": str(organization_id)},
        )
    )
