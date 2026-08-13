from datetime import UTC, date, datetime
from decimal import Decimal

from database.models.market_data import FxRate, MarketQuote, YieldCurvePoint
from ia_investing.application.market_data import SplitEvent, split_adjustment_factor


def test_split_adjustment_uses_only_information_known_as_of() -> None:
    events = [
        SplitEvent("split", date(2025, 6, 1), Decimal("2"), datetime(2025, 5, 1, tzinfo=UTC)),
        SplitEvent("split", date(2025, 9, 1), Decimal("10"), datetime(2025, 8, 1, tzinfo=UTC)),
    ]

    factor = split_adjustment_factor(events, date(2025, 1, 1), datetime(2025, 7, 1, tzinfo=UTC))

    assert factor == Decimal("0.5")


def test_action_announced_after_as_of_never_adjusts_history() -> None:
    event = SplitEvent("reverse_split", date(2025, 6, 1), Decimal("10"), datetime(2025, 7, 1, tzinfo=UTC))
    assert split_adjustment_factor([event], date(2025, 1, 1), datetime(2025, 6, 15, tzinfo=UTC)) == 1


def test_quote_fx_and_curve_models_enforce_point_in_time_identity() -> None:
    quote_constraints = {item.name for item in MarketQuote.__table__.constraints}
    fx_constraints = {item.name for item in FxRate.__table__.constraints}
    curve_constraints = {item.name for item in YieldCurvePoint.__table__.constraints}

    assert {"uq_market_quotes_pit", "ck_market_quotes_valid_spread"} <= quote_constraints
    assert {"uq_fx_rates_pit", "ck_fx_rates_positive_rate"} <= fx_constraints
    assert {"uq_yield_curve_points_pit", "ck_yield_curve_points_positive_tenor"} <= curve_constraints
