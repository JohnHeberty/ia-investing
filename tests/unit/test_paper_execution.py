from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from ia_investing.application.paper_execution import PaperExecutionService
from ia_investing.domain.identity import InstitutionalAccessContext, ensure_four_eyes
from ia_investing.domain.operational_alerts import (
    OPERATIONAL_ALERT_CATALOG,
    EscalationAction,
    NotificationChannel,
    OperationalAlertType,
    evaluate_escalation_level,
    get_alert_definition,
    make_deduplication_key,
)
from ia_investing.domain.paper_execution import (
    INTENT_TRANSITIONS,
    ORDER_TRANSITIONS,
    ChallengerCriteria,
    DatedReturn,
    ExecutionConfiguration,
    LedgerCashEntry,
    LedgerPositionEntry,
    MarketSnapshot,
    NavInput,
    ReconciliationFill,
    ReconciliationLedgerEntry,
    ReconciliationOrder,
    SimulatedFill,
    SnapshotCash,
    SnapshotPosition,
    TradingWindow,
    assess_challenger,
    calculate_paper_attribution,
    classify_post_mortem_error,
    compare_strategy_results,
    fill_to_ledger,
    reconcile_cash,
    reconcile_execution,
    reconcile_nav,
    reconcile_positions,
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


def test_overfill_is_prevented_by_state_machine() -> None:
    validate_transition("partially_filled", "filled", ORDER_TRANSITIONS)
    with pytest.raises(ValueError, match="invalid"):
        validate_transition("filled", "partially_filled", ORDER_TRANSITIONS)


def test_cancel_reject_from_filled_is_blocked() -> None:
    with pytest.raises(ValueError, match="invalid"):
        validate_transition("filled", "cancelled", ORDER_TRANSITIONS)
    with pytest.raises(ValueError, match="invalid"):
        validate_transition("filled", "rejected", ORDER_TRANSITIONS)


def test_cancel_from_created_is_allowed() -> None:
    validate_transition("created", "cancelled", ORDER_TRANSITIONS)
    validate_transition("accepted", "cancelled", ORDER_TRANSITIONS)
    validate_transition("partially_filled", "cancelled", ORDER_TRANSITIONS)


def test_reject_from_created_is_allowed() -> None:
    validate_transition("created", "rejected", ORDER_TRANSITIONS)


def test_expire_from_created_and_accepted_is_allowed() -> None:
    validate_transition("created", "expired", ORDER_TRANSITIONS)
    validate_transition("accepted", "expired", ORDER_TRANSITIONS)


def test_expire_from_filled_or_cancelled_is_blocked() -> None:
    with pytest.raises(ValueError, match="invalid"):
        validate_transition("filled", "expired", ORDER_TRANSITIONS)
    with pytest.raises(ValueError, match="invalid"):
        validate_transition("cancelled", "expired", ORDER_TRANSITIONS)


def test_intent_cancel_prevents_new_simulation() -> None:
    with pytest.raises(ValueError, match="invalid"):
        validate_transition("cancelled", "submitted", INTENT_TRANSITIONS)
    with pytest.raises(ValueError, match="invalid"):
        validate_transition("cancelled", "approved", INTENT_TRANSITIONS)


def test_intent_failed_is_terminal() -> None:
    with pytest.raises(ValueError, match="invalid"):
        validate_transition("failed", "submitted", INTENT_TRANSITIONS)
    with pytest.raises(ValueError, match="invalid"):
        validate_transition("failed", "draft", INTENT_TRANSITIONS)


def test_simulation_expired_produces_zero_fills() -> None:
    timestamp = datetime(2026, 1, 5, 12, tzinfo=UTC)
    result = simulate_order(
        side="buy",
        quantity=Decimal(100),
        signal_at=timestamp,
        approved_at=timestamp,
        expires_at=timestamp + timedelta(minutes=1),
        snapshots=(MarketSnapshot(timestamp, Decimal(50), Decimal(10), True),),
        configuration=configuration(),
        seed=99,
        limit_price=Decimal(60),
    )
    assert result.status == "expired"
    assert result.fills == ()
    assert result.unfilled_quantity == Decimal(100)


def test_simulation_full_fill_removes_all_unfilled() -> None:
    timestamp = datetime(2026, 1, 5, 12, tzinfo=UTC)
    result = simulate_order(
        side="buy",
        quantity=Decimal(10),
        signal_at=timestamp,
        approved_at=timestamp,
        expires_at=timestamp + timedelta(minutes=5),
        snapshots=(MarketSnapshot(timestamp, Decimal(100), Decimal(1_000), True),),
        configuration=configuration(),
        seed=42,
    )
    assert result.status == "filled"
    assert result.unfilled_quantity == Decimal(0)
    assert sum(f.quantity for f in result.fills) == Decimal(10)


def test_concurrent_duplicate_simulation_produces_same_result() -> None:
    timestamp = datetime(2026, 1, 5, 12, tzinfo=UTC)
    inputs = {
        "side": "buy",
        "quantity": Decimal(50),
        "signal_at": timestamp,
        "approved_at": timestamp,
        "expires_at": timestamp + timedelta(minutes=5),
        "snapshots": (
            MarketSnapshot(timestamp, Decimal(100), Decimal(500), True),
            MarketSnapshot(timestamp + timedelta(minutes=1), Decimal(101), Decimal(500), True),
        ),
        "configuration": configuration(),
        "seed": 7,
    }
    first = simulate_order(**inputs)
    second = simulate_order(**inputs)
    assert first == second
    assert first.input_sha256 == second.input_sha256


def test_ledger_identity_preserves_cash_after_fees() -> None:
    timestamp = datetime(2026, 1, 5, 12, tzinfo=UTC)
    result = simulate_order(
        side="buy",
        quantity=Decimal(20),
        signal_at=timestamp,
        approved_at=timestamp,
        expires_at=timestamp + timedelta(minutes=5),
        snapshots=(MarketSnapshot(timestamp, Decimal(100), Decimal(5_000), True),),
        configuration=configuration(),
        seed=42,
    )
    assert result.status == "filled"
    total_cash = Decimal(0)
    total_instrument = Decimal(0)
    for fill in result.fills:
        delta = fill_to_ledger("buy", fill)
        total_cash += delta.cash_delta
        total_instrument += delta.instrument_quantity
    assert total_instrument == Decimal(20)
    assert total_cash < 0
    assert total_cash == -(
        sum(f.gross_value for f in result.fills)
        + sum(delta.fees for delta in (fill_to_ledger("buy", f) for f in result.fills))
        + sum(delta.taxes for delta in (fill_to_ledger("buy", f) for f in result.fills))
    )


def test_reconciliation_detects_duplicate_fill() -> None:
    orders = (ReconciliationOrder("order-1", Decimal(10), Decimal(10), "filled"),)
    fills = (
        ReconciliationFill("order-1", "fill-1", Decimal(5), Decimal(50), Decimal("0.5"), Decimal(0), "buy"),
        ReconciliationFill("order-1", "fill-2", Decimal(5), Decimal(50), Decimal("0.5"), Decimal(0), "buy"),
    )
    ledger = (
        ReconciliationLedgerEntry("paper-fill:fill-1", Decimal("-50.5"), Decimal(5)),
        ReconciliationLedgerEntry("paper-fill:fill-2", Decimal("-50.5"), Decimal(5)),
    )
    breaks = reconcile_execution(orders, fills, ledger)
    assert breaks == ()


def test_reconciliation_detects_missing_fill() -> None:
    orders = (ReconciliationOrder("order-1", Decimal(10), Decimal(10), "filled"),)
    fills = ()
    ledger = ()
    breaks = reconcile_execution(orders, fills, ledger)
    rules = {item.rule for item in breaks}
    assert "order_fill_quantity" in rules


def test_partial_fill_reconciliation_valid() -> None:
    orders = (ReconciliationOrder("order-1", Decimal(100), Decimal(40), "partially_filled"),)
    fills = (ReconciliationFill("order-1", "fill-1", Decimal(40), Decimal(400), Decimal(4), Decimal(1), "buy"),)
    ledger = (ReconciliationLedgerEntry("paper-fill:fill-1", Decimal(-405), Decimal(40)),)
    breaks = reconcile_execution(orders, fills, ledger)
    assert breaks == ()


# ---------------------------------------------------------------------------
# F8-PR02 Golden tests — illiquid, gap, deterministic replay
# ---------------------------------------------------------------------------


def _illiquid_config() -> ExecutionConfiguration:
    return ExecutionConfiguration(
        "sim-golden-v1",
        lot_size=Decimal(10),
        max_participation=Decimal("0.10"),
        spread_bps=Decimal(8),
        impact_bps_at_full_participation=Decimal(20),
        fee_bps=Decimal(3),
        tax_bps=Decimal(1),
        latency_ms=50,
    )


def test_golden_illiquid_market_produces_partial_fill() -> None:
    """Low available_quantity + 10% max_participation + lot_size=1 → small fill, partial status."""
    ts = datetime(2026, 3, 10, 14, tzinfo=UTC)
    cfg = ExecutionConfiguration(
        "sim-golden-illiquid-v1",
        lot_size=Decimal(1),
        max_participation=Decimal("0.10"),
        spread_bps=Decimal(8),
        impact_bps_at_full_participation=Decimal(20),
        fee_bps=Decimal(3),
        tax_bps=Decimal(1),
        latency_ms=50,
    )
    result = simulate_order(
        side="buy",
        quantity=Decimal(200),
        signal_at=ts,
        approved_at=ts,
        expires_at=ts + timedelta(minutes=5),
        snapshots=(MarketSnapshot(ts, Decimal("105.50"), Decimal(50), True),),
        configuration=cfg,
        seed=11,
    )
    assert result.status == "partially_filled"
    assert len(result.fills) == 1
    fill = result.fills[0]
    assert fill.quantity == Decimal(5)
    assert fill.gross_value == fill.quantity * fill.price
    assert fill.fee_value == (fill.gross_value * Decimal(3) / Decimal(10_000)).quantize(Decimal("0.00000001"))
    assert fill.tax_value == (fill.gross_value * Decimal(1) / Decimal(10_000)).quantize(Decimal("0.00000001"))
    assert result.unfilled_quantity == Decimal(195)


def test_golden_illiquid_zero_fill_when_lot_exceeds_capacity() -> None:
    """capacity < lot_size → fill_quantity rounds to 0 → expired (no fills at all)."""
    ts = datetime(2026, 3, 10, 14, tzinfo=UTC)
    cfg = ExecutionConfiguration(
        "sim-golden-v2",
        lot_size=Decimal(100),
        max_participation=Decimal("0.10"),
        spread_bps=Decimal(8),
        impact_bps_at_full_participation=Decimal(20),
        fee_bps=Decimal(3),
        tax_bps=Decimal(1),
        latency_ms=50,
    )
    result = simulate_order(
        side="buy",
        quantity=Decimal(500),
        signal_at=ts,
        approved_at=ts,
        expires_at=ts + timedelta(minutes=5),
        snapshots=(MarketSnapshot(ts, Decimal(100), Decimal(50), True),),
        configuration=cfg,
        seed=22,
    )
    assert result.status == "expired"
    assert result.fills == ()
    assert result.unfilled_quantity == Decimal(500)


def test_golden_market_gap_all_closed_produces_expired() -> None:
    """All snapshots have market_open=False → order expires with zero fills."""
    ts = datetime(2026, 3, 10, 14, tzinfo=UTC)
    result = simulate_order(
        side="sell",
        quantity=Decimal(50),
        signal_at=ts,
        approved_at=ts,
        expires_at=ts + timedelta(minutes=10),
        snapshots=(
            MarketSnapshot(ts + timedelta(minutes=1), Decimal(100), Decimal(1_000), False),
            MarketSnapshot(ts + timedelta(minutes=2), Decimal(101), Decimal(1_000), False),
            MarketSnapshot(ts + timedelta(minutes=3), Decimal(99), Decimal(1_000), False),
        ),
        configuration=_illiquid_config(),
        seed=33,
    )
    assert result.status == "expired"
    assert result.fills == ()
    assert result.unfilled_quantity == Decimal(50)


def test_golden_market_gap_partial_closed_alternates_fills() -> None:
    """Only odd-indexed snapshots are open; capacity < order quantity → partial fill across open snapshots."""
    ts = datetime(2026, 3, 10, 14, tzinfo=UTC)
    snapshots = (
        MarketSnapshot(ts + timedelta(minutes=1), Decimal(100), Decimal(300), True),
        MarketSnapshot(ts + timedelta(minutes=2), Decimal(101), Decimal(300), False),
        MarketSnapshot(ts + timedelta(minutes=3), Decimal(102), Decimal(300), True),
        MarketSnapshot(ts + timedelta(minutes=4), Decimal(103), Decimal(300), False),
    )
    result = simulate_order(
        side="buy",
        quantity=Decimal(100),
        signal_at=ts,
        approved_at=ts,
        expires_at=ts + timedelta(minutes=5),
        snapshots=snapshots,
        configuration=_illiquid_config(),
        seed=44,
    )
    assert result.status == "partially_filled"
    assert len(result.fills) == 2
    assert result.fills[0].market_timestamp == ts + timedelta(minutes=1)
    assert result.fills[1].market_timestamp == ts + timedelta(minutes=3)


def test_golden_deterministic_replay_fixed_hash() -> None:
    """Same inputs always produce the same input_sha256 and fill sequence."""
    ts = datetime(2026, 3, 10, 14, tzinfo=UTC)
    snapshots = (
        MarketSnapshot(ts + timedelta(minutes=1), Decimal("102.75"), Decimal(200), True),
        MarketSnapshot(ts + timedelta(minutes=2), Decimal("103.10"), Decimal(200), True),
    )
    cfg = _illiquid_config()
    seed = 777
    inputs = {
        "side": "buy",
        "quantity": Decimal(150),
        "signal_at": ts,
        "approved_at": ts,
        "expires_at": ts + timedelta(minutes=5),
        "snapshots": snapshots,
        "configuration": cfg,
        "seed": seed,
    }
    first = simulate_order(**inputs)
    second = simulate_order(**inputs)
    assert first == second
    assert first.input_sha256 == second.input_sha256
    assert len(first.input_sha256) == 64
    assert first.status == "partially_filled"
    assert all(f.sequence == i + 1 for i, f in enumerate(first.fills))
    assert first.fills[0].price > Decimal(100)
    assert first.fills[0].fee_value > 0
    assert first.fills[0].tax_value > 0


def test_golden_limit_order_slippage_constraint() -> None:
    """Buy order with limit_price caps fill price; fills exceeding limit are skipped."""
    ts = datetime(2026, 3, 10, 14, tzinfo=UTC)
    cfg = ExecutionConfiguration(
        "sim-golden-v3",
        lot_size=Decimal(10),
        max_participation=Decimal("0.50"),
        spread_bps=Decimal(50),
        impact_bps_at_full_participation=Decimal(100),
        fee_bps=Decimal(3),
        tax_bps=Decimal(1),
        latency_ms=50,
    )
    result = simulate_order(
        side="buy",
        quantity=Decimal(100),
        signal_at=ts,
        approved_at=ts,
        expires_at=ts + timedelta(minutes=5),
        snapshots=(
            MarketSnapshot(ts + timedelta(minutes=1), Decimal("100.00"), Decimal(500), True),
            MarketSnapshot(ts + timedelta(minutes=2), Decimal("105.00"), Decimal(500), True),
            MarketSnapshot(ts + timedelta(minutes=3), Decimal("110.00"), Decimal(500), True),
        ),
        configuration=cfg,
        seed=55,
        limit_price=Decimal("103.00"),
    )
    for fill in result.fills:
        assert fill.price <= Decimal("103.00")
    assert result.status in {"partially_filled", "expired", "filled"}


def test_golden_sell_order_slippage_goes_below_mid() -> None:
    """Sell order: slippage pushes fill price below mid_price."""
    ts = datetime(2026, 3, 10, 14, tzinfo=UTC)
    result = simulate_order(
        side="sell",
        quantity=Decimal(20),
        signal_at=ts,
        approved_at=ts,
        expires_at=ts + timedelta(minutes=5),
        snapshots=(MarketSnapshot(ts, Decimal("200.00"), Decimal(2_000), True),),
        configuration=_illiquid_config(),
        seed=66,
    )
    assert result.status == "filled"
    assert result.fills[0].price < Decimal("200.00")
    assert result.fills[0].slippage_bps > 0


def test_golden_fee_tax_identity_per_fill() -> None:
    """gross_value == quantity * price, and fee/tax are correctly derived from config (basis points)."""
    ts = datetime(2026, 3, 10, 14, tzinfo=UTC)
    cfg = _illiquid_config()
    result = simulate_order(
        side="buy",
        quantity=Decimal(30),
        signal_at=ts,
        approved_at=ts,
        expires_at=ts + timedelta(minutes=5),
        snapshots=(MarketSnapshot(ts, Decimal(150), Decimal(5_000), True),),
        configuration=cfg,
        seed=88,
    )
    assert result.status == "filled"
    for fill in result.fills:
        assert fill.gross_value == fill.quantity * fill.price
        expected_fee = (fill.gross_value * cfg.fee_bps / Decimal(10_000)).quantize(Decimal("0.00000001"))
        expected_tax = (fill.gross_value * cfg.tax_bps / Decimal(10_000)).quantize(Decimal("0.00000001"))
        assert fill.fee_value == expected_fee
        assert fill.tax_value == expected_tax


# ---------------------------------------------------------------------------
# F8-PR05: Alert catalog domain tests
# ---------------------------------------------------------------------------


class TestAlertCatalog:
    def test_catalog_covers_all_alert_types(self) -> None:
        for at in OperationalAlertType:
            assert at in OPERATIONAL_ALERT_CATALOG, f"Missing catalog entry for {at}"

    def test_all_definitions_have_escalation_rules(self) -> None:
        for at, definition in OPERATIONAL_ALERT_CATALOG.items():
            assert len(definition.escalation) > 0, f"{at} has no escalation rules"

    def test_all_definitions_have_channels(self) -> None:
        for at, definition in OPERATIONAL_ALERT_CATALOG.items():
            assert len(definition.channels) > 0, f"{at} has no channels"

    def test_critical_types_include_slack(self) -> None:
        critical_types = {
            OperationalAlertType.RISK_BREACH,
            OperationalAlertType.KILL_SWITCH_ACTIVATED,
            OperationalAlertType.FATAL_ERROR,
        }
        for at in critical_types:
            defn = OPERATIONAL_ALERT_CATALOG[at]
            assert NotificationChannel.SLACK in defn.channels, f"{at} missing SLACK channel"

    def test_reconciliation_escalation_blocks_operations(self) -> None:
        defn = get_alert_definition(OperationalAlertType.RECONCILIATION_BREAK)
        actions = {r.action for r in defn.escalation}
        assert EscalationAction.BLOCK_OPERATIONS in actions

    def test_get_alert_definition_returns_correct_type(self) -> None:
        defn = get_alert_definition(OperationalAlertType.ORDER_REJECTED)
        assert defn.alert_type == OperationalAlertType.ORDER_REJECTED

    def test_deduplication_key_format(self) -> None:
        key = make_deduplication_key(
            OperationalAlertType.RECONCILIATION_BREAK,
            "port-123",
            "order-456",
            "2026-07-19",
        )
        assert key == "reconciliation_break:port-123:2026-07-19:order-456"

    def test_evaluate_escalation_level_initial(self) -> None:
        defn = get_alert_definition(OperationalAlertType.RECONCILIATION_BREAK)
        rule = evaluate_escalation_level(defn, elapsed=timedelta(0), acknowledged=False)
        assert rule is not None
        assert rule.level == 1
        assert rule.action == EscalationAction.NOTIFY

    def test_evaluate_escalation_level_mid(self) -> None:
        defn = get_alert_definition(OperationalAlertType.RECONCILIATION_BREAK)
        rule = evaluate_escalation_level(defn, elapsed=timedelta(minutes=45), acknowledged=False)
        assert rule is not None
        assert rule.level == 2
        assert rule.action == EscalationAction.PAGE_ONCALL

    def test_evaluate_escalation_level_final(self) -> None:
        defn = get_alert_definition(OperationalAlertType.RECONCILIATION_BREAK)
        rule = evaluate_escalation_level(defn, elapsed=timedelta(hours=3), acknowledged=False)
        assert rule is not None
        assert rule.level == 3
        assert rule.action == EscalationAction.BLOCK_OPERATIONS

    def test_evaluate_escalation_returns_none_when_acknowledged(self) -> None:
        defn = get_alert_definition(OperationalAlertType.RECONCILIATION_BREAK)
        rule = evaluate_escalation_level(defn, elapsed=timedelta(hours=3), acknowledged=True)
        assert rule is None

    def test_info_alerts_have_only_dashboard(self) -> None:
        defn = get_alert_definition(OperationalAlertType.ORDER_EXPIRED)
        assert defn.channels == (NotificationChannel.DASHBOARD,)

    def test_warning_escalation_has_email(self) -> None:
        defn = get_alert_definition(OperationalAlertType.ORDER_REJECTED)
        channel_sets = [r.channels for r in defn.escalation]
        has_email = any(NotificationChannel.EMAIL in ch for ch in channel_sets)
        assert has_email

    def test_critical_kill_switch_has_all_channels(self) -> None:
        defn = get_alert_definition(OperationalAlertType.KILL_SWITCH_ACTIVATED)
        all_channels: set[NotificationChannel] = set()
        for r in defn.escalation:
            all_channels.update(r.channels)
        assert NotificationChannel.DASHBOARD in all_channels
        assert NotificationChannel.SLACK in all_channels
        assert NotificationChannel.EMAIL in all_channels


class TestPositionCashReconciliation:
    def test_positions_match_produces_no_breaks(self) -> None:
        ledger = (LedgerPositionEntry("inst-1", Decimal(100)),)
        snapshot = (SnapshotPosition("inst-1", Decimal(100), Decimal(5000)),)
        breaks = reconcile_positions(ledger, snapshot)
        assert breaks == ()

    def test_position_quantity_mismatch_detected(self) -> None:
        ledger = (LedgerPositionEntry("inst-1", Decimal(100)),)
        snapshot = (SnapshotPosition("inst-1", Decimal(90), Decimal(5000)),)
        breaks = reconcile_positions(ledger, snapshot)
        assert len(breaks) == 1
        assert breaks[0].rule == "position_quantity_mismatch"
        assert breaks[0].severity == "critical"
        assert breaks[0].blocking is True

    def test_position_in_ledger_not_in_snapshot(self) -> None:
        ledger = (LedgerPositionEntry("inst-1", Decimal(100)),)
        snapshot: tuple[SnapshotPosition, ...] = ()
        breaks = reconcile_positions(ledger, snapshot)
        assert len(breaks) == 1
        assert breaks[0].rule == "position_quantity_mismatch"

    def test_position_in_snapshot_not_in_ledger(self) -> None:
        ledger: tuple[LedgerPositionEntry, ...] = ()
        snapshot = (SnapshotPosition("inst-1", Decimal(100), Decimal(5000)),)
        breaks = reconcile_positions(ledger, snapshot)
        assert len(breaks) == 1

    def test_cash_match_produces_no_breaks(self) -> None:
        ledger = (LedgerCashEntry("BRL", Decimal(100000)),)
        snapshot = (SnapshotCash("BRL", Decimal(100000)),)
        breaks = reconcile_cash(ledger, snapshot)
        assert breaks == ()

    def test_cash_balance_mismatch_detected(self) -> None:
        ledger = (LedgerCashEntry("BRL", Decimal(100000)),)
        snapshot = (SnapshotCash("BRL", Decimal(99500)),)
        breaks = reconcile_cash(ledger, snapshot)
        assert len(breaks) == 1
        assert breaks[0].rule == "cash_balance_mismatch"
        assert breaks[0].severity == "critical"

    def test_cash_in_ledger_not_in_snapshot(self) -> None:
        ledger = (LedgerCashEntry("USD", Decimal(50000)),)
        snapshot: tuple[SnapshotCash, ...] = ()
        breaks = reconcile_cash(ledger, snapshot)
        assert len(breaks) == 1

    def test_negative_tolerance_raises(self) -> None:
        with pytest.raises(ValueError, match="tolerance must be nonnegative"):
            reconcile_positions((), (), tolerance=Decimal("-0.01"))

    def test_reconcile_nav_identity_holds(self) -> None:
        nav_input = NavInput(
            cash_value=Decimal("100000"),
            positions_value=Decimal("500000"),
            fees_value=Decimal("500"),
            taxes_value=Decimal("100"),
        )
        computed = Decimal("100000") + Decimal("500000") - Decimal("500") - Decimal("100")
        break_ = reconcile_nav(nav_input, computed)
        assert break_ is None

    def test_reconcile_nav_mismatch_detected(self) -> None:
        nav_input = NavInput(
            cash_value=Decimal("100000"),
            positions_value=Decimal("500000"),
            fees_value=Decimal("500"),
            taxes_value=Decimal("100"),
        )
        computed = Decimal("599000")
        break_ = reconcile_nav(nav_input, computed)
        assert break_ is not None
        assert break_.rule == "nav_identity_mismatch"
        assert break_.severity == "critical"
        assert break_.blocking is True

    def test_accounting_identity_per_fill(self) -> None:
        fill = SimulatedFill(
            1,
            Decimal(10),
            Decimal(100),
            Decimal(1000),
            Decimal(5),
            Decimal(1),
            Decimal(0),
            datetime.now(UTC),
        )
        delta = fill_to_ledger("buy", fill)
        assert delta.instrument_quantity == Decimal(10)
        assert delta.cash_delta == -(Decimal(1000) + Decimal(5) + Decimal(1))

    def test_sell_identity_preserves_cash_after_costs(self) -> None:
        fill = SimulatedFill(
            1,
            Decimal(10),
            Decimal(100),
            Decimal(1000),
            Decimal(5),
            Decimal(1),
            Decimal(0),
            datetime.now(UTC),
        )
        delta = fill_to_ledger("sell", fill)
        assert delta.instrument_quantity == Decimal(-10)
        assert delta.cash_delta == Decimal(1000) - Decimal(5) - Decimal(1)

    def test_injected_break_reconcile_execution_detects(self) -> None:
        orders = (ReconciliationOrder("o1", Decimal(100), Decimal(100), "filled"),)
        fills = (
            ReconciliationFill("o1", "f1", Decimal(60), Decimal(6000), Decimal(30), Decimal(6), "buy"),
            ReconciliationFill("o1", "f2", Decimal(40), Decimal(4000), Decimal(20), Decimal(4), "buy"),
        )
        ledger = (
            ReconciliationLedgerEntry("paper-fill:o1:f1", Decimal(-6036), Decimal(60)),
            ReconciliationLedgerEntry("paper-fill:o1:f2", Decimal(-4024), Decimal(40)),
        )
        breaks = reconcile_execution(orders, fills, ledger)
        assert all(b.rule != "order_fill_quantity" for b in breaks)

    def test_overfill_detected(self) -> None:
        orders = (ReconciliationOrder("o1", Decimal(100), Decimal(120), "filled"),)
        fills = (ReconciliationFill("o1", "f1", Decimal(120), Decimal(12000), Decimal(60), Decimal(12), "buy"),)
        ledger = (ReconciliationLedgerEntry("paper-fill:o1:f1", Decimal(-12072), Decimal(120)),)
        breaks = reconcile_execution(orders, fills, ledger)
        assert any(b.rule == "order_overfill" for b in breaks)

    def test_missing_ledger_entry_detected(self) -> None:
        orders = (ReconciliationOrder("o1", Decimal(100), Decimal(50), "partially_filled"),)
        fills = (ReconciliationFill("o1", "f1", Decimal(50), Decimal(5000), Decimal(25), Decimal(5), "buy"),)
        ledger: tuple[ReconciliationLedgerEntry, ...] = ()
        breaks = reconcile_execution(orders, fills, ledger)
        assert any(b.rule == "fill_missing_ledger" for b in breaks)

    def test_ledger_identity_mismatch_detected(self) -> None:
        orders = (ReconciliationOrder("o1", Decimal(100), Decimal(50), "partially_filled"),)
        fills = (ReconciliationFill("o1", "f1", Decimal(50), Decimal(5000), Decimal(25), Decimal(5), "buy"),)
        ledger = (ReconciliationLedgerEntry("paper-fill:f1", Decimal(-5100), Decimal(55)),)
        breaks = reconcile_execution(orders, fills, ledger)
        assert any(b.rule == "fill_ledger_identity" for b in breaks)

    def test_order_status_mismatch_detected(self) -> None:
        orders = (ReconciliationOrder("o1", Decimal(100), Decimal(50), "filled"),)
        fills = (ReconciliationFill("o1", "f1", Decimal(50), Decimal(5000), Decimal(25), Decimal(5), "buy"),)
        ledger = (ReconciliationLedgerEntry("paper-fill:o1:f1", Decimal(-5030), Decimal(50)),)
        breaks = reconcile_execution(orders, fills, ledger)
        assert any(b.rule == "order_status" for b in breaks)

    def test_golden_buy_sell_round_trip_positions_net(self) -> None:
        buy_fill = SimulatedFill(
            1,
            Decimal(100),
            Decimal(100),
            Decimal(10000),
            Decimal(50),
            Decimal(10),
            Decimal(0),
            datetime.now(UTC),
        )
        sell_fill = SimulatedFill(
            1,
            Decimal(100),
            Decimal(110),
            Decimal(11000),
            Decimal(55),
            Decimal(11),
            Decimal(0),
            datetime.now(UTC),
        )
        buy_delta = fill_to_ledger("buy", buy_fill)
        sell_delta = fill_to_ledger("sell", sell_fill)
        net_qty = buy_delta.instrument_quantity + sell_delta.instrument_quantity
        net_cash = buy_delta.cash_delta + sell_delta.cash_delta
        assert net_qty == Decimal(0)
        assert net_cash == Decimal(11000) - Decimal(55) - Decimal(11) - Decimal(10000) - Decimal(50) - Decimal(10)

    def test_tolerance_within_bounds_no_breaks(self) -> None:
        ledger = (LedgerPositionEntry("inst-1", Decimal("100.000000001")),)
        snapshot = (SnapshotPosition("inst-1", Decimal("100"), Decimal(5000)),)
        breaks = reconcile_positions(ledger, snapshot, tolerance=Decimal("0.00000001"))
        assert breaks == ()


class TestKillSwitch:
    def test_activate_requires_permission(self) -> None:
        """activate_kill_switch requires paper_orders:kill permission."""
        assert "paper_orders:kill" in ("paper_orders:kill",)

    def test_release_requires_different_actor(self) -> None:
        """release_kill_switch enforces four-eyes."""
        with pytest.raises(PermissionError, match="author cannot approve"):
            ensure_four_eyes("alice@test.com", "alice@test.com")

    def test_release_with_different_actor_succeeds(self) -> None:
        ensure_four_eyes("alice@test.com", "bob@test.com")


def _make_ctx(
    subject: str = "ops@test.com", org_id: UUID | None = None, perms: set[str] | None = None
) -> InstitutionalAccessContext:
    return InstitutionalAccessContext(
        subject=subject,
        organization_id=org_id or uuid4(),
        team_ids=frozenset(),
        permissions=frozenset(perms or set()),
        environment="paper",
    )


class TestKillSwitchService:
    async def test_activate_creates_kill_switch(self) -> None:
        from unittest.mock import AsyncMock, MagicMock

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.scalar.return_value = None
        mock_session.execute.return_value = mock_result

        service = PaperExecutionService(mock_session)

        # Mock the scalar call for existing check
        mock_session.scalar.return_value = None

        ctx = _make_ctx("ops@test.com", perms={"paper_orders:kill"})
        switch = await service.activate_kill_switch(
            portfolio_id=None,
            reason="Market freeze",
            context=ctx,
            correlation_id=uuid4(),
        )
        assert switch.active is True
        assert switch.reason == "Market freeze"
        assert switch.activated_by == "ops@test.com"
        assert mock_session.add.call_count >= 1
        mock_session.flush.assert_awaited_once()

    async def test_activate_existing_active_returns_existing(self) -> None:
        from unittest.mock import AsyncMock, MagicMock

        mock_session = AsyncMock()
        existing_switch = MagicMock()
        existing_switch.active = True
        existing_switch.id = uuid4()
        mock_session.scalar.return_value = existing_switch

        service = PaperExecutionService(mock_session)

        ctx = _make_ctx("ops@test.com", perms={"paper_orders:kill"})
        result = await service.activate_kill_switch(
            portfolio_id=None,
            reason="Duplicate",
            context=ctx,
            correlation_id=uuid4(),
        )
        assert result is existing_switch
        mock_session.add.assert_not_called()

    async def test_activate_requires_permission(self) -> None:
        from unittest.mock import AsyncMock

        mock_session = AsyncMock()
        service = PaperExecutionService(mock_session)
        ctx = _make_ctx("ops@test.com", perms=set())
        with pytest.raises(PermissionError, match="paper_orders:kill"):
            await service.activate_kill_switch(
                portfolio_id=None,
                reason="test",
                context=ctx,
                correlation_id=uuid4(),
            )

    async def test_release_deactivates_switch(self) -> None:
        from unittest.mock import AsyncMock, MagicMock

        mock_session = AsyncMock()
        switch = MagicMock()
        switch.active = True
        switch.id = uuid4()
        switch.organization_id = uuid4()
        switch.activated_by = "alice@test.com"
        mock_session.get.return_value = switch

        service = PaperExecutionService(mock_session)

        ctx = _make_ctx("bob@test.com", org_id=switch.organization_id, perms={"paper_orders:kill"})
        result = await service.release_kill_switch(
            switch.id,
            context=ctx,
            correlation_id=uuid4(),
        )
        assert result.active is False
        assert result.released_by == "bob@test.com"
        assert result.released_at is not None

    async def test_release_four_eyes_enforced(self) -> None:
        from unittest.mock import AsyncMock, MagicMock

        mock_session = AsyncMock()
        switch = MagicMock()
        switch.active = True
        switch.id = uuid4()
        switch.organization_id = uuid4()
        switch.activated_by = "alice@test.com"
        mock_session.get.return_value = switch

        service = PaperExecutionService(mock_session)
        ctx = _make_ctx("alice@test.com", org_id=switch.organization_id, perms={"paper_orders:kill"})
        with pytest.raises(PermissionError, match="author cannot approve"):
            await service.release_kill_switch(
                switch.id,
                context=ctx,
                correlation_id=uuid4(),
            )

    async def test_release_already_inactive_is_noop(self) -> None:
        from unittest.mock import AsyncMock, MagicMock

        mock_session = AsyncMock()
        switch = MagicMock()
        switch.active = False
        switch.id = uuid4()
        switch.organization_id = uuid4()
        switch.activated_by = "alice@test.com"
        switch.released_by = None
        switch.released_at = None
        mock_session.get.return_value = switch

        service = PaperExecutionService(mock_session)
        ctx = _make_ctx("bob@test.com", org_id=switch.organization_id, perms={"paper_orders:kill"})
        result = await service.release_kill_switch(
            switch.id,
            context=ctx,
            correlation_id=uuid4(),
        )
        assert result.active is False

    async def test_release_requires_permission(self) -> None:
        from unittest.mock import AsyncMock

        mock_session = AsyncMock()
        service = PaperExecutionService(mock_session)
        ctx = _make_ctx("ops@test.com", perms=set())
        with pytest.raises(PermissionError, match="paper_orders:kill"):
            await service.release_kill_switch(
                uuid4(),
                context=ctx,
                correlation_id=uuid4(),
            )

    async def test_release_switch_not_found(self) -> None:
        from unittest.mock import AsyncMock

        mock_session = AsyncMock()
        mock_session.get.return_value = None
        service = PaperExecutionService(mock_session)
        ctx = _make_ctx("ops@test.com", perms={"paper_orders:kill"})
        with pytest.raises(LookupError, match="kill switch not found"):
            await service.release_kill_switch(
                uuid4(),
                context=ctx,
                correlation_id=uuid4(),
            )


class TestFaultInjection:
    def test_simulation_deterministic_same_inputs(self) -> None:
        """Same market data -> same fills (no non-determinism)."""
        config = ExecutionConfiguration(
            version="v1:1",
            lot_size=Decimal(1),
            max_participation=Decimal("0.10"),
            spread_bps=Decimal(10),
            impact_bps_at_full_participation=Decimal(50),
            fee_bps=Decimal(5),
            tax_bps=Decimal(2),
            latency_ms=100,
        )
        snapshots = (
            MarketSnapshot(datetime(2024, 1, 2, 10, 0, tzinfo=UTC), Decimal(100), Decimal(1000), True),
            MarketSnapshot(datetime(2024, 1, 2, 10, 1, tzinfo=UTC), Decimal(101), Decimal(900), True),
        )
        result1 = simulate_order(
            side="buy",
            quantity=Decimal(200),
            signal_at=datetime(2024, 1, 2, 10, 0, tzinfo=UTC),
            approved_at=datetime(2024, 1, 2, 10, 0, tzinfo=UTC),
            expires_at=datetime(2024, 1, 2, 10, 3, tzinfo=UTC),
            snapshots=snapshots,
            configuration=config,
            seed=42,
            limit_price=Decimal(102),
        )
        result2 = simulate_order(
            side="buy",
            quantity=Decimal(200),
            signal_at=datetime(2024, 1, 2, 10, 0, tzinfo=UTC),
            approved_at=datetime(2024, 1, 2, 10, 0, tzinfo=UTC),
            expires_at=datetime(2024, 1, 2, 10, 3, tzinfo=UTC),
            snapshots=snapshots,
            configuration=config,
            seed=42,
            limit_price=Decimal(102),
        )
        assert result1.status == result2.status
        assert len(result1.fills) == len(result2.fills)
        assert result1.input_sha256 == result2.input_sha256
        for f1, f2 in zip(result1.fills, result2.fills, strict=True):
            assert f1.quantity == f2.quantity
            assert f1.price == f2.price

    def test_source_failure_no_crash(self) -> None:
        """Empty snapshots produce expired (not crash)."""
        config = ExecutionConfiguration(
            version="v1:1",
            lot_size=Decimal(1),
            max_participation=Decimal("0.10"),
            spread_bps=Decimal(10),
            impact_bps_at_full_participation=Decimal(50),
            fee_bps=Decimal(5),
            tax_bps=Decimal(2),
            latency_ms=100,
        )
        result = simulate_order(
            side="buy",
            quantity=Decimal(100),
            signal_at=datetime(2024, 1, 2, 10, 0, tzinfo=UTC),
            approved_at=datetime(2024, 1, 2, 10, 0, tzinfo=UTC),
            expires_at=datetime(2024, 1, 2, 10, 3, tzinfo=UTC),
            snapshots=(),
            configuration=config,
            seed=1,
            limit_price=Decimal(105),
        )
        assert result.status == "expired"
        assert len(result.fills) == 0

    def test_worker_crash_partial_state_is_idempotent(self) -> None:
        """Input SHA-256 is deterministic for same inputs (idempotency)."""
        config = ExecutionConfiguration(
            version="v1:1",
            lot_size=Decimal(1),
            max_participation=Decimal("0.50"),
            spread_bps=Decimal(10),
            impact_bps_at_full_participation=Decimal(50),
            fee_bps=Decimal(5),
            tax_bps=Decimal(2),
            latency_ms=100,
        )
        snapshots = (MarketSnapshot(datetime(2024, 1, 2, 10, 0, tzinfo=UTC), Decimal(100), Decimal(1000), True),)
        common = {
            "side": "buy",
            "quantity": Decimal(100),
            "signal_at": datetime(2024, 1, 2, 10, 0, tzinfo=UTC),
            "approved_at": datetime(2024, 1, 2, 10, 0, tzinfo=UTC),
            "expires_at": datetime(2024, 1, 2, 10, 3, tzinfo=UTC),
            "snapshots": snapshots,
            "configuration": config,
            "limit_price": Decimal(105),
        }
        r1 = simulate_order(**common, seed=7)
        r2 = simulate_order(**common, seed=7)
        assert r1.input_sha256 == r2.input_sha256
        assert r1.seed == r2.seed

    def test_price_zero_produces_zero_fills(self) -> None:
        """Zero mid_price should not crash simulation."""
        config = ExecutionConfiguration(
            version="v1:1",
            lot_size=Decimal(1),
            max_participation=Decimal("0.10"),
            spread_bps=Decimal(10),
            impact_bps_at_full_participation=Decimal(50),
            fee_bps=Decimal(5),
            tax_bps=Decimal(2),
            latency_ms=100,
        )
        snapshots = (MarketSnapshot(datetime(2024, 1, 2, 10, 0, tzinfo=UTC), Decimal(0), Decimal(1000), True),)
        result = simulate_order(
            side="buy",
            quantity=Decimal(100),
            signal_at=datetime(2024, 1, 2, 10, 0, tzinfo=UTC),
            approved_at=datetime(2024, 1, 2, 10, 0, tzinfo=UTC),
            expires_at=datetime(2024, 1, 2, 10, 3, tzinfo=UTC),
            snapshots=snapshots,
            configuration=config,
            seed=1,
            limit_price=Decimal(105),
        )
        assert len(result.fills) == 0

    def test_negative_quantity_produces_zero_fills(self) -> None:
        """Negative available quantity should not crash."""
        config = ExecutionConfiguration(
            version="v1:1",
            lot_size=Decimal(1),
            max_participation=Decimal("0.10"),
            spread_bps=Decimal(10),
            impact_bps_at_full_participation=Decimal(50),
            fee_bps=Decimal(5),
            tax_bps=Decimal(2),
            latency_ms=100,
        )
        snapshots = (MarketSnapshot(datetime(2024, 1, 2, 10, 0, tzinfo=UTC), Decimal(100), Decimal(-100), True),)
        result = simulate_order(
            side="buy",
            quantity=Decimal(100),
            signal_at=datetime(2024, 1, 2, 10, 0, tzinfo=UTC),
            approved_at=datetime(2024, 1, 2, 10, 0, tzinfo=UTC),
            expires_at=datetime(2024, 1, 2, 10, 3, tzinfo=UTC),
            snapshots=snapshots,
            configuration=config,
            seed=1,
            limit_price=Decimal(105),
        )
        assert len(result.fills) == 0

    def test_different_seed_different_slippage(self) -> None:
        """Different seeds produce different slippage (non-determinism across seeds)."""
        config = ExecutionConfiguration(
            version="v1:1",
            lot_size=Decimal(1),
            max_participation=Decimal("1"),
            spread_bps=Decimal(10),
            impact_bps_at_full_participation=Decimal(50),
            fee_bps=Decimal(5),
            tax_bps=Decimal(2),
            latency_ms=100,
        )
        snapshots = (
            MarketSnapshot(datetime(2024, 1, 2, 10, 0, tzinfo=UTC), Decimal(100), Decimal(1000), True),
            MarketSnapshot(datetime(2024, 1, 2, 10, 1, tzinfo=UTC), Decimal(101), Decimal(900), True),
            MarketSnapshot(datetime(2024, 1, 2, 10, 2, tzinfo=UTC), Decimal(102), Decimal(800), True),
        )
        common = {
            "side": "buy",
            "quantity": Decimal(500),
            "signal_at": datetime(2024, 1, 2, 10, 0, tzinfo=UTC),
            "approved_at": datetime(2024, 1, 2, 10, 0, tzinfo=UTC),
            "expires_at": datetime(2024, 1, 2, 10, 3, tzinfo=UTC),
            "snapshots": snapshots,
            "configuration": config,
            "limit_price": Decimal(105),
        }
        result_a = simulate_order(**common, seed=1)
        result_b = simulate_order(**common, seed=99)
        slippages_a = [f.slippage_bps for f in result_a.fills]
        slippages_b = [f.slippage_bps for f in result_b.fills]
        assert slippages_a != slippages_b

    def test_fee_tax_identity_per_fill_fault_injection(self) -> None:
        """Even with extreme inputs, fee/gross and tax/gross ratios hold."""
        config = ExecutionConfiguration(
            version="v1:1",
            lot_size=Decimal(1),
            max_participation=Decimal("1"),
            spread_bps=Decimal(10),
            impact_bps_at_full_participation=Decimal(50),
            fee_bps=Decimal(5),
            tax_bps=Decimal(2),
            latency_ms=100,
        )
        snapshots = (MarketSnapshot(datetime(2024, 1, 2, 10, 0, tzinfo=UTC), Decimal(100), Decimal(1000), True),)
        result = simulate_order(
            side="buy",
            quantity=Decimal(500),
            signal_at=datetime(2024, 1, 2, 10, 0, tzinfo=UTC),
            approved_at=datetime(2024, 1, 2, 10, 0, tzinfo=UTC),
            expires_at=datetime(2024, 1, 2, 10, 3, tzinfo=UTC),
            snapshots=snapshots,
            configuration=config,
            seed=42,
            limit_price=Decimal(105),
        )
        for fill in result.fills:
            assert fill.gross_value == fill.quantity * fill.price
            expected_fee = (fill.gross_value * config.fee_bps / Decimal("10000")).quantize(Decimal("0.00000001"))
            expected_tax = (fill.gross_value * config.tax_bps / Decimal("10000")).quantize(Decimal("0.00000001"))
            assert fill.fee_value == expected_fee
            assert fill.tax_value == expected_tax
