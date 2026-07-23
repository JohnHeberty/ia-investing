from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.paper_execution import ChallengerEvaluation, PaperPostMortem
from database.models.portfolio_domain import InstitutionalPortfolioVersion, ModelPortfolio
from ia_investing.domain.identity import InstitutionalAccessContext, ensure_four_eyes
from ia_investing.domain.paper_execution import (
    immutable_report_hash,
    validate_challenger_comparison,
    validate_post_mortem_lineage,
)

from ._base import audit_entity


class EvaluationService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_post_mortem(
        self,
        portfolio_id: UUID,
        *,
        period_start: datetime,
        period_end: datetime,
        expected: dict[str, object],
        realized: dict[str, object],
        attribution: dict[str, object],
        findings: list[dict[str, object]],
        dissent: list[dict[str, object]],
        context: InstitutionalAccessContext,
        correlation_id: UUID,
    ) -> PaperPostMortem:
        if "postmortem:write" not in context.permissions:
            raise PermissionError("permission required: postmortem:write")
        portfolio = await self.session.get(ModelPortfolio, portfolio_id)
        if portfolio is None or portfolio.organization_id != context.organization_id:
            raise LookupError("portfolio not found")
        if period_start.tzinfo is None or period_end.tzinfo is None or period_end <= period_start:
            raise ValueError("post-mortem period must be a valid timezone-aware window")
        validate_post_mortem_lineage(attribution)
        version = (
            await self.session.scalar(
                sa.select(sa.func.max(PaperPostMortem.version)).where(PaperPostMortem.portfolio_id == portfolio.id)
            )
            or 0
        ) + 1
        payload = {
            "portfolio_id": str(portfolio.id),
            "version": version,
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
            "expected": expected,
            "realized": realized,
            "attribution": attribution,
            "findings": findings,
            "dissent": dissent,
        }
        row = PaperPostMortem(
            organization_id=context.organization_id,
            portfolio_id=portfolio.id,
            version=version,
            period_start=period_start,
            period_end=period_end,
            expected=expected,
            realized=realized,
            attribution=attribution,
            findings=findings,
            dissent=dissent,
            content_sha256=immutable_report_hash(payload),
            created_by=context.subject,
        )
        self.session.add(row)
        await self.session.flush()
        audit_entity(
            self.session,
            "paper_post_mortem.create",
            "paper_post_mortem",
            row.id,
            context.subject,
            context.organization_id,
            correlation_id,
            {"version": version, "content_sha256": row.content_sha256},
        )
        return row

    async def list_post_mortems(
        self,
        portfolio_id: UUID,
        *,
        limit: int = 50,
    ) -> list[PaperPostMortem]:
        stmt = sa.select(PaperPostMortem).where(PaperPostMortem.portfolio_id == portfolio_id)
        stmt = stmt.order_by(PaperPostMortem.created_at.desc()).limit(limit)
        return list((await self.session.scalars(stmt)).all())

    async def create_challenger_evaluation(
        self,
        *,
        champion_portfolio_id: UUID,
        challenger_portfolio_id: UUID,
        window_start: datetime,
        window_end: datetime,
        methodology_version: str,
        comparison_config: dict[str, object],
        metrics: dict[str, object],
        evidence: dict[str, object],
        context: InstitutionalAccessContext,
        correlation_id: UUID,
    ) -> ChallengerEvaluation:
        if "portfolio:propose" not in context.permissions:
            raise PermissionError("permission required: portfolio:propose")
        champion = await self.session.get(ModelPortfolio, champion_portfolio_id)
        challenger = await self.session.get(ModelPortfolio, challenger_portfolio_id)
        if (
            champion is None
            or challenger is None
            or champion.organization_id != context.organization_id
            or challenger.organization_id != context.organization_id
        ):
            raise LookupError("champion or challenger portfolio not found")
        if champion.mandate_id != challenger.mandate_id:
            raise ValueError("champion and challenger must share the same mandate")
        if champion.environment != "paper" or challenger.environment != "paper":
            raise ValueError("champion/challenger comparison is paper-only")
        comparison_sha256 = validate_challenger_comparison(comparison_config)
        row = ChallengerEvaluation(
            mandate_id=champion.mandate_id,
            champion_portfolio_id=champion.id,
            challenger_portfolio_id=challenger.id,
            window_start=window_start,
            window_end=window_end,
            methodology_version=methodology_version,
            comparison_sha256=comparison_sha256,
            comparison_config=comparison_config,
            metrics=metrics,
            evidence=evidence,
            decision="pending_committee",
            created_by=context.subject,
        )
        self.session.add(row)
        await self.session.flush()
        audit_entity(
            self.session,
            "challenger_evaluation.create",
            "challenger_evaluation",
            row.id,
            context.subject,
            context.organization_id,
            correlation_id,
            {"comparison_sha256": comparison_sha256},
        )
        return row

    async def decide_challenger(
        self,
        evaluation_id: UUID,
        *,
        decision: str,
        context: InstitutionalAccessContext,
        correlation_id: UUID,
    ) -> ChallengerEvaluation:
        if "committee:vote" not in context.permissions:
            raise PermissionError("permission required: committee:vote")
        row = await self.session.get(ChallengerEvaluation, evaluation_id, with_for_update=True)
        if row is None:
            raise LookupError("challenger evaluation not found")
        champion = await self.session.get(ModelPortfolio, row.champion_portfolio_id)
        if champion is None or champion.organization_id != context.organization_id:
            raise LookupError("challenger evaluation not found")
        ensure_four_eyes(row.created_by, context.subject)
        if row.decision != "pending_committee":
            raise ValueError("challenger evaluation has already been decided")
        if decision not in {"retained", "promoted", "rejected"}:
            raise ValueError("invalid challenger decision")
        row.decision = decision
        row.decided_by = context.subject
        row.decided_at = datetime.now(UTC)
        if decision == "promoted":
            challenger_latest = await self.session.scalar(
                sa.select(InstitutionalPortfolioVersion)
                .where(
                    InstitutionalPortfolioVersion.portfolio_id == row.challenger_portfolio_id,
                    InstitutionalPortfolioVersion.status.in_(["approved", "draft"]),
                )
                .order_by(InstitutionalPortfolioVersion.version.desc())
                .limit(1)
            )
            if challenger_latest is not None:
                next_version = challenger_latest.version + 1
                new_version = InstitutionalPortfolioVersion(
                    portfolio_id=row.challenger_portfolio_id,
                    mandate_id=row.mandate_id,
                    version=next_version,
                    as_of=datetime.now(UTC),
                    input_snapshot_sha256=challenger_latest.input_snapshot_sha256,
                    weights_sha256=challenger_latest.weights_sha256,
                    approved_weights=challenger_latest.approved_weights,
                    proposal={
                        "source": "challenger_promotion",
                        "evaluation_id": str(row.id),
                        "promoted_from_version": challenger_latest.version,
                    },
                    decision={
                        "decided_by": context.subject,
                        "decided_at": datetime.now(UTC).isoformat(),
                        "reason": "challenger_promotion",
                    },
                    status="approved",
                    created_by=context.subject,
                    approved_by=context.subject,
                )
                self.session.add(new_version)
                await self.session.flush()
                audit_entity(
                    self.session,
                    "portfolio_version.create",
                    "institutional_portfolio_version",
                    new_version.id,
                    context.subject,
                    context.organization_id,
                    correlation_id,
                    {
                        "version": next_version,
                        "portfolio_id": str(row.challenger_portfolio_id),
                    },
                )
        audit_entity(
            self.session,
            "challenger_evaluation.decide",
            "challenger_evaluation",
            row.id,
            context.subject,
            context.organization_id,
            correlation_id,
            {"decision": decision},
        )
        return row

    async def list_challenger_evaluations(
        self,
        *,
        organization_id: UUID | None = None,
        portfolio_id: UUID | None = None,
        limit: int = 50,
    ) -> list[ChallengerEvaluation]:
        stmt = sa.select(ChallengerEvaluation)
        if organization_id is not None:
            stmt = stmt.join(ModelPortfolio, ModelPortfolio.id == ChallengerEvaluation.champion_portfolio_id)
            stmt = stmt.where(ModelPortfolio.organization_id == organization_id)
        if portfolio_id is not None:
            stmt = stmt.where(ChallengerEvaluation.champion_portfolio_id == portfolio_id)
        stmt = stmt.order_by(ChallengerEvaluation.window_end.desc()).limit(limit)
        return list((await self.session.scalars(stmt)).all())
