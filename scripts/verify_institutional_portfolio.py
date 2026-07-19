from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import sqlalchemy as sa

from database.core import session_scope
from database.models.catalog import Issuer
from database.models.data_foundation import SourceObjectVersion
from database.models.identity import Organization, Team
from database.models.instrument_master import Instrument, Listing
from database.models.market_data import CorporateAction, FxRate, MarketBar, MarketIndex
from database.models.portfolio_domain import InstitutionalRiskPolicy, OptimizationRun, PortfolioApprovalEvidence
from database.models.thesis_domain import ResearchThesisVersion
from database.models.valuation import ValuationRun
from ia_investing.application.institutional_portfolio import InstitutionalPortfolioService
from ia_investing.domain.identity import InstitutionalAccessContext


async def verify() -> None:
    suffix = uuid4().hex[:12]
    async with session_scope() as session:
        organization = Organization(slug=f"verify-{suffix}", display_name="Verification Organization")
        session.add(organization)
        await session.flush()
        team = Team(organization_id=organization.id, slug="investments", display_name="Investments")
        session.add(team)
        benchmark = await session.scalar(sa.select(MarketIndex).where(MarketIndex.code == "IBOV"))
        if benchmark is None:
            benchmark = MarketIndex(
                code=f"VERIFY-{suffix}", name="Verification Benchmark", provider="internal", currency_code="BRL"
            )
            session.add(benchmark)
        await session.flush()
        context = InstitutionalAccessContext(
            "portfolio-author",
            organization.id,
            frozenset({team.id}),
            frozenset(
                {
                    "mandate:create",
                    "portfolio:create",
                    "portfolio:transition",
                    "portfolio:propose",
                    "nav:publish",
                    "risk:assess",
                    "risk:waive",
                }
            ),
            "paper",
        )
        service = InstitutionalPortfolioService(session)
        payload: dict[str, object] = {
            "logical_id": "br-quality",
            "objective": "Capital appreciation with controlled drawdown",
            "strategy_type": "long_only",
            "universe_definition": {"market": "B3", "liquidity_floor": 1_000_000},
            "benchmark_index_id": benchmark.id,
            "benchmark_in_universe": False,
            "base_currency": "BRL",
            "investment_horizon_days": 365,
            "rebalance_policy": {"frequency": "monthly"},
            "risk_budget": {"tracking_error": "0.08"},
            "target_volatility": "0.15",
            "max_drawdown": "0.20",
            "concentration_limits": {"position": "0.10", "sector": "0.30"},
            "factor_limits": {},
            "liquidity_policy": {"days_to_liquidate": 5},
            "min_cash_weight": "0.02",
            "max_cash_weight": "0.10",
            "max_turnover": "0.30",
            "exclusions": {"restricted": []},
            "cost_policy": {"bps": 10},
            "tax_policy": {"jurisdiction": "BR"},
            "approval_policy": {"four_eyes": True},
        }
        mandate = await service.create_mandate(payload, context)
        repeated = await service.create_mandate(payload, context)
        assert mandate.id == repeated.id
        portfolio = await service.create_portfolio(
            mandate_id=mandate.id,
            owner_team_id=team.id,
            name=f"Quality Portfolio {suffix}",
            context=context,
        )
        await service.transition(portfolio.id, "researching", 1, "verification", context)
        assert portfolio.state == "researching" and portfolio.lock_version == 2
        issuer_id = await session.scalar(sa.select(Issuer.id).order_by(Issuer.id).limit(1))
        source_version_id = await session.scalar(
            sa.select(SourceObjectVersion.id).order_by(SourceObjectVersion.id).limit(1)
        )
        if issuer_id is None or source_version_id is None:
            raise RuntimeError("NAV verification requires issuer and source version fixtures")
        thesis_version_id = await session.scalar(sa.select(ResearchThesisVersion.id).order_by(ResearchThesisVersion.id))
        valuation_run_id = await session.scalar(sa.select(ValuationRun.id).order_by(ValuationRun.id))
        if thesis_version_id is None or valuation_run_id is None:
            raise RuntimeError("approval verification requires thesis and valuation fixtures")
        instrument = Instrument(
            issuer_id=issuer_id,
            instrument_type="common_share",
            share_class="ON",
            currency_code="USD",
            is_active=True,
        )
        session.add(instrument)
        await session.flush()
        benchmark.instrument_id = instrument.id
        benchmark.currency_code = "USD"
        listing = Listing(
            instrument_id=instrument.id,
            exchange_code="B3",
            ticker=f"NAV{suffix[:4].upper()}",
            market_segment="verification",
            valid_from=date(2020, 1, 1),
            valid_to=None,
        )
        session.add(listing)
        nav_at = datetime.now(UTC)
        snapshot_at = nav_at - timedelta(days=1)
        await session.flush()
        session.add_all(
            [
                MarketBar(
                    listing_id=listing.id,
                    interval="1d",
                    bar_at=snapshot_at,
                    open_price=Decimal("8"),
                    high_price=Decimal("8"),
                    low_price=Decimal("8"),
                    close_price=Decimal("8"),
                    volume=1_000,
                    source_object_version_id=source_version_id,
                    knowledge_at=snapshot_at,
                ),
                MarketBar(
                    listing_id=listing.id,
                    interval="1d",
                    bar_at=nav_at,
                    open_price=Decimal("10"),
                    high_price=Decimal("10"),
                    low_price=Decimal("10"),
                    close_price=Decimal("10"),
                    volume=1_000,
                    source_object_version_id=source_version_id,
                    knowledge_at=nav_at,
                ),
                FxRate(
                    base_currency="USD",
                    quote_currency="BRL",
                    rate_at=nav_at,
                    rate=Decimal("5"),
                    source_object_version_id=source_version_id,
                    knowledge_at=nav_at,
                ),
                CorporateAction(
                    instrument_id=instrument.id,
                    action_type="split",
                    announcement_date=snapshot_at.date(),
                    ex_date=nav_at.date(),
                    record_date=nav_at.date(),
                    payment_date=None,
                    amount_per_unit=None,
                    ratio=Decimal("2"),
                    currency_code=None,
                    source_object_version_id=source_version_id,
                    knowledge_at=snapshot_at,
                ),
                CorporateAction(
                    instrument_id=instrument.id,
                    action_type="dividend",
                    announcement_date=snapshot_at.date(),
                    ex_date=nav_at.date(),
                    record_date=nav_at.date(),
                    payment_date=nav_at.date(),
                    amount_per_unit=Decimal("1"),
                    ratio=None,
                    currency_code="USD",
                    source_object_version_id=source_version_id,
                    knowledge_at=snapshot_at,
                ),
            ]
        )
        version = await service.create_version(
            portfolio_id=portfolio.id,
            as_of=snapshot_at,
            positions=((instrument.id, Decimal("10"), Decimal("8")),),
            cash=(("USD", Decimal("100")),),
            proposal={"target_weights": {str(instrument.id): "0.625"}},
            thesis_version_ids=(thesis_version_id,),
            valuation_run_ids=(valuation_run_id,),
            context=context,
        )
        publication = await service.publish_nav(version.id, nav_at, context)
        if publication.nav != Decimal("1600"):
            raise AssertionError(f"unexpected PIT/FX/corporate-action NAV: {publication.nav}")
        if publication.gross_pnl != Decimal("700") or publication.benchmark_return != Decimal("0.25"):
            raise AssertionError("PnL or benchmark performance is not reproducible")
        position_detail = publication.input_details["positions"]
        if not isinstance(position_detail, list) or position_detail[0]["ticker"] != listing.ticker:
            raise AssertionError("NAV did not preserve temporal listing provenance")
        republication = await service.publish_nav(version.id, nav_at, context)
        if republication.revision != 2 or republication.input_sha256 != publication.input_sha256:
            raise AssertionError("NAV republication did not preserve a reproducible versioned result")
        policy = InstitutionalRiskPolicy(
            mandate_id=mandate.id,
            version=1,
            methodology_version="risk-verification-v1",
            limits={
                "limits": [{"name": "largest_position_weight", "type": "hard", "maximum": "0.40"}],
                "factor_loadings": {},
                "max_price_age_hours": 24,
            },
            content_sha256="1" * 64,
            status="active",
        )
        session.add(policy)
        await session.flush()
        risk_snapshot, breaches = await service.assess_risk(version.id, policy.id, nav_at, context)
        if len(breaches) != 1 or breaches[0].limit_type != "hard":
            raise AssertionError("hard risk breach was not generated")
        optimization = OptimizationRun(
            portfolio_id=portfolio.id,
            as_of=version.as_of,
            input_sha256="2" * 64,
            solver="SCS",
            solver_version="verification",
            tolerances={"epsilon": 1e-8},
            status="optimal",
            weights={str(instrument.id): 0.625},
            trades=[],
            slacks={},
            diagnostics={"verification": True},
        )
        session.add(optimization)
        await session.flush()
        approval_context = InstitutionalAccessContext(
            "committee-approver",
            organization.id,
            frozenset({team.id}),
            frozenset({"portfolio:approve"}),
            "paper",
        )
        decision = {
            "rationale": "verified institutional decision pack",
            "votes": [
                {"actor_id": "manager-approver", "role": "portfolio_manager", "decision": "approved"},
                {"actor_id": "risk-approver", "role": "risk_officer", "decision": "approved"},
            ],
        }
        try:
            await service.approve_version(version.id, optimization.id, risk_snapshot.id, decision, approval_context)
        except ValueError as exc:
            if "hard risk breach" not in str(exc):
                raise
        else:
            raise AssertionError("open hard breach did not block approval")
        waiver = await service.waive_breach(
            breaches[0].id,
            "temporary verification waiver",
            nav_at + timedelta(hours=1),
            context,
        )
        approved = await service.approve_version(
            version.id, optimization.id, risk_snapshot.id, decision, approval_context
        )
        evidence = await session.get(PortfolioApprovalEvidence, version.id)
        if approved.status != "approved" or evidence is None or "evidence" not in approved.decision:
            raise AssertionError("approved version did not preserve optimizer/risk/decision evidence")
        expired = await service.expire_waivers(nav_at + timedelta(hours=2))
        await session.refresh(breaches[0])
        if waiver.breach_id != breaches[0].id or expired != 1 or breaches[0].status != "open":
            raise AssertionError("waiver lifecycle did not reopen the expired breach")
        mandate.exclusions = {"restricted": [str(instrument.id)]}
        try:
            await service.create_version(
                portfolio_id=portfolio.id,
                as_of=nav_at,
                positions=((instrument.id, Decimal("1"), Decimal("10")),),
                cash=(("BRL", Decimal("1")),),
                proposal={"target_weights": {str(instrument.id): "0.99"}},
                thesis_version_ids=(),
                valuation_run_ids=(),
                context=context,
            )
        except ValueError as exc:
            if "restricted" not in str(exc):
                raise
        else:
            raise AssertionError("restricted instrument was accepted")
        mandate.exclusions = {"restricted": []}
        try:
            await service.assess_risk(version.id, policy.id, nav_at + timedelta(hours=25), context)
        except ValueError as exc:
            if "stale" not in str(exc):
                raise
        else:
            raise AssertionError("stale risk price was accepted")
        print(
            "institutional-portfolio-ok",
            "tenant=true mandate_idempotent=true state_machine=true nav_pit_fx_actions=true "
            "pnl_benchmark=true republication=true risk_waiver_expiry=true approval_evidence=true",
            f"portfolio={portfolio.id}",
            f"nav={publication.nav}",
        )


if __name__ == "__main__":
    asyncio.run(verify())
