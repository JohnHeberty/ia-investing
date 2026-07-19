from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from ia_investing.domain.paper_execution import (
    INTENT_TRANSITIONS,
    ORDER_TRANSITIONS,
    ChallengerCriteria,
    DatedReturn,
    ExecutionConfiguration,
    MarketSnapshot,
    ReconciliationFill,
    ReconciliationLedgerEntry,
    ReconciliationOrder,
    TradingWindow,
    assess_challenger,
    calculate_paper_attribution,
    classify_post_mortem_error,
    compare_strategy_results,
    fill_to_ledger,
    reconcile_execution,
    reconciliation_is_blocking,
    require_human_challenger_decision,
    simulate_order,
    validate_challenger_comparison,
    validate_paper_order_request,
    validate_post_mortem_lineage,
    validate_transition,
)


def configuration() -> ExecutionConfiguration:
    return ExecutionConfiguration(
        "sim-v1", Decimal(10), Decimal("0.10"), Decimal(8), Decimal(20), Decimal(3), Decimal(1), 50
    )


def test_state_machines_fail_closed() -> None:
    validate_transition("draft", "pending_approval", INTENT_TRANSITIONS)
    validate_transition("accepted", "partially_filled", ORDER_TRANSITIONS)
    with pytest.raises(ValueError, match="invalid"):
        validate_transition("cancelled", "submitted", INTENT_TRANSITIONS)
    with pytest.raises(ValueError, match="invalid"):
        validate_transition("filled", "accepted", ORDER_TRANSITIONS)


def test_simulation_is_deterministic_partial_and_never_uses_preapproval_price() -> None:
    signal = datetime(2026, 1, 5, 12, tzinfo=UTC)
    approved = signal + timedelta(minutes=2)
    snapshots = (
        MarketSnapshot(signal + timedelta(minutes=1), Decimal(90), Decimal(10_000), True),
        MarketSnapshot(signal + timedelta(minutes=3), Decimal(100), Decimal(500), True),
        MarketSnapshot(signal + timedelta(minutes=4), Decimal(101), Decimal(500), True),
    )
    inputs = {
        "side": "buy",
        "quantity": Decimal(120),
        "signal_at": signal,
        "approved_at": approved,
        "expires_at": signal + timedelta(minutes=10),
        "snapshots": snapshots,
        "configuration": configuration(),
        "seed": 42,
    }
    first = simulate_order(**inputs)
    second = simulate_order(**inputs)
    assert first == second
    assert first.status == "partially_filled"
    assert first.unfilled_quantity == Decimal(20)
    assert all(fill.market_timestamp >= approved for fill in first.fills)
    assert all(fill.price >= Decimal(100) for fill in first.fills)


def test_limit_order_can_expire_without_silent_fallback() -> None:
    timestamp = datetime(2026, 1, 5, 12, tzinfo=UTC)
    result = simulate_order(
        side="buy",
        quantity=Decimal(10),
        signal_at=timestamp,
        approved_at=timestamp,
        expires_at=timestamp + timedelta(minutes=1),
        snapshots=(MarketSnapshot(timestamp, Decimal(100), Decimal(1_000), True),),
        configuration=configuration(),
        seed=1,
        limit_price=Decimal(99),
    )
    assert result.status == "expired"
    assert result.fills == ()


def test_paper_order_contract_enforces_type_lot_and_market_calendar() -> None:
    opens = datetime(2026, 1, 5, 13, tzinfo=UTC)
    closes = datetime(2026, 1, 5, 20, tzinfo=UTC)
    validate_paper_order_request(
        order_type="limit",
        limit_price=Decimal(100),
        quantity=Decimal(100),
        lot_size=Decimal(10),
        earliest_execution_at=opens,
        expires_at=closes,
        trading_windows=(TradingWindow(opens, closes),),
    )
    with pytest.raises(ValueError, match="whole lot"):
        validate_paper_order_request(
            order_type="market",
            limit_price=None,
            quantity=Decimal(101),
            lot_size=Decimal(10),
            earliest_execution_at=opens,
            expires_at=closes,
            trading_windows=(TradingWindow(opens, closes),),
        )
    with pytest.raises(ValueError, match="open market"):
        validate_paper_order_request(
            order_type="market",
            limit_price=None,
            quantity=Decimal(100),
            lot_size=Decimal(10),
            earliest_execution_at=closes + timedelta(hours=1),
            expires_at=closes + timedelta(hours=2),
            trading_windows=(TradingWindow(opens, closes),),
        )


def test_fill_ledger_preserves_cash_and_cost_signs() -> None:
    timestamp = datetime(2026, 1, 5, 12, tzinfo=UTC)
    result = simulate_order(
        side="sell",
        quantity=Decimal(10),
        signal_at=timestamp,
        approved_at=timestamp,
        expires_at=timestamp + timedelta(minutes=1),
        snapshots=(MarketSnapshot(timestamp, Decimal(100), Decimal(1_000), True),),
        configuration=configuration(),
        seed=1,
    )
    delta = fill_to_ledger("sell", result.fills[0])
    assert delta.instrument_quantity == Decimal(-10)
    assert delta.cash_delta == result.fills[0].gross_value - delta.fees - delta.taxes
    assert delta.cash_delta > 0


