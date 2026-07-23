from __future__ import annotations

from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.portfolio_domain import (
    InstitutionalPortfolioVersion,
    InstitutionalRiskSnapshot,
    ModelPortfolio,
    OptimizationRun,
    PortfolioApprovalEvidence,
    PortfolioVersionThesis,
    PortfolioVersionValuation,
    RiskBreach,
)
from ia_investing.domain.identity import InstitutionalAccessContext, ResourceAttributes, authorize, ensure_four_eyes
from ia_investing.domain.institutional_portfolio import canonical_hash


class ApprovalService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def approve_version(
        self,
        version_id: UUID,
        optimization_run_id: UUID,
        risk_snapshot_id: UUID,
        decision: dict[str, object],
        context: InstitutionalAccessContext,
    ) -> InstitutionalPortfolioVersion:
        version = await self.session.get(InstitutionalPortfolioVersion, version_id, with_for_update=True)
        if version is None:
            raise LookupError("portfolio version not found")
        portfolio = await self.session.get(ModelPortfolio, version.portfolio_id)
        if portfolio is None:
            raise RuntimeError("portfolio version references missing portfolio")
        authorize(context, "portfolio:approve", ResourceAttributes(portfolio.organization_id, portfolio.owner_team_id))
        ensure_four_eyes(version.created_by, context.subject)
        if version.status != "proposed":
            raise ValueError("only proposed versions can be approved")
        thesis_count = await self.session.scalar(
            sa.select(sa.func.count())
            .select_from(PortfolioVersionThesis)
            .where(PortfolioVersionThesis.portfolio_version_id == version.id)
        )
        valuation_count = await self.session.scalar(
            sa.select(sa.func.count())
            .select_from(PortfolioVersionValuation)
            .where(PortfolioVersionValuation.portfolio_version_id == version.id)
        )
        if not thesis_count or not valuation_count:
            raise ValueError("approval requires linked thesis and valuation evidence")
        optimization = await self.session.get(OptimizationRun, optimization_run_id)
        if (
            optimization is None
            or optimization.portfolio_id != portfolio.id
            or optimization.as_of != version.as_of
            or optimization.status not in {"optimal", "optimal_inaccurate"}
        ):
            raise ValueError("approval requires a valid optimization for the same portfolio and as_of")
        risk_snapshot = await self.session.get(InstitutionalRiskSnapshot, risk_snapshot_id)
        if risk_snapshot is None or risk_snapshot.portfolio_version_id != version.id:
            raise ValueError("approval requires a risk snapshot for the same portfolio version")
        blocking_breach = await self.session.scalar(
            sa.select(
                sa.exists().where(
                    RiskBreach.risk_snapshot_id == risk_snapshot.id,
                    RiskBreach.limit_type == "hard",
                    RiskBreach.status == "open",
                )
            )
        )
        if blocking_breach:
            raise ValueError("an open hard risk breach blocks portfolio approval")
        votes = decision.get("votes")
        if not isinstance(votes, list):
            raise ValueError("approval votes are required")
        roles: set[str] = set()
        actors: set[str] = set()
        for vote in votes:
            if not isinstance(vote, dict):
                raise ValueError("approval vote must be an object")
            actor = str(vote.get("actor_id", "")).strip()
            role = str(vote.get("role", "")).strip()
            if not actor or actor in actors or actor == version.created_by:
                raise ValueError("approval votes require distinct actors and four-eyes separation")
            if vote.get("decision") not in {"approved", "approved_with_conditions"}:
                raise ValueError("all portfolio approval votes must approve the proposal")
            actors.add(actor)
            roles.add(role)
        if not {"portfolio_manager", "risk_officer"} <= roles:
            raise ValueError("portfolio manager and risk officer votes are required")
        version.status = "approved"
        version.approved_by = context.subject
        evidence_payload = {
            "portfolio_version_id": version.id,
            "optimization_run_id": optimization.id,
            "optimization_input_sha256": optimization.input_sha256,
            "risk_snapshot_id": risk_snapshot.id,
            "risk_input_sha256": risk_snapshot.input_sha256,
        }
        version.decision = {**decision, "evidence": {key: str(value) for key, value in evidence_payload.items()}}
        self.session.add(
            PortfolioApprovalEvidence(
                portfolio_version_id=version.id,
                optimization_run_id=optimization.id,
                risk_snapshot_id=risk_snapshot.id,
                evidence_sha256=canonical_hash(evidence_payload),
            )
        )
        await self.session.flush()
        return version
