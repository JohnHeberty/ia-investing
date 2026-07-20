from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.agents import AuditLog
from database.models.instrument_master import Instrument, Listing
from database.models.market_data import CorporateAction, FxRate, MarketBar, MarketIndex
from database.models.portfolio_domain import (
    CashSnapshot,
    InstitutionalPortfolioVersion,
    InstitutionalRiskPolicy,
    InstitutionalRiskSnapshot,
    ModelPortfolio,
    NavPublication,
    OptimizationRun,
    PortfolioApprovalEvidence,
    PortfolioLedgerEntry,
    PortfolioVersionThesis,
    PortfolioVersionValuation,
    PositionSnapshot,
    RiskBreach,
    RiskWaiver,
    StrategyMandate,
)
from ia_investing.domain.identity import (
    InstitutionalAccessContext,
    ResourceAttributes,
    authorize,
    ensure_four_eyes,
)
from ia_investing.domain.institutional_portfolio import (
    PositionValue,
    RiskLimitInput,
    calculate_nav,
    calculate_portfolio_risk,
    canonical_hash,
    evaluate_risk_limits,
    validate_mandate,
    validate_portfolio_transition,
)


class PortfolioConcurrencyError(RuntimeError):
    pass


class InstitutionalPortfolioService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_mandate(
        self,
        payload: dict[str, object],
        context: InstitutionalAccessContext,
    ) -> StrategyMandate:
        authorize(context, "mandate:create", ResourceAttributes(context.organization_id))
        validate_mandate(
            min_cash_weight=Decimal(str(payload["min_cash_weight"])),
            max_cash_weight=Decimal(str(payload["max_cash_weight"])),
            max_turnover=Decimal(str(payload["max_turnover"])),
            max_drawdown=Decimal(str(payload["max_drawdown"])),
            benchmark_in_universe=bool(payload.get("benchmark_in_universe", False)),
        )
        content_hash = canonical_hash(payload)
        existing = (
            await self.session.execute(
                sa.select(StrategyMandate).where(
                    StrategyMandate.organization_id == context.organization_id,
                    StrategyMandate.logical_id == payload["logical_id"],
                    StrategyMandate.content_sha256 == content_hash,
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            return existing
        next_version = (
            await self.session.scalar(
                sa.select(sa.func.coalesce(sa.func.max(StrategyMandate.version), 0) + 1).where(
                    StrategyMandate.organization_id == context.organization_id,
                    StrategyMandate.logical_id == payload["logical_id"],
                )
            )
        ) or 1
        mandate = StrategyMandate(
            organization_id=context.organization_id,
            logical_id=str(payload["logical_id"]),
            version=next_version,
            objective=str(payload["objective"]),
            strategy_type=str(payload["strategy_type"]),
            universe_definition=dict(payload["universe_definition"]),  # type: ignore[arg-type]
            benchmark_index_id=UUID(str(payload["benchmark_index_id"])),
            base_currency=str(payload.get("base_currency", "BRL")),
            investment_horizon_days=int(str(payload["investment_horizon_days"])),
            rebalance_policy=dict(payload["rebalance_policy"]),  # type: ignore[arg-type]
            risk_budget=dict(payload["risk_budget"]),  # type: ignore[arg-type]
            target_volatility=Decimal(str(payload["target_volatility"])) if payload.get("target_volatility") else None,
            max_drawdown=Decimal(str(payload["max_drawdown"])),
            concentration_limits=dict(payload["concentration_limits"]),  # type: ignore[arg-type]
            factor_limits=dict(payload["factor_limits"]),  # type: ignore[arg-type]
            liquidity_policy=dict(payload["liquidity_policy"]),  # type: ignore[arg-type]
            min_cash_weight=Decimal(str(payload["min_cash_weight"])),
            max_cash_weight=Decimal(str(payload["max_cash_weight"])),
            max_turnover=Decimal(str(payload["max_turnover"])),
            exclusions=dict(payload["exclusions"]),  # type: ignore[arg-type]
            cost_policy=dict(payload["cost_policy"]),  # type: ignore[arg-type]
            tax_policy=dict(payload["tax_policy"]),  # type: ignore[arg-type]
            approval_policy=dict(payload["approval_policy"]),  # type: ignore[arg-type]
            content_sha256=content_hash,
            status="draft",
            created_by=context.subject,
        )
        self.session.add(mandate)
        await self.session.flush()
        self._audit(context, "mandate.create", "strategy_mandate", mandate.id, {"version": next_version})
        await self.session.flush()
        return mandate

    async def create_portfolio(
        self,
        *,
        mandate_id: UUID,
        owner_team_id: UUID,
        name: str,
        context: InstitutionalAccessContext,
    ) -> ModelPortfolio:
        authorize(context, "portfolio:create", ResourceAttributes(context.organization_id, owner_team_id))
        mandate = await self.session.get(StrategyMandate, mandate_id)
        if mandate is None or mandate.organization_id != context.organization_id:
            raise LookupError("mandate not found in organization")
        portfolio = ModelPortfolio(
            organization_id=context.organization_id,
            owner_team_id=owner_team_id,
            mandate_id=mandate.id,
            name=name,
            base_currency=mandate.base_currency,
            state="draft",
            environment="paper",
            created_by=context.subject,
        )
        self.session.add(portfolio)
        await self.session.flush()
        self._audit(context, "portfolio.create", "model_portfolio", portfolio.id, {"mandate_id": str(mandate.id)})
        await self.session.flush()
        return portfolio

    async def transition(
        self,
        portfolio_id: UUID,
        target: str,
        expected_version: int,
        reason: str,
        context: InstitutionalAccessContext,
    ) -> ModelPortfolio:
        portfolio = await self.session.get(ModelPortfolio, portfolio_id, with_for_update=True)
        if portfolio is None:
            raise LookupError("portfolio not found")
        authorize(
            context,
            "portfolio:transition",
            ResourceAttributes(
                portfolio.organization_id, portfolio.owner_team_id, portfolio.environment, portfolio.state
            ),
        )
        if portfolio.lock_version != expected_version:
            raise PortfolioConcurrencyError("portfolio version does not match If-Match")
        validate_portfolio_transition(portfolio.state, target)
        before = portfolio.state
        portfolio.state = target
        portfolio.lock_version += 1
        self._audit(
            context,
            "portfolio.transition",
            "model_portfolio",
            portfolio.id,
            {"from": before, "to": target, "reason": reason},
        )
        await self.session.flush()
        return portfolio

    async def create_version(
        self,
        *,
        portfolio_id: UUID,
        as_of: datetime,
        positions: tuple[tuple[UUID, Decimal, Decimal], ...],
        cash: tuple[tuple[str, Decimal], ...],
        proposal: dict[str, object],
        thesis_version_ids: tuple[UUID, ...],
        valuation_run_ids: tuple[UUID, ...],
        context: InstitutionalAccessContext,
    ) -> InstitutionalPortfolioVersion:
        portfolio = await self.session.get(ModelPortfolio, portfolio_id)
        if portfolio is None:
            raise LookupError("portfolio not found")
        authorize(context, "portfolio:propose", ResourceAttributes(portfolio.organization_id, portfolio.owner_team_id))
        mandate = await self.session.get(StrategyMandate, portfolio.mandate_id)
        if mandate is None:
            raise RuntimeError("portfolio references a missing mandate")
        if as_of.tzinfo is None:
            raise ValueError("as_of must be timezone-aware")
        if any(quantity < 0 or cost_basis < 0 for _, quantity, cost_basis in positions):
            raise ValueError("position quantity and cost basis must be nonnegative")
        if any(amount < 0 for _, amount in cash):
            raise ValueError("cash snapshots must be nonnegative")
        restricted = {str(item) for item in mandate.exclusions.get("restricted", [])}
        selected = {str(instrument_id) for instrument_id, _, _ in positions}
        if selected & restricted:
            raise ValueError(f"portfolio contains restricted instruments: {sorted(selected & restricted)}")
        next_version = (
            await self.session.scalar(
                sa.select(sa.func.coalesce(sa.func.max(InstitutionalPortfolioVersion.version), 0) + 1).where(
                    InstitutionalPortfolioVersion.portfolio_id == portfolio.id
                )
            )
        ) or 1
        snapshot_payload = {
            "as_of": as_of,
            "positions": positions,
            "cash": cash,
            "theses": thesis_version_ids,
            "valuations": valuation_run_ids,
        }
        approved_weights = dict(proposal.get("target_weights", {}))  # type: ignore[arg-type]
        version = InstitutionalPortfolioVersion(
            portfolio_id=portfolio.id,
            mandate_id=portfolio.mandate_id,
            version=next_version,
            as_of=as_of,
            input_snapshot_sha256=canonical_hash(snapshot_payload),
            weights_sha256=canonical_hash(approved_weights),
            approved_weights=approved_weights,
            proposal=proposal,
            status="proposed",
            created_by=context.subject,
        )
        self.session.add(version)
        await self.session.flush()
        for instrument_id, quantity, cost_basis in positions:
            self.session.add(
                PositionSnapshot(
                    portfolio_version_id=version.id,
                    instrument_id=instrument_id,
                    quantity=quantity,
                    cost_basis=cost_basis,
                    as_of=as_of,
                )
            )
        for currency, amount in cash:
            self.session.add(
                CashSnapshot(portfolio_version_id=version.id, currency=currency, amount=amount, as_of=as_of)
            )
        for thesis_version_id in thesis_version_ids:
            self.session.add(
                PortfolioVersionThesis(portfolio_version_id=version.id, thesis_version_id=thesis_version_id)
            )
        for valuation_run_id in valuation_run_ids:
            self.session.add(
                PortfolioVersionValuation(portfolio_version_id=version.id, valuation_run_id=valuation_run_id)
            )
        await self.session.flush()
        return version

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

    async def publish_nav(
        self,
        version_id: UUID,
        as_of: datetime,
        context: InstitutionalAccessContext,
    ) -> NavPublication:
        version = await self.session.get(InstitutionalPortfolioVersion, version_id)
        if version is None:
            raise LookupError("portfolio version not found")
        portfolio = await self.session.get(ModelPortfolio, version.portfolio_id)
        if portfolio is None:
            raise RuntimeError("portfolio version references missing portfolio")
        authorize(context, "nav:publish", ResourceAttributes(portfolio.organization_id, portfolio.owner_team_id))
        snapshots = list(
            (
                await self.session.execute(
                    sa.select(PositionSnapshot).where(PositionSnapshot.portfolio_version_id == version.id)
                )
            ).scalars()
        )
        positions: list[PositionValue] = []
        input_details: dict[str, object] = {"positions": [], "cash": [], "corporate_action_cash": []}
        corporate_action_cash: list[Decimal] = []
        invested_cost = Decimal(0)
        for snapshot in snapshots:
            price_row = (
                await self.session.execute(
                    sa.select(Listing, MarketBar)
                    .join(MarketBar, MarketBar.listing_id == Listing.id)
                    .where(
                        Listing.instrument_id == snapshot.instrument_id,
                        Listing.valid_from <= as_of.date(),
                        sa.or_(Listing.valid_to.is_(None), Listing.valid_to > as_of.date()),
                        MarketBar.bar_at <= as_of,
                        MarketBar.knowledge_at <= as_of,
                    )
                    .order_by(MarketBar.bar_at.desc(), MarketBar.knowledge_at.desc())
                    .limit(1)
                )
            ).first()
            if price_row is None:
                raise ValueError(f"price missing at as_of for instrument {snapshot.instrument_id}")
            listing, bar = price_row
            instrument = await self.session.get(Instrument, snapshot.instrument_id)
            if instrument is None:
                raise RuntimeError("position references missing instrument")
            fx_rate, fx_id = await self._fx_multiplier(instrument.currency_code, portfolio.base_currency, as_of)
            invested_cost += snapshot.quantity * snapshot.cost_basis * fx_rate
            quantity = snapshot.quantity
            actions = list(
                (
                    await self.session.scalars(
                        sa.select(CorporateAction)
                        .where(
                            CorporateAction.instrument_id == snapshot.instrument_id,
                            CorporateAction.knowledge_at <= as_of,
                            CorporateAction.ex_date.is_not(None),
                            CorporateAction.ex_date > snapshot.as_of.date(),
                            CorporateAction.ex_date <= as_of.date(),
                        )
                        .order_by(CorporateAction.ex_date, CorporateAction.knowledge_at)
                    )
                ).all()
            )
            applied_actions: list[str] = []
            for action in (item for item in actions if item.action_type in {"split", "reverse_split"}):
                if action.action_type == "split" and action.ratio is not None:
                    quantity *= action.ratio
                elif action.action_type == "reverse_split" and action.ratio is not None:
                    quantity /= action.ratio
                applied_actions.append(str(action.id))
            for action in (item for item in actions if item.action_type in {"dividend", "jcp"}):
                if action.amount_per_unit is not None:
                    action_currency = action.currency_code or instrument.currency_code
                    action_fx, action_fx_id = await self._fx_multiplier(action_currency, portfolio.base_currency, as_of)
                    amount = quantity * action.amount_per_unit * action_fx
                    corporate_action_cash.append(amount)
                    cast_cash = input_details["corporate_action_cash"]
                    if isinstance(cast_cash, list):
                        cast_cash.append(
                            {
                                "action_id": str(action.id),
                                "amount": str(amount),
                                "fx_rate_id": str(action_fx_id) if action_fx_id else None,
                            }
                        )
                applied_actions.append(str(action.id))
            base_price = bar.close_price * fx_rate
            positions.append(PositionValue(str(snapshot.instrument_id), quantity, base_price))
            cast_positions = input_details["positions"]
            if isinstance(cast_positions, list):
                cast_positions.append(
                    {
                        "instrument_id": str(snapshot.instrument_id),
                        "listing_id": str(listing.id),
                        "ticker": listing.ticker,
                        "bar_id": str(bar.id),
                        "bar_knowledge_at": bar.knowledge_at.isoformat(),
                        "currency": instrument.currency_code,
                        "fx_rate_id": str(fx_id) if fx_id else None,
                        "adjusted_quantity": str(quantity),
                        "corporate_action_ids": applied_actions,
                    }
                )
        cash_rows = (
            await self.session.execute(
                sa.select(CashSnapshot.currency, CashSnapshot.amount).where(
                    CashSnapshot.portfolio_version_id == version.id
                )
            )
        ).all()
        converted_cash: list[Decimal] = []
        for currency, amount in cash_rows:
            fx_rate, fx_id = await self._fx_multiplier(currency, portfolio.base_currency, as_of)
            converted = amount * fx_rate
            converted_cash.append(converted)
            cast_cash_rows = input_details["cash"]
            if isinstance(cast_cash_rows, list):
                cast_cash_rows.append(
                    {
                        "currency": currency,
                        "amount": str(amount),
                        "converted": str(converted),
                        "fx_rate_id": str(fx_id) if fx_id else None,
                    }
                )
        ledger = (
            await self.session.execute(
                sa.select(PortfolioLedgerEntry.entry_type, PortfolioLedgerEntry.amount).where(
                    PortfolioLedgerEntry.portfolio_id == portfolio.id,
                    PortfolioLedgerEntry.occurred_at <= as_of,
                    PortfolioLedgerEntry.entry_type.in_({"fee", "tax"}),
                )
            )
        ).all()
        fees = tuple(amount for entry_type, amount in ledger if entry_type == "fee")
        taxes = tuple(amount for entry_type, amount in ledger if entry_type == "tax")
        result = calculate_nav(tuple(positions), (*converted_cash, *corporate_action_cash), fees, taxes)
        gross_pnl = result.positions_value + sum(corporate_action_cash, start=Decimal(0)) - invested_cost
        net_pnl = gross_pnl - result.fees_value - result.taxes_value
        benchmark_value, benchmark_return, benchmark_details = await self._benchmark_performance(
            version.mandate_id, version.as_of, as_of, portfolio.base_currency
        )
        input_details["benchmark"] = benchmark_details
        revision = (
            await self.session.scalar(
                sa.select(sa.func.coalesce(sa.func.max(NavPublication.revision), 0) + 1).where(
                    NavPublication.portfolio_id == portfolio.id,
                    NavPublication.as_of == as_of,
                )
            )
        ) or 1
        publication = NavPublication(
            portfolio_id=portfolio.id,
            portfolio_version_id=version.id,
            as_of=as_of,
            revision=revision,
            methodology_version="nav-v2-pit-fx-actions",
            input_sha256=canonical_hash({"calculation_input_sha256": result.input_sha256, "provenance": input_details}),
            input_details=input_details,
            cash_value=result.cash_value,
            positions_value=result.positions_value,
            gross_pnl=gross_pnl,
            net_pnl=net_pnl,
            fees_value=result.fees_value,
            taxes_value=result.taxes_value,
            nav=result.nav,
            benchmark_value=benchmark_value,
            benchmark_return=benchmark_return,
            reconciled=result.reconciled,
            published_by=context.subject,
        )
        self.session.add(publication)
        await self.session.flush()
        return publication

    async def _benchmark_performance(
        self,
        mandate_id: UUID,
        start_at: datetime,
        as_of: datetime,
        base_currency: str,
    ) -> tuple[Decimal | None, Decimal | None, dict[str, object]]:
        mandate = await self.session.get(StrategyMandate, mandate_id)
        index = await self.session.get(MarketIndex, mandate.benchmark_index_id) if mandate is not None else None
        if index is None or index.instrument_id is None:
            return None, None, {"status": "unavailable", "reason": "benchmark instrument is not mapped"}
        start_bar = await self._latest_instrument_bar(index.instrument_id, start_at, as_of)
        end_bar = await self._latest_instrument_bar(index.instrument_id, as_of, as_of)
        if start_bar is None or end_bar is None or start_bar.close_price <= 0:
            return None, None, {"status": "unavailable", "reason": "benchmark prices are missing"}
        fx, fx_id = await self._fx_multiplier(index.currency_code, base_currency, as_of)
        return (
            end_bar.close_price * fx,
            end_bar.close_price / start_bar.close_price - Decimal(1),
            {
                "status": "available",
                "index_id": str(index.id),
                "instrument_id": str(index.instrument_id),
                "start_bar_id": str(start_bar.id),
                "end_bar_id": str(end_bar.id),
                "fx_rate_id": str(fx_id) if fx_id else None,
            },
        )

    async def _latest_instrument_bar(
        self,
        instrument_id: UUID,
        price_cutoff: datetime,
        knowledge_cutoff: datetime,
    ) -> MarketBar | None:
        return (
            await self.session.execute(
                sa.select(MarketBar)
                .join(Listing, Listing.id == MarketBar.listing_id)
                .where(
                    Listing.instrument_id == instrument_id,
                    Listing.valid_from <= price_cutoff.date(),
                    sa.or_(Listing.valid_to.is_(None), Listing.valid_to > price_cutoff.date()),
                    MarketBar.bar_at <= price_cutoff,
                    MarketBar.knowledge_at <= knowledge_cutoff,
                )
                .order_by(MarketBar.bar_at.desc(), MarketBar.knowledge_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()

    async def _fx_multiplier(
        self,
        source_currency: str,
        target_currency: str,
        as_of: datetime,
    ) -> tuple[Decimal, UUID | None]:
        if source_currency == target_currency:
            return Decimal(1), None
        direct = (
            await self.session.execute(
                sa.select(FxRate)
                .where(
                    FxRate.base_currency == source_currency,
                    FxRate.quote_currency == target_currency,
                    FxRate.rate_at <= as_of,
                    FxRate.knowledge_at <= as_of,
                )
                .order_by(FxRate.rate_at.desc(), FxRate.knowledge_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if direct is not None:
            return direct.rate, direct.id
        inverse = (
            await self.session.execute(
                sa.select(FxRate)
                .where(
                    FxRate.base_currency == target_currency,
                    FxRate.quote_currency == source_currency,
                    FxRate.rate_at <= as_of,
                    FxRate.knowledge_at <= as_of,
                )
                .order_by(FxRate.rate_at.desc(), FxRate.knowledge_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if inverse is None:
            raise ValueError(f"FX rate missing at as_of for {source_currency}/{target_currency}")
        return Decimal(1) / inverse.rate, inverse.id

    async def assess_risk(
        self,
        version_id: UUID,
        policy_id: UUID,
        as_of: datetime,
        context: InstitutionalAccessContext,
    ) -> tuple[InstitutionalRiskSnapshot, tuple[RiskBreach, ...]]:
        version = await self.session.get(InstitutionalPortfolioVersion, version_id)
        policy = await self.session.get(InstitutionalRiskPolicy, policy_id)
        if version is None or policy is None or version.mandate_id != policy.mandate_id:
            raise LookupError("portfolio version or risk policy not found")
        portfolio = await self.session.get(ModelPortfolio, version.portfolio_id)
        if portfolio is None:
            raise RuntimeError("portfolio missing")
        authorize(context, "risk:assess", ResourceAttributes(portfolio.organization_id, portfolio.owner_team_id))
        if as_of.tzinfo is None:
            raise ValueError("risk cutoff must include timezone information")
        position_rows = list(
            (
                await self.session.scalars(
                    sa.select(PositionSnapshot).where(PositionSnapshot.portfolio_version_id == version.id)
                )
            ).all()
        )
        position_values: dict[str, Decimal] = {}
        average_daily_values: dict[str, Decimal] = {}
        return_series: dict[str, list[Decimal]] = {}
        max_price_age_hours = Decimal(str(policy.limits.get("max_price_age_hours", 72)))
        if max_price_age_hours <= 0:
            raise ValueError("risk policy max_price_age_hours must be positive")
        for position in position_rows:
            bars = list(
                (
                    await self.session.scalars(
                        sa.select(MarketBar)
                        .join(Listing, Listing.id == MarketBar.listing_id)
                        .where(
                            Listing.instrument_id == position.instrument_id,
                            Listing.valid_from <= as_of.date(),
                            sa.or_(Listing.valid_to.is_(None), Listing.valid_to > as_of.date()),
                            MarketBar.bar_at <= as_of,
                            MarketBar.knowledge_at <= as_of,
                        )
                        .order_by(MarketBar.bar_at.desc(), MarketBar.knowledge_at.desc())
                        .limit(253)
                    )
                ).all()
            )
            latest_by_bar = {}
            for bar in bars:
                latest_by_bar.setdefault(bar.bar_at, bar)
            bars = sorted(latest_by_bar.values(), key=lambda item: item.bar_at)
            if len(bars) < 2:
                raise ValueError(f"risk history is missing for instrument {position.instrument_id}")
            price_age_hours = Decimal(str((as_of - bars[-1].bar_at).total_seconds())) / Decimal(3600)
            if price_age_hours > max_price_age_hours:
                raise ValueError(f"risk price is stale for instrument {position.instrument_id}")
            instrument_key = str(position.instrument_id)
            position_values[instrument_key] = position.quantity * bars[-1].close_price
            average_daily_values[instrument_key] = sum(
                (bar.close_price * Decimal(bar.volume) for bar in bars), start=Decimal(0)
            ) / Decimal(len(bars))
            return_series[instrument_key] = [
                bars[index].close_price / bars[index - 1].close_price - Decimal(1)
                for index in range(1, len(bars))
                if bars[index - 1].close_price > 0
            ]
        cash_value = (
            await self.session.scalar(
                sa.select(sa.func.coalesce(sa.func.sum(CashSnapshot.amount), 0)).where(
                    CashSnapshot.portfolio_version_id == version.id
                )
            )
        ) or Decimal(0)
        nav_value = cash_value + sum(position_values.values(), start=Decimal(0))
        weights = {key: value / nav_value for key, value in position_values.items()} if nav_value > 0 else {}
        common_length = min((len(values) for values in return_series.values()), default=0)
        portfolio_returns = tuple(
            sum(
                (weights[key] * values[-common_length + index] for key, values in return_series.items()),
                start=Decimal(0),
            )
            for index in range(common_length)
        )
        nav_history = tuple(
            (
                await self.session.scalars(
                    sa.select(NavPublication.nav)
                    .where(NavPublication.portfolio_id == portfolio.id, NavPublication.as_of <= as_of)
                    .order_by(NavPublication.as_of, NavPublication.revision)
                )
            ).all()
        )
        raw_factor_loadings = policy.limits.get("factor_loadings", {})
        factor_loadings = {
            str(instrument): {str(factor): Decimal(str(value)) for factor, value in values.items()}
            for instrument, values in raw_factor_loadings.items()
            if isinstance(values, dict)
        }
        metrics = calculate_portfolio_risk(
            position_values=position_values,
            cash_value=cash_value,
            average_daily_values=average_daily_values,
            factor_loadings=factor_loadings,
            portfolio_returns=portfolio_returns,
            nav_history=nav_history,
        )
        raw_limits = policy.limits.get("limits", [])
        limits = tuple(
            RiskLimitInput(str(item["name"]), str(item["type"]), Decimal(str(item["maximum"])))
            for item in raw_limits
            if isinstance(item, dict)
        )
        evaluated = evaluate_risk_limits(metrics.observations, limits)
        snapshot = InstitutionalRiskSnapshot(
            portfolio_version_id=version.id,
            risk_policy_id=policy.id,
            as_of=as_of,
            input_sha256=canonical_hash({"metrics": metrics.input_sha256, "policy": policy.content_sha256}),
            exposures={key: str(value) for key, value in metrics.factor_exposures.items()},
            concentration={key: str(value) for key, value in metrics.concentration.items()},
            liquidity={key: str(value) for key, value in metrics.liquidity.items()},
            volatility=metrics.volatility,
            drawdown=metrics.drawdown,
        )
        self.session.add(snapshot)
        await self.session.flush()
        breaches = tuple(
            RiskBreach(
                risk_snapshot_id=snapshot.id,
                limit_name=item.name,
                limit_type=item.limit_type,
                observed_value=item.observed,
                limit_value=item.maximum,
                status="open",
            )
            for item in evaluated
        )
        self.session.add_all(breaches)
        await self.session.flush()
        return snapshot, breaches

    async def waive_breach(
        self,
        breach_id: UUID,
        reason: str,
        expires_at: datetime,
        context: InstitutionalAccessContext,
    ) -> RiskWaiver:
        breach = await self.session.get(RiskBreach, breach_id, with_for_update=True)
        if breach is None:
            raise LookupError("risk breach not found")
        snapshot = await self.session.get(InstitutionalRiskSnapshot, breach.risk_snapshot_id)
        version = (
            await self.session.get(InstitutionalPortfolioVersion, snapshot.portfolio_version_id)
            if snapshot is not None
            else None
        )
        portfolio = await self.session.get(ModelPortfolio, version.portfolio_id) if version is not None else None
        if portfolio is None:
            raise RuntimeError("risk breach references a missing portfolio")
        authorize(context, "risk:waive", ResourceAttributes(portfolio.organization_id, portfolio.owner_team_id))
        if breach.status != "open":
            raise ValueError("only an open breach can be waived")
        if not reason.strip():
            raise ValueError("waiver reason is required")
        if expires_at.tzinfo is None or expires_at <= datetime.now(UTC):
            raise ValueError("waiver expiry must be an aware future timestamp")
        waiver = RiskWaiver(breach_id=breach.id, granted_by=context.subject, reason=reason, expires_at=expires_at)
        breach.status = "waived"
        self.session.add(waiver)
        await self.session.flush()
        self._audit(
            context,
            "risk_breach.waive",
            "risk_breach",
            breach.id,
            {"reason": reason, "expires_at": expires_at.isoformat(), "waiver_id": str(waiver.id)},
        )
        await self.session.flush()
        return waiver

    async def get_portfolio(self, portfolio_id: UUID, organization_id: UUID) -> ModelPortfolio | None:
        portfolio = await self.session.get(ModelPortfolio, portfolio_id)
        if portfolio is None or portfolio.organization_id != organization_id:
            return None
        return portfolio

    async def list_model_portfolios(
        self,
        organization_id: UUID,
        *,
        limit: int = 50,
        after: UUID | None = None,
        state: str | None = None,
    ) -> tuple[list[ModelPortfolio], bool]:
        stmt = (
            sa.select(ModelPortfolio)
            .where(ModelPortfolio.organization_id == organization_id)
            .order_by(ModelPortfolio.id)
            .limit(limit + 1)
        )
        if after is not None:
            stmt = stmt.where(ModelPortfolio.id > after)
        if state is not None:
            stmt = stmt.where(ModelPortfolio.state == state)
        rows = list((await self.session.scalars(stmt)).all())
        has_more = len(rows) > limit
        if has_more:
            rows = rows[:limit]
        return rows, has_more

    async def get_portfolio_version_with_portfolio(
        self, version_id: UUID, organization_id: UUID
    ) -> tuple[InstitutionalPortfolioVersion, ModelPortfolio] | None:
        version = await self.session.get(InstitutionalPortfolioVersion, version_id)
        if version is None:
            return None
        portfolio = await self.session.get(ModelPortfolio, version.portfolio_id)
        if portfolio is None or portfolio.organization_id != organization_id:
            return None
        return version, portfolio

    async def list_positions(self, version_id: UUID) -> list[PositionSnapshot]:
        return list(
            (
                await self.session.scalars(
                    sa.select(PositionSnapshot)
                    .where(PositionSnapshot.portfolio_version_id == version_id)
                    .order_by(PositionSnapshot.instrument_id)
                )
            ).all()
        )

    async def list_nav_publications(self, portfolio_id: UUID, *, as_of: datetime | None = None) -> list[NavPublication]:
        stmt = (
            sa.select(NavPublication)
            .where(NavPublication.portfolio_id == portfolio_id)
            .order_by(NavPublication.as_of.desc(), NavPublication.revision.desc())
        )
        if as_of is not None:
            stmt = stmt.where(NavPublication.as_of <= as_of)
        return list((await self.session.scalars(stmt)).all())

    async def list_risk_breaches(
        self, snapshot_id: UUID, organization_id: UUID
    ) -> tuple[InstitutionalRiskSnapshot, list[RiskBreach]] | None:
        snapshot = await self.session.get(InstitutionalRiskSnapshot, snapshot_id)
        if snapshot is None:
            return None
        version = await self.session.get(InstitutionalPortfolioVersion, snapshot.portfolio_version_id)
        if version is None:
            return None
        portfolio = await self.session.get(ModelPortfolio, version.portfolio_id)
        if portfolio is None or portfolio.organization_id != organization_id:
            return None
        rows = list(
            (
                await self.session.scalars(
                    sa.select(RiskBreach).where(RiskBreach.risk_snapshot_id == snapshot_id).order_by(RiskBreach.id)
                )
            ).all()
        )
        return snapshot, rows

    async def expire_waivers(self, now: datetime) -> int:
        if now.tzinfo is None:
            raise ValueError("waiver expiry cutoff must be timezone-aware")
        breach_ids = sa.select(RiskWaiver.breach_id).where(RiskWaiver.expires_at <= now)
        result = await self.session.execute(
            sa.update(RiskBreach)
            .where(RiskBreach.id.in_(breach_ids), RiskBreach.status == "waived")
            .values(status="open")
        )
        return int(result.rowcount)

    def _audit(
        self,
        context: InstitutionalAccessContext,
        action: str,
        entity_type: str,
        entity_id: UUID,
        details: dict[str, object],
    ) -> None:
        self.session.add(
            AuditLog(
                actor_type="human",
                actor_id=context.subject,
                action=action,
                entity_type=entity_type,
                entity_id=entity_id,
                correlation_id=uuid4(),
                details={"organization_id": str(context.organization_id), **details},
            )
        )