def test_reconciliation_and_challenger_decisions_fail_closed() -> None:
    assert reconciliation_is_blocking(quantity_delta=Decimal(1), cash_delta=Decimal(0), tolerance=Decimal("0.01"))
    assert not reconciliation_is_blocking(
        quantity_delta=Decimal(0), cash_delta=Decimal("0.01"), tolerance=Decimal("0.01")
    )
    with pytest.raises(ValueError, match="committee"):
        require_human_challenger_decision("promoted", None)
    require_human_challenger_decision("promoted", "committee-user")


def test_reconciliation_detects_missing_ledger_and_overfill() -> None:
    orders = (ReconciliationOrder("order-1", Decimal(10), Decimal(11), "filled"),)
    fills = (ReconciliationFill("order-1", "fill-1", Decimal(11), Decimal(110), Decimal(1), Decimal(0), "buy"),)
    breaks = reconcile_execution(orders, fills, ())
    assert {item.rule for item in breaks} == {"order_overfill", "order_status", "fill_missing_ledger"}
    assert all(item.blocking for item in breaks if item.severity == "critical")


def test_reconciliation_accepts_exact_append_only_ledger_identity() -> None:
    orders = (ReconciliationOrder("order-1", Decimal(10), Decimal(10), "filled"),)
    fills = (ReconciliationFill("order-1", "fill-1", Decimal(10), Decimal(100), Decimal(1), Decimal(2), "buy"),)
    ledger = (ReconciliationLedgerEntry("paper-fill:fill-1", Decimal(-103), Decimal(10)),)
    assert reconcile_execution(orders, fills, ledger) == ()


def test_post_mortem_and_challenger_require_comparable_lineage() -> None:
    with pytest.raises(ValueError, match="lineage"):
        validate_post_mortem_lineage({"decision": {}})
    validate_post_mortem_lineage(
        {
            "portfolio_version_id": "v1",
            "thesis_version_ids": ["t1"],
            "agent_run_ids": ["a1"],
            "decision": {"approved": True},
            "trade_intent_ids": ["i1"],
            "attribution_by_asset": {"A": "0.01"},
            "attribution_by_sector": {"financials": "0.01"},
            "attribution_by_factor": {"rates": "-0.002"},
            "decision_attribution": "0.003",
            "cost_attribution": "0.001",
            "comparison": {"paper_vs_backtest": "-0.01"},
            "error_classification": "model",
            "corrective_actions": [
                {
                    "action": "recalibrate",
                    "owner_role": "model_risk",
                    "due_at": "2026-08-01T00:00:00Z",
                    "verification": "independent replay",
                }
            ],
        }
    )
    with pytest.raises(ValueError, match="out-of-sample"):
        validate_challenger_comparison(
            {
                "benchmark_id": "b1",
                "risk_policy_version": "r1",
                "cost_model_version": "c1",
                "window_type": "backtest",
                "out_of_sample": True,
            }
        )


def test_paper_attribution_comparison_and_error_classification_are_deterministic() -> None:
    attribution = calculate_paper_attribution(
        weights={"A": Decimal("0.6"), "B": Decimal("0.4")},
        asset_returns={"A": Decimal("0.10"), "B": Decimal("-0.05")},
        sectors={"A": "materials", "B": "financials"},
        factor_exposures={"rates": Decimal("-0.2")},
        factor_returns={"rates": Decimal("0.03")},
        baseline_return=Decimal("0.03"),
        fee_return=Decimal("0.001"),
        tax_return=Decimal("0.0005"),
        slippage_return=Decimal("0.002"),
    )
    assert attribution.gross_return == Decimal("0.040")
    assert attribution.costs == Decimal("0.0035")
    assert attribution.net_return == Decimal("0.0365")
    assert attribution.by_sector == {"materials": Decimal("0.060"), "financials": Decimal("-0.020")}
    comparison = compare_strategy_results(
        expected=Decimal("0.05"), backtest=Decimal("0.04"), paper=attribution.net_return, realized=Decimal("0.03")
    )
    assert comparison["paper_vs_backtest"] == Decimal("-0.0035")
    assert (
        classify_post_mortem_error(
            data_incident=False,
            model_miss=True,
            decision_override=False,
            execution_miss=False,
            operational_break=False,
        )
        == "model"
    )
    assert (
        classify_post_mortem_error(
            data_incident=True,
            model_miss=True,
            decision_override=False,
            execution_miss=False,
            operational_break=False,
        )
        == "mixed"
    )


def test_challenger_uses_same_dated_window_and_fails_closed_on_governance_gates() -> None:
    dates = tuple(datetime(2026, 1, day, tzinfo=UTC) for day in (2, 5, 6))
    champion = tuple(DatedReturn(day, Decimal("0.01")) for day in dates)
    challenger = tuple(DatedReturn(day, Decimal("0.02")) for day in dates)
    benchmark = tuple(DatedReturn(day, Decimal("0.005")) for day in dates)
    criteria = ChallengerCriteria(3, Decimal("0.20"), True, True, True, True)
    assessment = assess_challenger(champion=champion, challenger=challenger, benchmark=benchmark, criteria=criteria)
    assert assessment.eligible
    assert assessment.metrics["challenger_return"] > assessment.metrics["champion_return"]
    assert len(assessment.evidence_sha256) == 64
    blocked = assess_challenger(
        champion=champion,
        challenger=challenger,
        benchmark=benchmark,
        criteria=ChallengerCriteria(4, Decimal("0.20"), False, True, True, True),
    )
    assert blocked.failures == ("insufficient_history", "data_gate")
    with pytest.raises(ValueError, match="identical"):
        assess_challenger(
            champion=champion,
            challenger=challenger[:-1],
            benchmark=benchmark,
            criteria=criteria,
        )
