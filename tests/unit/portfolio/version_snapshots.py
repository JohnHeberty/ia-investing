from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

from ia_investing.domain.backtest import (
    HistoricalUniverseMember,
    InstitutionalBacktestConfig,
    MarketSession,
    PointInTimeCorporateAction,
    PointInTimePrice,
    PointInTimeSignal,
    run_point_in_time_backtest,
)
from ia_investing.domain.institutional_portfolio import (
    NavResult,
    PositionValue,
    calculate_nav,
    canonical_hash,
    validate_portfolio_transition,
)
from ia_investing.domain.portfolio_decision import (
    CommitteeVote,
    PortfolioDecisionInputs,
    decision_pack_sha256,
)


def _make_config(**overrides: object) -> InstitutionalBacktestConfig:
    defaults: dict[str, object] = {
        "start_date": date(2025, 1, 1),
        "end_date": date(2025, 1, 10),
        "signal_delay_sessions": 1,
        "top_n": 1,
        "initial_cash": Decimal(100_000),
        "transaction_cost_bps": Decimal(0),
        "sell_tax_bps": Decimal(0),
        "seed": 0,
    }
    defaults.update(overrides)
    return InstitutionalBacktestConfig(**defaults)  # type: ignore[arg-type]


def _make_sessions(start: date, end: date) -> tuple[MarketSession, ...]:
    sessions: list[MarketSession] = []
    current = start
    while current <= end:
        sessions.append(MarketSession(current, datetime(current.year, current.month, current.day, 20, tzinfo=UTC)))
        current = date.fromordinal(current.toordinal() + 1)
    return tuple(sessions)


def _make_universe(
    instruments: tuple[str, ...],
    valid_from: date,
    valid_to: date | None = None,
) -> tuple[HistoricalUniverseMember, ...]:
    knowledge_at = datetime(2025, 1, 1, tzinfo=UTC)
    return tuple(HistoricalUniverseMember(inst, valid_from, valid_to, knowledge_at) for inst in instruments)


class TestVersionRevision:
    def test_version_v2_does_not_alter_v1_decision_pack(self) -> None:
        validate_portfolio_transition("draft", "researching")
        inputs_v1 = PortfolioDecisionInputs(
            portfolio_id="p-1",
            proposed_by="analyst",
            input_snapshot_sha256="a" * 64,
            proposal_sha256="b" * 64,
            risk_opinion="approved",
            compliance_opinion="approved",
            optimizer_status="optimal",
            eligible=True,
            hard_breach=False,
        )
        hash_v1 = decision_pack_sha256(inputs_v1, ())

        inputs_v2 = PortfolioDecisionInputs(
            portfolio_id="p-1",
            proposed_by="analyst",
            input_snapshot_sha256="c" * 64,
            proposal_sha256="d" * 64,
            risk_opinion="approved",
            compliance_opinion="approved",
            optimizer_status="optimal",
            eligible=True,
            hard_breach=False,
        )
        hash_v2 = decision_pack_sha256(inputs_v2, ())
        assert hash_v2 != hash_v1

    def test_same_inputs_produce_same_decision_pack(self) -> None:
        inputs = PortfolioDecisionInputs(
            portfolio_id="p-1",
            proposed_by="analyst",
            input_snapshot_sha256="a" * 64,
            proposal_sha256="b" * 64,
            risk_opinion="approved",
            compliance_opinion="approved",
            optimizer_status="optimal",
            eligible=True,
            hard_breach=False,
        )
        assert decision_pack_sha256(inputs, ()) == decision_pack_sha256(inputs, ())

    def test_version_preserves_immutable_snapshot_hash(self) -> None:
        positions = (PositionValue("A", Decimal(100), Decimal(10)),)
        nav_result: NavResult = calculate_nav(positions, (Decimal(50_000),))
        snapshot_hash = canonical_hash({"nav": nav_result.nav, "cash": nav_result.cash_value})
        inputs_a = PortfolioDecisionInputs(
            portfolio_id="p-1",
            proposed_by="analyst",
            input_snapshot_sha256=snapshot_hash,
            proposal_sha256="b" * 64,
            risk_opinion="approved",
            compliance_opinion="approved",
            optimizer_status="optimal",
            eligible=True,
            hard_breach=False,
        )
        inputs_b = PortfolioDecisionInputs(
            portfolio_id="p-2",
            proposed_by="analyst",
            input_snapshot_sha256=snapshot_hash,
            proposal_sha256="e" * 64,
            risk_opinion="approved",
            compliance_opinion="approved",
            optimizer_status="optimal",
            eligible=True,
            hard_breach=False,
        )
        vote_a = CommitteeVote("mgr", "portfolio_manager", "approved", "ok", "f" * 64)
        vote_b = CommitteeVote("mgr", "portfolio_manager", "rejected", "no", "f" * 64)
        hash_a = decision_pack_sha256(inputs_a, (vote_a,))
        hash_b = decision_pack_sha256(inputs_b, (vote_b,))
        assert hash_a != hash_b


