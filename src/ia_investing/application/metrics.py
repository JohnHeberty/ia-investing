from __future__ import annotations

from datetime import datetime
from decimal import Decimal, DivisionByZero
from typing import Literal
from uuid import UUID

import sqlalchemy as sa
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.financial_facts import (
    FinancialFact,
    MetricDefinition,
    MetricFactLineage,
    MetricObservation,
    TaxonomyAccount,
)
from ia_investing.application.financial_facts import require_aware


class MetricBundleV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    observation_id: UUID
    issuer_id: UUID
    reporting_period_id: UUID
    metric_name: str
    definition_version: int
    formula: str
    unit: str
    value: Decimal | None
    value_status: str
    data_as_of: datetime
    quality_score: Decimal
    coverage_ratio: Decimal
    calculation_version: str
    lineage_ids: list[UUID]


def calculate_known_metric(name: str, values: dict[str, Decimal]) -> Decimal:
    formulas = {
        "current_ratio": lambda inputs: inputs["current_assets"] / inputs["current_liabilities"],
        "net_margin": lambda inputs: inputs["net_income"] / inputs["revenue"],
        "debt_to_equity": lambda inputs: inputs["total_debt"] / inputs["equity"],
    }
    if name not in formulas:
        raise ValueError(f"metric calculator is not registered: {name}")
    try:
        return formulas[name](values)
    except (DivisionByZero, ZeroDivisionError) as exc:
        raise ValueError(f"metric denominator is zero: {name}") from exc


class MetricService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def calculate(
        self,
        metric_name: str,
        issuer_id: UUID,
        reporting_period_id: UUID,
        as_of: datetime,
    ) -> MetricBundleV1:
        require_aware(as_of, "as_of")
        definition = (
            await self.session.execute(
                sa.select(MetricDefinition)
                .where(MetricDefinition.name == metric_name)
                .order_by(MetricDefinition.version.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if definition is None:
            raise LookupError("metric definition not found")
        rows = (
            await self.session.execute(
                sa.select(FinancialFact, TaxonomyAccount.canonical_code)
                .join(TaxonomyAccount, TaxonomyAccount.id == FinancialFact.taxonomy_account_id)
                .where(
                    FinancialFact.issuer_id == issuer_id,
                    FinancialFact.reporting_period_id == reporting_period_id,
                    TaxonomyAccount.canonical_code.in_(definition.dependencies),
                    FinancialFact.knowledge_at <= as_of,
                    FinancialFact.valid_from <= as_of,
                    sa.or_(FinancialFact.valid_to.is_(None), FinancialFact.valid_to > as_of),
                )
            )
        ).all()
        facts = {code: fact for fact, code in rows}
        usable = {
            code: fact.value
            for code, fact in facts.items()
            if fact.value_status in {"reported", "calculated"} and fact.value is not None
        }
        coverage = Decimal(len(usable)) / Decimal(len(definition.dependencies))
        if len(usable) != len(definition.dependencies):
            value = None
            status = "missing"
        else:
            value = calculate_known_metric(metric_name, usable)
            status = "calculated"
        calculation_version = f"{metric_name}:v{definition.version}"
        existing = (
            await self.session.execute(
                sa.select(MetricObservation).where(
                    MetricObservation.issuer_id == issuer_id,
                    MetricObservation.reporting_period_id == reporting_period_id,
                    MetricObservation.metric_definition_id == definition.id,
                    MetricObservation.data_as_of == as_of,
                )
            )
        ).scalar_one_or_none()
        if existing is None:
            existing = MetricObservation(
                issuer_id=issuer_id,
                reporting_period_id=reporting_period_id,
                metric_definition_id=definition.id,
                value=value,
                value_status=status,
                quality_score=coverage,
                coverage_ratio=coverage,
                data_as_of=as_of,
                calculation_version=calculation_version,
            )
            self.session.add(existing)
            await self.session.flush()
            for code in definition.dependencies:
                if code in facts:
                    self.session.add(
                        MetricFactLineage(
                            metric_observation_id=existing.id,
                            financial_fact_id=facts[code].id,
                            input_role=code,
                        )
                    )
            await self.session.flush()
        lineage_ids = list(
            (
                await self.session.execute(
                    sa.select(MetricFactLineage.financial_fact_id).where(
                        MetricFactLineage.metric_observation_id == existing.id
                    )
                )
            ).scalars()
        )
        return MetricBundleV1(
            observation_id=existing.id,
            issuer_id=issuer_id,
            reporting_period_id=reporting_period_id,
            metric_name=definition.name,
            definition_version=definition.version,
            formula=definition.formula,
            unit=definition.unit,
            value=existing.value,
            value_status=existing.value_status,
            data_as_of=existing.data_as_of,
            quality_score=existing.quality_score,
            coverage_ratio=existing.coverage_ratio,
            calculation_version=existing.calculation_version,
            lineage_ids=lineage_ids,
        )
