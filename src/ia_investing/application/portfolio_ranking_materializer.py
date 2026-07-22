"""Persist deterministic portfolio-ranking inputs with reproducible provenance."""
from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

_COMPONENT_NAMES = (
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


class RankingComponents(BaseModel):
    model_config = ConfigDict(extra="forbid")

    excess_return: Decimal
    sortino: Decimal
    drawdown_control: Decimal
    regime_stability: Decimal
    walk_forward_robustness: Decimal
    risk_compliance: Decimal
    thesis_health: Decimal
    cost_capacity: Decimal
    data_model_confidence: Decimal

    @field_validator("*")
    @classmethod
    def bounded(cls, value: Decimal) -> Decimal:
        if value < 0 or value > 1:
            raise ValueError("ranking components must be between 0 and 1")
        return value


class RankingEvidenceBundle(BaseModel):
    """Validated outputs from deterministic analytics, never direct LLM scores."""

    model_config = ConfigDict(extra="forbid")

    portfolio_id: UUID
    portfolio_version_id: UUID
    as_of: datetime
    category: str = Field(min_length=1, max_length=50)
    benchmark: str = Field(min_length=1, max_length=50)
    risk_class: str = Field(min_length=1, max_length=30)
    inception_at: datetime
    nav_reconciled: bool
    backtest_point_in_time_verified: bool
    approved_version: bool
    open_hard_breaches: int = Field(ge=0)
    open_soft_breaches: int = Field(ge=0)
    expired_theses: int = Field(ge=0)
    thesis_coverage: Decimal = Field(ge=0, le=1)
    data_confidence: Decimal = Field(ge=0, le=1)
    low_liquidity: bool
    high_turnover: bool
    components: RankingComponents
    methodology_version: str = Field(min_length=1, max_length=100)
    evidence_ids: list[UUID] = Field(default_factory=list)
    analytics_snapshot_ids: list[UUID] = Field(default_factory=list)

    @field_validator("as_of", "inception_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("ranking timestamps must be timezone-aware")
        return value


def canonical_payload(bundle: RankingEvidenceBundle) -> dict[str, Any]:
    return bundle.model_dump(mode="json", exclude_none=False)


def payload_sha256(bundle: RankingEvidenceBundle) -> str:
    encoded = json.dumps(
        canonical_payload(bundle),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


UPSERT_SQL = text(
    """
    INSERT INTO portfolio_ranking_snapshots (
        id,
        portfolio_id,
        portfolio_version_id,
        as_of,
        category,
        benchmark,
        risk_class,
        inception_at,
        nav_reconciled,
        backtest_point_in_time_verified,
        approved_version,
        open_hard_breaches,
        open_soft_breaches,
        expired_theses,
        thesis_coverage,
        data_confidence,
        low_liquidity,
        high_turnover,
        excess_return,
        sortino,
        drawdown_control,
        regime_stability,
        walk_forward_robustness,
        risk_compliance,
        thesis_health,
        cost_capacity,
        data_model_confidence,
        methodology_version,
        input_sha256,
        input_payload,
        computed_at
    ) VALUES (
        :id,
        :portfolio_id,
        :portfolio_version_id,
        :as_of,
        :category,
        :benchmark,
        :risk_class,
        :inception_at,
        :nav_reconciled,
        :backtest_point_in_time_verified,
        :approved_version,
        :open_hard_breaches,
        :open_soft_breaches,
        :expired_theses,
        :thesis_coverage,
        :data_confidence,
        :low_liquidity,
        :high_turnover,
        :excess_return,
        :sortino,
        :drawdown_control,
        :regime_stability,
        :walk_forward_robustness,
        :risk_compliance,
        :thesis_health,
        :cost_capacity,
        :data_model_confidence,
        :methodology_version,
        :input_sha256,
        CAST(:input_payload AS JSONB),
        :computed_at
    )
    ON CONFLICT (portfolio_id, as_of, methodology_version)
    DO UPDATE SET
        portfolio_version_id = EXCLUDED.portfolio_version_id,
        category = EXCLUDED.category,
        benchmark = EXCLUDED.benchmark,
        risk_class = EXCLUDED.risk_class,
        inception_at = EXCLUDED.inception_at,
        nav_reconciled = EXCLUDED.nav_reconciled,
        backtest_point_in_time_verified = EXCLUDED.backtest_point_in_time_verified,
        approved_version = EXCLUDED.approved_version,
        open_hard_breaches = EXCLUDED.open_hard_breaches,
        open_soft_breaches = EXCLUDED.open_soft_breaches,
        expired_theses = EXCLUDED.expired_theses,
        thesis_coverage = EXCLUDED.thesis_coverage,
        data_confidence = EXCLUDED.data_confidence,
        low_liquidity = EXCLUDED.low_liquidity,
        high_turnover = EXCLUDED.high_turnover,
        excess_return = EXCLUDED.excess_return,
        sortino = EXCLUDED.sortino,
        drawdown_control = EXCLUDED.drawdown_control,
        regime_stability = EXCLUDED.regime_stability,
        walk_forward_robustness = EXCLUDED.walk_forward_robustness,
        risk_compliance = EXCLUDED.risk_compliance,
        thesis_health = EXCLUDED.thesis_health,
        cost_capacity = EXCLUDED.cost_capacity,
        data_model_confidence = EXCLUDED.data_model_confidence,
        input_sha256 = EXCLUDED.input_sha256,
        input_payload = EXCLUDED.input_payload,
        computed_at = EXCLUDED.computed_at
    WHERE portfolio_ranking_snapshots.input_sha256 IS DISTINCT FROM EXCLUDED.input_sha256
    RETURNING id
    """
)


class PortfolioRankingMaterializer:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def persist(self, bundle: RankingEvidenceBundle) -> UUID:
        payload = canonical_payload(bundle)
        values: dict[str, Any] = {
            "id": uuid4(),
            "portfolio_id": bundle.portfolio_id,
            "portfolio_version_id": bundle.portfolio_version_id,
            "as_of": bundle.as_of,
            "category": bundle.category,
            "benchmark": bundle.benchmark,
            "risk_class": bundle.risk_class,
            "inception_at": bundle.inception_at,
            "nav_reconciled": bundle.nav_reconciled,
            "backtest_point_in_time_verified": bundle.backtest_point_in_time_verified,
            "approved_version": bundle.approved_version,
            "open_hard_breaches": bundle.open_hard_breaches,
            "open_soft_breaches": bundle.open_soft_breaches,
            "expired_theses": bundle.expired_theses,
            "thesis_coverage": bundle.thesis_coverage,
            "data_confidence": bundle.data_confidence,
            "low_liquidity": bundle.low_liquidity,
            "high_turnover": bundle.high_turnover,
            "methodology_version": bundle.methodology_version,
            "input_sha256": payload_sha256(bundle),
            "input_payload": json.dumps(payload, sort_keys=True, separators=(",", ":")),
            "computed_at": datetime.now(UTC),
        }
        values.update(bundle.components.model_dump())
        snapshot_id = await self._session.scalar(UPSERT_SQL, values)
        if snapshot_id is None:
            existing = await self._session.scalar(
                text(
                    """
                    SELECT id
                    FROM portfolio_ranking_snapshots
                    WHERE portfolio_id = :portfolio_id
                      AND as_of = :as_of
                      AND methodology_version = :methodology_version
                    """
                ),
                {
                    "portfolio_id": bundle.portfolio_id,
                    "as_of": bundle.as_of,
                    "methodology_version": bundle.methodology_version,
                },
            )
            if existing is None:
                raise RuntimeError("ranking snapshot upsert returned no row")
            return UUID(str(existing))
        return UUID(str(snapshot_id))
