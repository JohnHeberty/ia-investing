from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.paper_execution import (
    OperationalAlert,
    PaperFill,
    PaperKillSwitch,
    PaperOrder,
    ReconciliationBreak,
)


class DashboardService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_operational_dashboard(self, organization_id: UUID) -> dict[str, object]:
        now = datetime.now(UTC)

        order_count = await self.session.scalar(
            sa.select(sa.func.count(PaperOrder.id)).where(
                PaperOrder.environment == "paper",
            )
        )
        fill_count = await self.session.scalar(
            sa.select(sa.func.count(PaperFill.id)).where(
                PaperFill.environment == "paper",
            )
        )
        active_breaks = await self.session.scalar(
            sa.select(sa.func.count(ReconciliationBreak.id)).where(
                ReconciliationBreak.status.in_(("open", "acknowledged")),
            )
        )
        blocking_breaks = await self.session.scalar(
            sa.select(sa.func.count(ReconciliationBreak.id)).where(
                ReconciliationBreak.status.in_(("open", "acknowledged")),
                ReconciliationBreak.blocking.is_(True),
            )
        )
        open_alerts = await self.session.scalar(
            sa.select(sa.func.count(OperationalAlert.id)).where(
                OperationalAlert.status == "open",
            )
        )
        critical_alerts = await self.session.scalar(
            sa.select(sa.func.count(OperationalAlert.id)).where(
                OperationalAlert.status == "open",
                OperationalAlert.severity == "critical",
            )
        )
        kill_switches = await self.session.scalar(
            sa.select(sa.func.count(PaperKillSwitch.id)).where(
                PaperKillSwitch.active.is_(True),
            )
        )

        return {
            "as_of": now.isoformat(),
            "orders_total": int(order_count or 0),
            "fills_total": int(fill_count or 0),
            "reconciliation_breaks_open": int(active_breaks or 0),
            "reconciliation_breaks_blocking": int(blocking_breaks or 0),
            "alerts_open": int(open_alerts or 0),
            "alerts_critical": int(critical_alerts or 0),
            "kill_switches_active": int(kill_switches or 0),
            "slo": {
                "execution_success_rate": "N/A (paper environment)",
                "reconciliation_freshness": "daily",
                "alert_acknowledgement_sla": "4h",
                "nav_publication_sla": "T+1",
            },
        }
