from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from ia_investing.domain.backtest import (
    HistoricalUniverseMember,
    InstitutionalBacktestConfig,
    MarketSession,
    PointInTimeCorporateAction,
    PointInTimePrice,
    PointInTimeSignal,
    historical_universe,
    known_signals,
    run_point_in_time_backtest,
    select_equal_weight,
    signal_ablation_sources,
    validate_walk_forward_split,
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
    evaluate_risk_limits,
    investable_universe,
    stress_portfolio,
    top_portfolio_eligible,
    validate_mandate,
    validate_portfolio_transition,
)


def test_institutional_authorization_is_tenant_team_and_environment_scoped() -> None:
    organization_id, team_id = uuid4(), uuid4()
    context = InstitutionalAccessContext(
        "manager", organization_id, frozenset({team_id}), frozenset({"portfolio:propose"}), "paper"
    )
    authorize(context, "portfolio:propose", ResourceAttributes(organization_id, team_id))
    with pytest.raises(PermissionError, match="cross-organization"):
        authorize(context, "portfolio:propose", ResourceAttributes(uuid4(), team_id))
    with pytest.raises(PermissionError, match="live"):
        authorize(context, "portfolio:propose", ResourceAttributes(organization_id, team_id, "live"))
    with pytest.raises(PermissionError, match="own"):
        ensure_four_eyes("manager", "manager")


def test_mandate_and_state_machine_fail_closed() -> None:
    validate_mandate(
        min_cash_weight=Decimal("0.02"),
        max_cash_weight=Decimal("0.10"),
        max_turnover=Decimal("0.25"),
        max_drawdown=Decimal("0.20"),
        benchmark_in_universe=False,
    )
    validate_portfolio_transition("draft", "researching")
    with pytest.raises(ValueError, match="invalid"):
        validate_portfolio_transition("draft", "approved")
    with pytest.raises(ValueError, match="benchmark"):
        validate_mandate(
            min_cash_weight=Decimal(0),
            max_cash_weight=Decimal("0.1"),
            max_turnover=Decimal("0.2"),
            max_drawdown=Decimal("0.2"),
            benchmark_in_universe=True,
        )


def test_nav_preserves_accounting_identity_and_reproducible_hash() -> None:
    inputs = (PositionValue("A", Decimal(10), Decimal(12)),)
    first = calculate_nav(inputs, (Decimal(100),), (Decimal(2),), (Decimal(3),))
    second = calculate_nav(inputs, (Decimal(100),), (Decimal(2),), (Decimal(3),))
    assert first.nav == Decimal(215)
    assert first.nav == first.cash_value + first.positions_value - first.fees_value - first.taxes_value
    assert first.input_sha256 == second.input_sha256


def test_hard_risk_limit_blocks_and_stress_is_deterministic() -> None:
    breaches = evaluate_risk_limits(
        {"position_weight": Decimal("0.25")},
        (RiskLimitInput("position_weight", "hard", Decimal("0.20")),),
    )
    assert breaches[0].blocks
    assert stress_portfolio(
        {"equity": Decimal(100), "rates": Decimal(-20)},
        {"equity": Decimal("-0.1"), "rates": Decimal("0.05")},
    ) == Decimal(-11)


def test_backtest_filters_future_information_and_benchmark() -> None:
    now = datetime(2026, 1, 10, tzinfo=UTC)
    signals = (
        PointInTimeSignal("A", date(2026, 1, 9), now - timedelta(days=1), Decimal("0.9")),
        PointInTimeSignal("B", date(2026, 1, 9), now + timedelta(days=1), Decimal("1.0")),
        PointInTimeSignal("IBOV", date(2026, 1, 9), now - timedelta(days=1), Decimal("2.0")),
    )
    members = tuple(
        HistoricalUniverseMember(item, date(2020, 1, 1), None, now - timedelta(days=1)) for item in ("A", "B", "IBOV")
    )
    universe = historical_universe(members, now, "IBOV")
    weights = select_equal_weight(known_signals(signals, now), universe, 10)
    assert weights == {"A": Decimal(1)}
    altered_future = (*signals, PointInTimeSignal("B", date(2026, 1, 9), now + timedelta(hours=1), Decimal("99")))
    assert select_equal_weight(known_signals(altered_future, now), universe, 10) == weights


def test_top_portfolio_excludes_critical_breach() -> None:
    assert top_portfolio_eligible(
        approved=True,
        nav_reconciled=True,
        benchmark_complete=True,
        backtest_pit_passed=True,
        theses_healthy=True,
        critical_breach=False,
    )
    assert not top_portfolio_eligible(
        approved=True,
        nav_reconciled=True,
        benchmark_complete=True,
        backtest_pit_passed=True,
        theses_healthy=True,
        critical_breach=True,
    )


def test_investable_universe_excludes_restricted_and_benchmark_fail_closed() -> None:
    assert investable_universe(("A", "B", "IBOV"), restricted=frozenset({"B"}), benchmark_instrument_id="IBOV") == (
        "A",
    )
    with pytest.raises(ValueError, match="no investable"):
        investable_universe(("B", "IBOV"), restricted=frozenset({"B"}), benchmark_instrument_id="IBOV")