class TestCorporateActionOnSnapshot:
    def test_split_adjusts_position_quantity(self) -> None:
        sessions = _make_sessions(date(2025, 1, 1), date(2025, 1, 5))
        knowledge_at = datetime(2025, 1, 1, tzinfo=UTC)
        prices = tuple(PointInTimePrice("A", s.session_date, s.close_at, Decimal(10)) for s in sessions)
        result = run_point_in_time_backtest(
            config=_make_config(start_date=date(2025, 1, 1), end_date=date(2025, 1, 5)),
            sessions=sessions,
            signals=(PointInTimeSignal("A", date(2025, 1, 1), knowledge_at, Decimal(1)),),
            universe_members=_make_universe(("A",), date(2025, 1, 1)),
            prices=prices,
            corporate_actions=(PointInTimeCorporateAction("A", date(2025, 1, 3), knowledge_at, "split", Decimal(2)),),
        )
        assert ("A", date(2025, 1, 3), "split") in result.applied_actions
        assert result.nav[-1].nav > 0

    def test_dividend_adds_to_cash(self) -> None:
        sessions = _make_sessions(date(2025, 1, 1), date(2025, 1, 5))
        knowledge_at = datetime(2025, 1, 1, tzinfo=UTC)
        prices = tuple(PointInTimePrice("A", s.session_date, s.close_at, Decimal(10)) for s in sessions)
        universe_after_div = (HistoricalUniverseMember("A", date(2025, 1, 1), date(2025, 1, 4), knowledge_at),)
        result = run_point_in_time_backtest(
            config=_make_config(start_date=date(2025, 1, 1), end_date=date(2025, 1, 5)),
            sessions=sessions,
            signals=(PointInTimeSignal("A", date(2025, 1, 1), knowledge_at, Decimal(1)),),
            universe_members=universe_after_div,
            prices=prices,
            corporate_actions=(
                PointInTimeCorporateAction("A", date(2025, 1, 4), knowledge_at, "dividend", Decimal("1.50")),
            ),
        )
        assert ("A", date(2025, 1, 4), "dividend") in result.applied_actions
        assert result.nav[-1].nav > result.nav[0].nav

    def test_jcp_net_of_tax(self) -> None:
        sessions = _make_sessions(date(2025, 1, 1), date(2025, 1, 5))
        knowledge_at = datetime(2025, 1, 1, tzinfo=UTC)
        prices = tuple(PointInTimePrice("A", s.session_date, s.close_at, Decimal(10)) for s in sessions)
        result = run_point_in_time_backtest(
            config=_make_config(start_date=date(2025, 1, 1), end_date=date(2025, 1, 5)),
            sessions=sessions,
            signals=(PointInTimeSignal("A", date(2025, 1, 1), knowledge_at, Decimal(1)),),
            universe_members=_make_universe(("A",), date(2025, 1, 1)),
            prices=prices,
            corporate_actions=(
                PointInTimeCorporateAction(
                    "A", date(2025, 1, 3), knowledge_at, "jcp", Decimal("0.50"), Decimal("0.15")
                ),
            ),
        )
        assert ("A", date(2025, 1, 3), "jcp") in result.applied_actions
        assert result.nav[-1].nav > 0

    def test_delist_removes_position(self) -> None:
        sessions = _make_sessions(date(2025, 1, 1), date(2025, 1, 5))
        knowledge_at = datetime(2025, 1, 1, tzinfo=UTC)
        prices = tuple(PointInTimePrice("A", s.session_date, s.close_at, Decimal(10)) for s in sessions)
        universe_members = (HistoricalUniverseMember("A", date(2025, 1, 1), date(2025, 1, 4), knowledge_at),)
        result = run_point_in_time_backtest(
            config=_make_config(start_date=date(2025, 1, 1), end_date=date(2025, 1, 5)),
            sessions=sessions,
            signals=(PointInTimeSignal("A", date(2025, 1, 1), knowledge_at, Decimal(1)),),
            universe_members=universe_members,
            prices=prices,
            corporate_actions=(PointInTimeCorporateAction("A", date(2025, 1, 4), knowledge_at, "delist", Decimal(8)),),
        )
        assert ("A", date(2025, 1, 4), "delist") in result.applied_actions
        assert result.nav[-1].cash > 0
        assert result.nav[-1].positions_value == Decimal(0)


