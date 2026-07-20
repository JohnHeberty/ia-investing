from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from ia_investing.domain.backtest import (
    HistoricalUniverseMember,
    InstitutionalBacktestConfig,
    MarketSession,
    PointInTimePrice,
    PointInTimeSignal,
    run_point_in_time_backtest,
)
from ia_investing.domain.institutional_portfolio import (
    PositionValue,
    calculate_nav,
    top_portfolio_eligible,
    validate_mandate,
    validate_portfolio_transition,
)
from ia_investing.domain.portfolio_decision import (
    CommitteeVote,
    PortfolioDecisionInputs,
    decision_pack_sha256,
    validate_committee_vote,
)


class TestMandateToNavE2E:
    def test_mandate_validation_passes(self) -> None:
        validate_mandate(
            min_cash_weight=Decimal("0.05"),
            max_cash_weight=Decimal("0.15"),
            max_turnover=Decimal("0.5"),
            max_drawdown=Decimal("0.2"),
            benchmark_in_universe=False,
        )

    def test_full_portfolio_lifecycle(self) -> None:
        transitions = [
            ("draft", "researching"),
            ("researching", "simulated"),
            ("simulated", "committee_review"),
            ("committee_review", "approved"),
            ("approved", "paper_live"),
        ]
        for current, target in transitions:
            validate_portfolio_transition(current, target)

    def test_decision_pack_is_immutable_and_deterministic(self) -> None:
        inputs = PortfolioDecisionInputs(
            portfolio_id="PORT-001",
            proposed_by="analyst-01",
            input_snapshot_sha256="a" * 64,
            proposal_sha256="b" * 64,
            risk_opinion="approved",
            compliance_opinion="approved",
            optimizer_status="optimal",
            eligible=True,
            hard_breach=False,
        )
        vote_pm = CommitteeVote(
            actor_id="pm-01",
            role="portfolio_manager",
            decision="approved",
            rationale="Strong risk-adjusted thesis",
            signature_sha256="c" * 64,
        )
        vote_risk = CommitteeVote(
            actor_id="risk-01",
            role="risk_officer",
            decision="approved_with_conditions",
            rationale="Approve with monitoring",
            signature_sha256="d" * 64,
            conditions=("max_drawdown_review",),
        )
        votes = (vote_pm, vote_risk)
        hash_first = decision_pack_sha256(inputs, votes)
        hash_second = decision_pack_sha256(inputs, votes)
        assert hash_first == hash_second

        vote_risk_changed = CommitteeVote(
            actor_id="risk-01",
            role="risk_officer",
            decision="rejected",
            rationale="Excessive concentration risk",
            signature_sha256="e" * 64,
        )
        hash_changed = decision_pack_sha256(inputs, (vote_pm, vote_risk_changed))
        assert hash_changed != hash_first

    def test_committee_four_eyes_enforced(self) -> None:
        author_vote = CommitteeVote(
            actor_id="analyst-02",
            role="portfolio_manager",
            decision="approved",
            rationale="Self-approval attempt",
            signature_sha256="h" * 64,
        )
        with pytest.raises(PermissionError, match="proposal author cannot approve"):
            validate_committee_vote(author_vote, proposed_by="analyst-02", existing_actors=frozenset())

        valid_vote = CommitteeVote(
            actor_id="pm-01",
            role="portfolio_manager",
            decision="approved",
            rationale="Looks good",
            signature_sha256="i" * 64,
        )
        validate_committee_vote(valid_vote, proposed_by="analyst-02", existing_actors=frozenset())

        duplicate_vote = CommitteeVote(
            actor_id="pm-01",
            role="risk_officer",
            decision="approved",
            rationale="Second vote",
            signature_sha256="j" * 64,
        )
        with pytest.raises(ValueError, match="already voted"):
            validate_committee_vote(duplicate_vote, proposed_by="analyst-02", existing_actors=frozenset({"pm-01"}))

        unauthorized_vote = CommitteeVote(
            actor_id="intern-01",
            role="intern",
            decision="approved",
            rationale="Not authorized",
            signature_sha256="k" * 64,
        )
        with pytest.raises(ValueError, match="not authorized"):
            validate_committee_vote(unauthorized_vote, proposed_by="analyst-02", existing_actors=frozenset())

    def test_nav_calculation_reproducible(self) -> None:
        positions = (
            PositionValue(instrument_id="PETR4", quantity=Decimal(100), price=Decimal("28.50")),
            PositionValue(instrument_id="VALE3", quantity=Decimal(50), price=Decimal("65.00")),
        )
        cash = (Decimal("10000"),)
        fees = (Decimal("50"),)
        taxes = (Decimal("25"),)

        nav_result = calculate_nav(positions, cash, fees, taxes)
        assert nav_result.cash_value == Decimal("10000")
        assert nav_result.positions_value == Decimal("6100")
        assert nav_result.fees_value == Decimal("50")
        assert nav_result.taxes_value == Decimal("25")
        assert nav_result.nav == Decimal("16025")
        assert nav_result.reconciled is True

        nav_result_2 = calculate_nav(positions, cash, fees, taxes)
        assert nav_result.input_sha256 == nav_result_2.input_sha256

    def test_nav_must_be_nonnegative(self) -> None:
        positions = ()
        cash = (Decimal("0"),)
        fees = (Decimal("100"),)
        taxes = ()

        nav_result = calculate_nav(positions, cash, fees, taxes)
        assert nav_result.nav < 0
        assert nav_result.reconciled is False

    def test_top_x_eligibility_checks_all_flags(self) -> None:
        assert (
            top_portfolio_eligible(
                approved=True,
                nav_reconciled=True,
                benchmark_complete=True,
                backtest_pit_passed=True,
                theses_healthy=True,
                critical_breach=False,
            )
            is True
        )

        assert (
            top_portfolio_eligible(
                approved=False,
                nav_reconciled=True,
                benchmark_complete=True,
                backtest_pit_passed=True,
                theses_healthy=True,
                critical_breach=False,
            )
            is False
        )

        assert (
            top_portfolio_eligible(
                approved=True,
                nav_reconciled=True,
                benchmark_complete=True,
                backtest_pit_passed=True,
                theses_healthy=True,
                critical_breach=True,
            )
            is False
        )

    def test_backtest_reproducible(self) -> None:
        config = InstitutionalBacktestConfig(
            start_date=date(2026, 1, 2),
            end_date=date(2026, 1, 3),
            signal_delay_sessions=1,
            top_n=1,
            initial_cash=Decimal("100000"),
        )
        sessions = (
            MarketSession(session_date=date(2026, 1, 2), close_at=datetime(2026, 1, 2, 18, 0, tzinfo=UTC)),
            MarketSession(session_date=date(2026, 1, 3), close_at=datetime(2026, 1, 3, 18, 0, tzinfo=UTC)),
        )
        signals = (
            PointInTimeSignal(
                instrument_id="PETR4",
                signal_date=date(2026, 1, 1),
                knowledge_at=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
                score=Decimal("0.8"),
            ),
            PointInTimeSignal(
                instrument_id="VALE3",
                signal_date=date(2026, 1, 1),
                knowledge_at=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
                score=Decimal("0.6"),
            ),
        )
        universe_members = (
            HistoricalUniverseMember(
                instrument_id="PETR4",
                valid_from=date(2025, 12, 1),
                valid_to=None,
                knowledge_at=datetime(2025, 12, 1, 12, 0, tzinfo=UTC),
            ),
            HistoricalUniverseMember(
                instrument_id="VALE3",
                valid_from=date(2025, 12, 1),
                valid_to=None,
                knowledge_at=datetime(2025, 12, 1, 12, 0, tzinfo=UTC),
            ),
        )
        prices = (
            PointInTimePrice(
                instrument_id="PETR4",
                session_date=date(2026, 1, 2),
                knowledge_at=datetime(2026, 1, 2, 18, 0, tzinfo=UTC),
                close=Decimal("30"),
            ),
            PointInTimePrice(
                instrument_id="PETR4",
                session_date=date(2026, 1, 3),
                knowledge_at=datetime(2026, 1, 3, 18, 0, tzinfo=UTC),
                close=Decimal("31"),
            ),
            PointInTimePrice(
                instrument_id="VALE3",
                session_date=date(2026, 1, 2),
                knowledge_at=datetime(2026, 1, 2, 18, 0, tzinfo=UTC),
                close=Decimal("60"),
            ),
            PointInTimePrice(
                instrument_id="VALE3",
                session_date=date(2026, 1, 3),
                knowledge_at=datetime(2026, 1, 3, 18, 0, tzinfo=UTC),
                close=Decimal("62"),
            ),
        )

        result_1 = run_point_in_time_backtest(
            config=config,
            sessions=sessions,
            signals=signals,
            universe_members=universe_members,
            prices=prices,
        )
        result_2 = run_point_in_time_backtest(
            config=config,
            sessions=sessions,
            signals=signals,
            universe_members=universe_members,
            prices=prices,
        )

        assert result_1.config_sha256 == result_2.config_sha256
        assert result_1.result_sha256 == result_2.result_sha256
        assert len(result_1.nav) == 2

    def test_ineligible_portfolio_excluded_from_ranking(self) -> None:
        assert (
            top_portfolio_eligible(
                approved=False,
                nav_reconciled=True,
                benchmark_complete=True,
                backtest_pit_passed=True,
                theses_healthy=True,
                critical_breach=False,
            )
            is False
        )

        assert (
            top_portfolio_eligible(
                approved=True,
                nav_reconciled=True,
                benchmark_complete=True,
                backtest_pit_passed=True,
                theses_healthy=True,
                critical_breach=True,
            )
            is False
        )
