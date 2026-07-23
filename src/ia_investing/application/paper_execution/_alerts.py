from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.paper_execution import OperationalAlert, PaperKillSwitch
from database.models.portfolio_domain import ModelPortfolio
from ia_investing.domain.identity import InstitutionalAccessContext, ensure_four_eyes

from ._base import audit_entity


class AlertService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def acknowledge_alert(
        self,
        alert_id: UUID,
        *,
        context: InstitutionalAccessContext,
        correlation_id: UUID,
    ) -> OperationalAlert:
        if "alerts:acknowledge" not in context.permissions:
            raise PermissionError("permission required: alerts:acknowledge")
        alert = await self.session.get(OperationalAlert, alert_id, with_for_update=True)
        if alert is None or alert.organization_id != context.organization_id:
            raise LookupError("operational alert not found")
        if alert.status == "open":
            alert.status = "acknowledged"
            alert.acknowledged_by = context.subject
            alert.acknowledged_at = datetime.now(UTC)
            audit_entity(
                self.session,
                "operational_alert.acknowledge",
                "operational_alert",
                alert.id,
                context.subject,
                context.organization_id,
                correlation_id,
                {"deduplication_key": alert.deduplication_key},
            )
        return alert

    async def resolve_alert(
        self,
        alert_id: UUID,
        *,
        resolution: dict[str, object],
        context: InstitutionalAccessContext,
        correlation_id: UUID,
    ) -> OperationalAlert:
        if "alerts:acknowledge" not in context.permissions:
            raise PermissionError("permission required: alerts:acknowledge")
        alert = await self.session.get(OperationalAlert, alert_id, with_for_update=True)
        if alert is None or alert.organization_id != context.organization_id:
            raise LookupError("operational alert not found")
        if alert.status in ("resolved",):
            return alert
        if alert.status == "open":
            alert.status = "acknowledged"
            alert.acknowledged_by = context.subject
            alert.acknowledged_at = datetime.now(UTC)
        alert.status = "resolved"
        alert.payload = {**alert.payload, "resolution": resolution, "resolved_by": context.subject}
        audit_entity(
            self.session,
            "operational_alert.resolve",
            "operational_alert",
            alert.id,
            context.subject,
            context.organization_id,
            correlation_id,
            {"deduplication_key": alert.deduplication_key, "resolution": resolution},
        )
        return alert

    async def list_alerts(
        self,
        context: InstitutionalAccessContext,
        *,
        status: str | None = None,
        severity: str | None = None,
        alert_type: str | None = None,
        portfolio_id: UUID | None = None,
        limit: int = 50,
    ) -> list[OperationalAlert]:
        if "alerts:read" not in context.permissions:
            raise PermissionError("permission required: alerts:read")
        stmt = sa.select(OperationalAlert).where(OperationalAlert.organization_id == context.organization_id)
        if status is not None:
            stmt = stmt.where(OperationalAlert.status == status)
        if severity is not None:
            stmt = stmt.where(OperationalAlert.severity == severity)
        if alert_type is not None:
            stmt = stmt.where(OperationalAlert.alert_type == alert_type)
        if portfolio_id is not None:
            stmt = stmt.where(OperationalAlert.portfolio_id == portfolio_id)
        stmt = stmt.order_by(OperationalAlert.created_at.desc()).limit(limit)
        return list((await self.session.scalars(stmt)).all())

    async def activate_kill_switch(
        self,
        *,
        portfolio_id: UUID | None,
        reason: str,
        context: InstitutionalAccessContext,
        correlation_id: UUID,
    ) -> PaperKillSwitch:
        if "paper_orders:kill" not in context.permissions:
            raise PermissionError("permission required: paper_orders:kill")
        if portfolio_id is not None:
            portfolio = await self.session.get(ModelPortfolio, portfolio_id)
            if portfolio is None or portfolio.organization_id != context.organization_id:
                raise LookupError("portfolio not found")
        existing = await self.session.scalar(
            sa.select(PaperKillSwitch).where(
                PaperKillSwitch.organization_id == context.organization_id,
                PaperKillSwitch.portfolio_id == portfolio_id,
                PaperKillSwitch.active.is_(True),
            )
        )
        if existing is not None:
            return existing
        switch = PaperKillSwitch(
            organization_id=context.organization_id,
            portfolio_id=portfolio_id,
            active=True,
            reason=reason,
            activated_by=context.subject,
        )
        self.session.add(switch)
        await self.session.flush()
        audit_entity(
            self.session,
            "paper_kill_switch.activate",
            "paper_kill_switch",
            switch.id,
            context.subject,
            context.organization_id,
            correlation_id,
            {"portfolio_id": str(portfolio_id) if portfolio_id else None, "reason": reason},
        )
        return switch

    async def release_kill_switch(
        self,
        switch_id: UUID,
        *,
        context: InstitutionalAccessContext,
        correlation_id: UUID,
    ) -> PaperKillSwitch:
        if "paper_orders:kill" not in context.permissions:
            raise PermissionError("permission required: paper_orders:kill")
        switch = await self.session.get(PaperKillSwitch, switch_id, with_for_update=True)
        if switch is None or switch.organization_id != context.organization_id:
            raise LookupError("paper kill switch not found")
        if switch.active:
            ensure_four_eyes(switch.activated_by, context.subject)
            switch.active = False
            switch.released_by = context.subject
            switch.released_at = datetime.now(UTC)
            audit_entity(
                self.session,
                "paper_kill_switch.release",
                "paper_kill_switch",
                switch.id,
                context.subject,
                context.organization_id,
                correlation_id,
                {"activated_by": switch.activated_by},
            )
        return switch
