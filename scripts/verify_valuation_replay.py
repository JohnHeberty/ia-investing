from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import sqlalchemy as sa

from database.core import session_scope
from database.models.catalog import Issuer
from database.models.financial_facts import MetricObservation
from ia_investing.application.theses import ThesisService, ThesisSnapshot
from ia_investing.application.valuations import (
    AssumptionInput,
    RelativeInput,
    ReverseDCFInput,
    ScenarioInput,
    ValuationCommand,
    ValuationService,
)
from ia_investing.domain.valuation import DCFInput


async def verify() -> None:
    async with session_scope() as session:
        issuer_id = await session.scalar(sa.select(Issuer.id).order_by(Issuer.id).limit(1))
        metric = (
            await session.execute(sa.select(MetricObservation).order_by(MetricObservation.id).limit(1))
        ).scalar_one_or_none()
        if issuer_id is None or metric is None:
            raise RuntimeError("verification requires one issuer and one metric observation")
        cutoff = max(metric.data_as_of, datetime.now(UTC))
        _, thesis_version = await ThesisService(session).create_draft(
            issuer_id,
            None,
            ThesisSnapshot(
                summary="Valuation replay verification",
                assumptions=[{"metric_id": str(metric.id)}],
                catalysts=[],
                risks=[],
                invalidation_criteria=[],
                recommendation="hold",
                recommendation_confidence=Decimal("0.50"),
                data_as_of=cutoff,
                expires_at=cutoff + timedelta(days=30),
            ),
            "valuation-verifier",
            frozenset({"research_theses:create"}),
            [],
            [],
        )
        command = ValuationCommand(
            thesis_version_id=thesis_version.id,
            code_version="valuation-v1-test",
            data_as_of=cutoff,
            assumptions=(
                AssumptionInput(
                    name="current_ratio",
                    value=metric.value,
                    unit="ratio",
                    horizon="latest",
                    source_type="metric_observation",
                    source_id=metric.id,
                    source_version=metric.calculation_version,
                    approved_by="valuation-reviewer",
                    sensitivity_low=Decimal("2.0"),
                    sensitivity_high=Decimal("3.0"),
                ),
            ),
            scenarios=tuple(
                ScenarioInput(
                    name=name,
                    probability=probability,
                    inputs=DCFInput(
                        free_cash_flows=(cash_flow, cash_flow * Decimal("1.05")),
                        discount_rate=Decimal("0.10"),
                        terminal_growth=Decimal("0.03"),
                        net_debt=Decimal("200"),
                        shares_outstanding=Decimal("100"),
                    ),
                )
                for name, probability, cash_flow in (
                    ("bear", Decimal("0.20"), Decimal("80")),
                    ("base", Decimal("0.50"), Decimal("100")),
                    ("bull", Decimal("0.30"), Decimal("120")),
                )
            ),
            relative=RelativeInput(Decimal("100"), Decimal("8"), Decimal("200"), Decimal("100")),
            reverse_dcf=ReverseDCFInput(Decimal("2000"), Decimal("100"), Decimal("0.10"), 5),
        )
        service = ValuationService(session)
        first = await service.execute(command, "valuation-verifier", frozenset({"valuations:create"}))
        second = await service.execute(command, "valuation-verifier", frozenset({"valuations:create"}))
        if first.run.id != second.run.id or not second.replayed:
            raise AssertionError("valuation replay did not return the persisted run")
        if len(first.results) != 6 or first.run.result_sha256 != second.run.result_sha256:
            raise AssertionError("valuation result set or hash is not reproducible")
        print(
            "valuation-replay-ok",
            f"run_id={first.run.id}",
            f"input_sha256={first.run.input_sha256}",
            f"result_sha256={first.run.result_sha256}",
            f"results={len(first.results)}",
        )


if __name__ == "__main__":
    asyncio.run(verify())
