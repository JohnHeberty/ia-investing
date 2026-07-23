from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.portfolio import Position
from database.models.portfolio_mandates import ModelPortfolio
from database.models.rebalance import DriftSnapshot, RebalanceProposal, RebalanceTrade
from ia_investing.domain.portfolio_machine import (
    PortfolioMachineModel,
    create_portfolio_machine,
)

TRANSACTION_COST_BPS = Decimal("0.0010")
TAX_RATE = Decimal("0.0003")
MIN_TRADE_SIZE_PCT = Decimal("0.001")
MAX_CONCENTRATION_PCT = Decimal("0.25")
MAX_SECTOR_PCT = Decimal("0.40")
MIN_LIQUIDITY_THRESHOLD = Decimal("100000")


class RebalanceService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def calculate_rebalance(
        self,
        portfolio_id: uuid.UUID,
        target_allocations: dict[str, float],
    ) -> list[dict[str, Any]]:
        portfolio = await self._get_portfolio(portfolio_id)
        positions = await self._get_positions(portfolio_id)
        total_nav = float(portfolio.get("nav", 0)) or 1.0

        current: dict[str, dict[str, Any]] = {}
        for pos in positions:
            ticker = pos.get("ticker_symbol", "")
            weight = Decimal(str(pos.get("weight_pct", 0) or 0))
            value = weight * Decimal(str(total_nav))
            current[ticker] = {"weight": weight, "value": value}

        trades: list[dict[str, Any]] = []
        all_tickers = set(current) | set(target_allocations)

        for ticker in all_tickers:
            cur_weight = current.get(ticker, {}).get("weight", Decimal("0"))
            tgt_pct = Decimal(str(target_allocations.get(ticker, 0)))
            delta = tgt_pct - cur_weight
            if abs(delta) < MIN_TRADE_SIZE_PCT:
                continue

            estimated_value = abs(delta) * Decimal(str(total_nav))
            fees = estimated_value * TRANSACTION_COST_BPS if delta > 0 else Decimal("0")
            taxes = estimated_value * TAX_RATE if delta > 0 else Decimal("0")

            trades.append(
                {
                    "ticker": ticker,
                    "current_weight": float(cur_weight),
                    "target_weight": float(tgt_pct),
                    "delta": float(delta),
                    "estimated_value": float(estimated_value),
                    "estimated_fees": float(fees),
                    "estimated_taxes": float(taxes),
                    "side": "buy" if delta > 0 else "sell",
                }
            )

        trades.sort(key=lambda t: abs(t["delta"]), reverse=True)
        return trades

    async def propose_rebalance(
        self,
        portfolio_id: uuid.UUID,
        target_allocations: dict[str, float],
        rationale: str,
        created_by: str,
    ) -> dict[str, Any]:
        positions = await self._get_positions(portfolio_id)

        current_allocations: dict[str, float] = {}
        for pos in positions:
            ticker = pos.get("ticker_symbol", "")
            weight = float(pos.get("weight_pct", 0) or 0)
            current_allocations[ticker] = weight

        drift = self._compute_drift(current_allocations, target_allocations)
        compliance = self._check_compliance(target_allocations)

        trades = await self.calculate_rebalance(portfolio_id, target_allocations)

        proposal = RebalanceProposal(
            portfolio_id=portfolio_id,
            status="draft",
            target_allocations={k: float(v) for k, v in target_allocations.items()},
            current_allocations=current_allocations,
            drift_analysis={
                "max_drift": float(drift["max_drift"]),
                "total_drift": float(drift["total_drift"]),
                "items": drift["items"],
                "compliance": compliance,
            },
            rationale=rationale,
            created_by=created_by,
        )
        self._session.add(proposal)
        await self._session.flush()

        for i, trade in enumerate(trades):
            self._session.add(
                RebalanceTrade(
                    proposal_id=proposal.id,
                    ticker=trade["ticker"],
                    side=trade["side"],
                    current_weight=Decimal(str(trade["current_weight"])),
                    target_weight=Decimal(str(trade["target_weight"])),
                    delta=Decimal(str(trade["delta"])),
                    estimated_value=Decimal(str(trade["estimated_value"])),
                    estimated_fees=Decimal(str(trade.get("estimated_fees", 0))),
                    estimated_taxes=Decimal(str(trade.get("estimated_taxes", 0))),
                    status="pending",
                    execution_order=i + 1,
                )
            )

        await self._session.flush()
        return await self._proposal_to_dict(proposal.id)

    async def approve_rebalance(
        self,
        proposal_id: uuid.UUID,
        approver_id: str,
        notes: str | None = None,
    ) -> dict[str, Any]:
        proposal = await self._get_proposal(proposal_id)
        if proposal.status != "draft":
            raise ValueError(f"Cannot approve proposal with status '{proposal.status}'")

        machine = self._get_portfolio_machine(proposal.portfolio_id)
        machine.approve_rebalance()
        await self._update_portfolio_state(proposal.portfolio_id, machine.model.state)

        proposal.status = "approved"
        proposal.approved_by = approver_id
        proposal.approval_notes = notes
        await self._session.flush()
        return await self._proposal_to_dict(proposal_id)

    async def execute_rebalance_step(
        self,
        proposal_id: uuid.UUID,
        trade_ids: list[uuid.UUID],
    ) -> dict[str, Any]:
        proposal = await self._get_proposal(proposal_id)
        if proposal.status not in ("approved", "in_progress"):
            raise ValueError(f"Cannot execute trades on proposal with status '{proposal.status}'")

        if proposal.status == "approved":
            machine = self._get_portfolio_machine(proposal.portfolio_id)
            machine.approve_rebalance()
            await self._update_portfolio_state(proposal.portfolio_id, "rebalancing")
            proposal.status = "in_progress"

        result = await self._session.execute(
            sa.select(RebalanceTrade).where(
                RebalanceTrade.id.in_(trade_ids),
                RebalanceTrade.proposal_id == proposal_id,
                RebalanceTrade.status == "pending",
            )
        )
        trades = list(result.scalars().all())

        now = datetime.now(UTC)
        for trade in trades:
            trade.status = "executed"
            trade.executed_at = now

        await self._session.flush()
        return await self._proposal_to_dict(proposal_id)

    async def complete_rebalance(self, proposal_id: uuid.UUID) -> dict[str, Any]:
        proposal = await self._get_proposal(proposal_id)
        if proposal.status not in ("approved", "in_progress"):
            raise ValueError(f"Cannot complete proposal with status '{proposal.status}'")

        machine = self._get_portfolio_machine(proposal.portfolio_id)
        machine.approve_rebalance()
        await self._update_portfolio_state(proposal.portfolio_id, "monitoring")

        proposal.status = "completed"
        proposal.completed_at = datetime.now(UTC)
        await self._session.flush()
        return await self._proposal_to_dict(proposal_id)

    async def cancel_rebalance(
        self,
        proposal_id: uuid.UUID,
        reason: str,
    ) -> dict[str, Any]:
        proposal = await self._get_proposal(proposal_id)
        if proposal.status in ("completed", "cancelled"):
            raise ValueError(f"Cannot cancel proposal with status '{proposal.status}'")

        proposal.status = "cancelled"
        proposal.cancelled_reason = reason
        proposal.cancelled_at = datetime.now(UTC)
        await self._session.flush()
        return await self._proposal_to_dict(proposal_id)

    async def get_rebalance_status(self, proposal_id: uuid.UUID) -> dict[str, Any]:
        await self._get_proposal(proposal_id)
        result = await self._session.execute(sa.select(RebalanceTrade).where(RebalanceTrade.proposal_id == proposal_id))
        trades = list(result.scalars().all())
        total = len(trades)
        executed = sum(1 for t in trades if t.status == "executed")
        skipped = sum(1 for t in trades if t.status == "skipped")
        failed = sum(1 for t in trades if t.status == "failed")

        base = await self._proposal_to_dict(proposal_id)
        base["execution_progress"] = {
            "total": total,
            "executed": executed,
            "skipped": skipped,
            "failed": failed,
            "percent_complete": round(executed / total * 100, 1) if total > 0 else 0,
        }
        return base

    async def get_drift_summary(self, portfolio_id: uuid.UUID) -> dict[str, Any]:
        portfolio = await self._get_portfolio(portfolio_id)
        positions = await self._get_positions(portfolio_id)

        current_allocations: dict[str, float] = {}
        for pos in positions:
            ticker = pos.get("ticker_symbol", "")
            weight = float(pos.get("weight_pct", 0) or 0)
            current_allocations[ticker] = weight

        latest_snapshot = await self._session.execute(
            sa.select(DriftSnapshot)
            .where(DriftSnapshot.portfolio_id == portfolio_id)
            .order_by(DriftSnapshot.snapshot_date.desc())
            .limit(1)
        )
        snapshot = latest_snapshot.scalar_one_or_none()
        target_allocations = snapshot.allocations if snapshot else {}

        drift = self._compute_drift(current_allocations, target_allocations)  # type: ignore[arg-type]
        return {
            "portfolio_id": str(portfolio_id),
            "portfolio_name": portfolio.get("name", ""),
            "snapshot_date": snapshot.snapshot_date.isoformat() if snapshot else None,
            "current_allocations": current_allocations,
            "target_allocations": target_allocations,
            "max_drift": float(drift["max_drift"]),
            "total_drift": float(drift["total_drift"]),
            "items": drift["items"],
        }

    async def get_history(self, portfolio_id: uuid.UUID) -> list[dict[str, Any]]:
        result = await self._session.execute(
            sa.select(RebalanceProposal)
            .where(RebalanceProposal.portfolio_id == portfolio_id)
            .order_by(RebalanceProposal.created_at.desc())
        )
        proposals = list(result.scalars().all())
        return [await self._proposal_to_dict(p.id) for p in proposals]

    async def list_proposals(
        self,
        status: str | None = None,
        portfolio_id: uuid.UUID | None = None,
    ) -> list[dict[str, Any]]:
        stmt = sa.select(RebalanceProposal).order_by(RebalanceProposal.created_at.desc())
        if status:
            stmt = stmt.where(RebalanceProposal.status == status)
        if portfolio_id:
            stmt = stmt.where(RebalanceProposal.portfolio_id == portfolio_id)

        result = await self._session.execute(stmt)
        proposals = list(result.scalars().all())
        return [await self._proposal_to_dict(p.id) for p in proposals]

    async def _get_portfolio(self, portfolio_id: uuid.UUID) -> dict[str, Any]:
        stmt = sa.select(ModelPortfolio).where(ModelPortfolio.id == portfolio_id)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            raise LookupError(f"Portfolio {portfolio_id} not found")
        return {
            "id": str(model.id),
            "name": model.name,
            "state": model.state,
            "nav": 1_000_000.0,
        }

    async def _get_positions(self, portfolio_id: uuid.UUID) -> list[dict[str, Any]]:
        stmt = sa.select(Position).where(Position.portfolio_id == portfolio_id)
        result = await self._session.execute(stmt)
        positions = list(result.scalars().all())
        return [
            {
                "ticker_symbol": p.ticker_symbol,
                "weight_pct": float(p.weight_pct) if p.weight_pct else 0,
                "quantity": float(p.quantity) if p.quantity else 0,
            }
            for p in positions
        ]

    async def _get_proposal(self, proposal_id: uuid.UUID) -> RebalanceProposal:
        stmt = sa.select(RebalanceProposal).where(RebalanceProposal.id == proposal_id)
        result = await self._session.execute(stmt)
        proposal = result.scalar_one_or_none()
        if proposal is None:
            raise LookupError(f"Rebalance proposal {proposal_id} not found")
        return proposal

    async def _proposal_to_dict(self, proposal_id: uuid.UUID) -> dict[str, Any]:
        proposal = await self._get_proposal(proposal_id)
        result = await self._session.execute(
            sa.select(RebalanceTrade)
            .where(RebalanceTrade.proposal_id == proposal_id)
            .order_by(RebalanceTrade.execution_order)
        )
        trades = list(result.scalars().all())

        return {
            "id": str(proposal.id),
            "portfolio_id": str(proposal.portfolio_id),
            "status": proposal.status,
            "target_allocations": proposal.target_allocations,
            "current_allocations": proposal.current_allocations,
            "drift_analysis": proposal.drift_analysis,
            "rationale": proposal.rationale,
            "created_by": proposal.created_by,
            "approved_by": proposal.approved_by,
            "approval_notes": proposal.approval_notes,
            "cancelled_reason": proposal.cancelled_reason,
            "created_at": proposal.created_at.isoformat() if proposal.created_at else None,
            "updated_at": proposal.updated_at.isoformat() if proposal.updated_at else None,
            "completed_at": proposal.completed_at.isoformat() if proposal.completed_at else None,
            "cancelled_at": proposal.cancelled_at.isoformat() if proposal.cancelled_at else None,
            "trades": [
                {
                    "id": str(t.id),
                    "ticker": t.ticker,
                    "side": t.side,
                    "current_weight": float(t.current_weight),
                    "target_weight": float(t.target_weight),
                    "delta": float(t.delta),
                    "estimated_value": float(t.estimated_value),
                    "estimated_fees": float(t.estimated_fees) if t.estimated_fees else None,
                    "estimated_taxes": float(t.estimated_taxes) if t.estimated_taxes else None,
                    "status": t.status,
                    "execution_order": t.execution_order,
                    "executed_at": t.executed_at.isoformat() if t.executed_at else None,
                    "fill_price": float(t.fill_price) if t.fill_price else None,
                    "fill_quantity": float(t.fill_quantity) if t.fill_quantity else None,
                }
                for t in trades
            ],
        }

    def _compute_drift(
        self,
        current: dict[str, float],
        target: dict[str, float],
    ) -> dict[str, Any]:
        all_tickers = set(current) | set(target)
        items: list[dict[str, Any]] = []
        max_drift = Decimal("0")
        total_drift = Decimal("0")

        for ticker in sorted(all_tickers):
            cur = Decimal(str(current.get(ticker, 0)))
            tgt = Decimal(str(target.get(ticker, 0)))
            drift_val = abs(tgt - cur)
            if drift_val > max_drift:
                max_drift = drift_val
            total_drift += drift_val
            severity = "green" if drift_val < Decimal("0.01") else "yellow" if drift_val < Decimal("0.03") else "red"

            items.append(
                {
                    "ticker": ticker,
                    "current_weight": float(cur),
                    "target_weight": float(tgt),
                    "drift": float(drift_val),
                    "severity": severity,
                }
            )

        items.sort(key=lambda i: i["drift"], reverse=True)
        return {
            "max_drift": float(max_drift),
            "total_drift": float(total_drift),
            "items": items,
        }

    def _check_compliance(self, allocations: dict[str, float]) -> dict[str, Any]:
        issues: list[str] = []
        for ticker, alloc in allocations.items():
            if Decimal(str(alloc)) > MAX_CONCENTRATION_PCT:
                issues.append(f"{ticker}: concentration {alloc:.1%} exceeds {float(MAX_CONCENTRATION_PCT):.0%} limit")
        return {
            "passed": len(issues) == 0,
            "issues": issues,
            "concentration_limit": float(MAX_CONCENTRATION_PCT),
            "sector_limit": float(MAX_SECTOR_PCT),
        }

    def _get_portfolio_machine(self, portfolio_id: uuid.UUID) -> Any:
        return create_portfolio_machine(
            PortfolioMachineModel(state="monitoring", nav=1_000_000.0, compliance_passed=True)
        )

    async def _update_portfolio_state(self, portfolio_id: uuid.UUID, state: str) -> None:
        stmt = sa.update(ModelPortfolio).where(ModelPortfolio.id == portfolio_id).values(state=state)
        await self._session.execute(stmt)
