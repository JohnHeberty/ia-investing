from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import pytest
from pydantic import ValidationError

from ia_investing.application.portfolio_ranking_materializer import (
    RankingComponents,
    RankingEvidenceBundle,
    payload_sha256,
)


def bundle() -> RankingEvidenceBundle:
    return RankingEvidenceBundle(
        portfolio_id=UUID("00000000-0000-0000-0000-000000000001"),
        portfolio_version_id=UUID("00000000-0000-0000-0000-000000000002"),
        as_of=datetime(2026, 7, 21, tzinfo=UTC),
        category="quality",
        benchmark="IBOV",
        risk_class="moderate",
        inception_at=datetime(2025, 1, 1, tzinfo=UTC),
        nav_reconciled=True,
        backtest_point_in_time_verified=True,
        approved_version=True,
        open_hard_breaches=0,
        open_soft_breaches=0,
        expired_theses=0,
        thesis_coverage=Decimal("0.95"),
        data_confidence=Decimal("0.98"),
        low_liquidity=False,
        high_turnover=False,
        components=RankingComponents(**{
            name: Decimal("0.8")
            for name in (
                "excess_return",
                "sortino",
                "drawdown_control",
                "regime_stability",
                "walk_forward_robustness",
                "risk_compliance",
                "thesis_health",
                "cost_capacity",
                "data_model_confidence",
            )
        }),
        methodology_version="institutional-v1",
    )


def test_hash_is_deterministic() -> None:
    first = bundle()
    second = bundle()
    assert payload_sha256(first) == payload_sha256(second)
    assert len(payload_sha256(first)) == 64


def test_component_rejects_out_of_range_value() -> None:
    values = {name: Decimal("0.8") for name in RankingComponents.model_fields}
    values["sortino"] = Decimal("1.01")
    with pytest.raises(ValidationError):
        RankingComponents(**values)


def test_timestamp_must_be_timezone_aware() -> None:
    data = bundle().model_dump()
    data["as_of"] = datetime(2026, 7, 21)
    with pytest.raises(ValidationError):
        RankingEvidenceBundle(**data)