def test_portfolio_risk_calculates_concentration_factors_liquidity_volatility_and_drawdown() -> None:
    result = calculate_portfolio_risk(
        position_values={"A": Decimal(60), "B": Decimal(30)},
        cash_value=Decimal(10),
        average_daily_values={"A": Decimal(30), "B": Decimal(30)},
        factor_loadings={
            "A": {"rates": Decimal("0.5"), "commodity": Decimal("0.2")},
            "B": {"rates": Decimal("-0.5")},
        },
        portfolio_returns=(Decimal("0.01"), Decimal("-0.02"), Decimal("0.03")),
        nav_history=(Decimal(100), Decimal(110), Decimal(88), Decimal(95)),
    )
    assert result.concentration["largest_position_weight"] == Decimal("0.6")
    assert result.concentration["hhi"] == Decimal("0.45")
    assert result.factor_exposures["rates"] == Decimal("0.15")
    assert result.liquidity["A"] == Decimal(2)
    assert result.observations["liquidity_days_max"] == Decimal(2)
    assert result.drawdown == Decimal("0.2")
    assert result.volatility is not None and result.volatility > 0


def test_portfolio_risk_fails_closed_when_liquidity_is_missing() -> None:
    with pytest.raises(ValueError, match="liquidity"):
        calculate_portfolio_risk(
            position_values={"A": Decimal(60)},
            cash_value=Decimal(10),
            average_daily_values={},
            factor_loadings={},
            portfolio_returns=(),
            nav_history=(),
        )


def test_institutional_backtest_delays_execution_and_applies_known_actions() -> None:
    sessions = tuple(
        MarketSession(day, datetime(day.year, day.month, day.day, 20, tzinfo=UTC))
        for day in (date(2026, 1, 2), date(2026, 1, 5), date(2026, 1, 6), date(2026, 1, 7))
    )
    known_at = datetime(2026, 1, 2, 19, tzinfo=UTC)
    prices = tuple(
        PointInTimePrice(instrument, session.session_date, session.close_at - timedelta(minutes=1), price)
        for session, asset_price, benchmark_price in zip(
            sessions,
            (Decimal(10), Decimal(10), Decimal(5), Decimal(5)),
            (Decimal(100), Decimal(101), Decimal(102), Decimal(103)),
            strict=True,
        )
        for instrument, price in (("A", asset_price), ("IBOV", benchmark_price))
    )
    result = run_point_in_time_backtest(
        config=InstitutionalBacktestConfig(
            date(2026, 1, 2), date(2026, 1, 7), 1, 1, Decimal(1_000), Decimal(10), Decimal(5), 7
        ),
        sessions=sessions,
        signals=(PointInTimeSignal("A", date(2026, 1, 2), known_at, Decimal(1)),),
        universe_members=(HistoricalUniverseMember("A", date(2026, 1, 2), None, known_at),),
        prices=prices,
        corporate_actions=(
            PointInTimeCorporateAction("A", date(2026, 1, 6), known_at, "split", Decimal(2)),
            PointInTimeCorporateAction("A", date(2026, 1, 7), known_at, "jcp", Decimal("0.5"), Decimal("0.15")),
        ),
        benchmark_instrument_id="IBOV",
    )
    assert result.trades
    assert all(trade.execution_date > trade.signal_date for trade in result.trades)
    assert result.applied_actions == (
        ("A", date(2026, 1, 6), "split"),
        ("A", date(2026, 1, 7), "jcp"),
    )
    assert result.nav[-1].benchmark_nav == Decimal(1_030)
    assert result.nav[-1].nav > 0


def test_backtest_is_reproducible_and_future_revisions_do_not_change_past() -> None:
    sessions = tuple(
        MarketSession(day, datetime(day.year, day.month, day.day, 20, tzinfo=UTC))
        for day in (date(2026, 2, 2), date(2026, 2, 3))
    )
    known_at = datetime(2026, 2, 2, 19, tzinfo=UTC)
    config = InstitutionalBacktestConfig(date(2026, 2, 2), date(2026, 2, 3), 1, 1, Decimal(100), seed=42)
    prices = tuple(
        PointInTimePrice("A", session.session_date, session.close_at - timedelta(minutes=1), Decimal(10))
        for session in sessions
    )
    kwargs = {
        "config": config,
        "sessions": sessions,
        "signals": (PointInTimeSignal("A", date(2026, 2, 2), known_at, Decimal(1)),),
        "universe_members": (HistoricalUniverseMember("A", date(2026, 2, 2), None, known_at),),
    }
    first = run_point_in_time_backtest(prices=prices, **kwargs)
    replay = run_point_in_time_backtest(prices=prices, **kwargs)
    prices_with_future_revision = (
        *prices,
        PointInTimePrice("A", date(2026, 2, 2), datetime(2026, 2, 4, tzinfo=UTC), Decimal(999)),
    )
    changed_input = run_point_in_time_backtest(prices=prices_with_future_revision, **kwargs)
    assert first.result_sha256 == replay.result_sha256 == changed_input.result_sha256
    assert first.data_sha256 != changed_input.data_sha256
    assert first.nav == changed_input.nav


def test_backtest_walk_forward_and_ablation_contracts() -> None:
    validate_walk_forward_split(date(2025, 12, 31), date(2026, 1, 1))
    with pytest.raises(ValueError, match="out-of-sample"):
        validate_walk_forward_split(date(2026, 1, 1), date(2026, 1, 1))
    now = datetime(2026, 1, 1, tzinfo=UTC)
    variants = signal_ablation_sources(
        (
            PointInTimeSignal("A", date(2026, 1, 1), now, Decimal(1), "quant"),
            PointInTimeSignal("A", date(2026, 1, 1), now, Decimal(1), "news"),
            PointInTimeSignal("A", date(2026, 1, 1), now, Decimal(1), "policy"),
        )
    )
    assert variants["quant_only"] == {"quant"}
    assert variants["without_news"] == {"quant", "policy"}