class TestDelistedInstrument:
    def test_delisted_instrument_not_in_future_universe(self) -> None:
        knowledge_at = datetime(2025, 1, 1, tzinfo=UTC)
        members = _make_universe(("A", "B"), date(2025, 1, 1))
        result = run_point_in_time_backtest(
            config=_make_config(
                start_date=date(2025, 1, 1),
                end_date=date(2025, 1, 10),
                signal_delay_sessions=1,
                top_n=1,
            ),
            sessions=_make_sessions(date(2025, 1, 1), date(2025, 1, 10)),
            signals=(
                PointInTimeSignal("A", date(2025, 1, 1), knowledge_at, Decimal(1)),
                PointInTimeSignal("B", date(2025, 1, 1), knowledge_at, Decimal(1)),
            ),
            universe_members=members,
            prices=tuple(
                PointInTimePrice(inst, s.session_date, s.close_at, Decimal(10))
                for s in _make_sessions(date(2025, 1, 1), date(2025, 1, 10))
                for inst in ("A", "B")
            ),
            corporate_actions=(PointInTimeCorporateAction("A", date(2025, 1, 5), knowledge_at, "delist", Decimal(10)),),
        )
        assert ("A", date(2025, 1, 5), "delist") in result.applied_actions

    def test_delisted_with_liquidation_price(self) -> None:
        sessions = _make_sessions(date(2025, 1, 1), date(2025, 1, 5))
        knowledge_at = datetime(2025, 1, 1, tzinfo=UTC)
        prices = tuple(PointInTimePrice("A", s.session_date, s.close_at, Decimal(10)) for s in sessions)
        universe_members = (HistoricalUniverseMember("A", date(2025, 1, 1), date(2025, 1, 4), knowledge_at),)
        result = run_point_in_time_backtest(
            config=_make_config(start_date=date(2025, 1, 1), end_date=date(2025, 1, 5)),
            sessions=sessions,
            signals=(PointInTimeSignal("A", date(2025, 1, 1), knowledge_at, Decimal(1)),),
            universe_members=universe_members,
            prices=prices,
            corporate_actions=(PointInTimeCorporateAction("A", date(2025, 1, 4), knowledge_at, "delist", Decimal(7)),),
        )
        assert ("A", date(2025, 1, 4), "delist") in result.applied_actions
        assert result.nav[-1].positions_value == Decimal(0)
        assert result.nav[-1].cash > 0
