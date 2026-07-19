from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.data_governance import QuarantineRecord
from database.models.financial_facts import FinancialFact, MetricObservation
from database.models.research import ResearchEvidence
from database.models.thesis_domain import ResearchThesisVersion
from database.models.valuation import ValuationAssumption, ValuationResult, ValuationRun
from ia_investing.domain.valuation import (
    DCFInput,
    DCFResult,
    discounted_cash_flow,
    relative_valuation,
    reverse_dcf_growth,
    weighted_scenarios,
)


def _json_value(value: object) -> object:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (datetime, UUID)):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json_value(item) for item in value]
    return value


def canonical_payload(payload: object) -> tuple[dict[str, object], str]:
    normalized = _json_value(payload)
    if not isinstance(normalized, dict):
        raise TypeError("valuation payload must be an object")
    encoded = json.dumps(normalized, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return normalized, hashlib.sha256(encoded.encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class AssumptionInput:
    name: str
    value: Decimal
    unit: str
    horizon: str
    source_type: str
    source_id: UUID
    source_version: str
    approved_by: str
    sensitivity_low: Decimal | None = None
    sensitivity_high: Decimal | None = None


@dataclass(frozen=True, slots=True)
class ScenarioInput:
    name: str
    probability: Decimal
    inputs: DCFInput


@dataclass(frozen=True, slots=True)
class RelativeInput:
    metric: Decimal
    selected_multiple: Decimal
    net_debt: Decimal
    shares_outstanding: Decimal


@dataclass(frozen=True, slots=True)
class ReverseDCFInput:
    market_enterprise_value: Decimal
    starting_cash_flow: Decimal
    discount_rate: Decimal
    years: int = 5


@dataclass(frozen=True, slots=True)
class ValuationCommand:
    thesis_version_id: UUID
    code_version: str
    data_as_of: datetime
    assumptions: tuple[AssumptionInput, ...]
    scenarios: tuple[ScenarioInput, ...]
    relative: RelativeInput
    reverse_dcf: ReverseDCFInput


@dataclass(frozen=True, slots=True)
class ValuationExecution:
    run: ValuationRun
    results: tuple[ValuationResult, ...]
    replayed: bool


class ValuationService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def execute(
        self,
        command: ValuationCommand,
        actor_subject: str,
        permissions: frozenset[str],
    ) -> ValuationExecution:
        if "valuations:create" not in permissions:
            raise PermissionError("permission required: valuations:create")
        if command.data_as_of.tzinfo is None:
            raise ValueError("data_as_of must include timezone information")
        thesis_version = await self.session.get(ResearchThesisVersion, command.thesis_version_id)
        if thesis_version is None:
            raise LookupError("thesis version not found")
        if thesis_version.data_as_of > command.data_as_of:
            raise ValueError("thesis version is from the future relative to valuation cutoff")
        if not command.assumptions:
            raise ValueError("at least one sourced valuation assumption is required")
        names = [item.name for item in command.assumptions]
        if len(names) != len(set(names)):
            raise ValueError("valuation assumption names must be unique")
        for assumption in command.assumptions:
            await self._validate_assumption_source(assumption, command.data_as_of)

        scenario_map = {item.name: discounted_cash_flow(item.inputs) for item in command.scenarios}
        probability_map = {item.name: item.probability for item in command.scenarios}
        weighted = weighted_scenarios(scenario_map, probability_map)
        relative = relative_valuation(**asdict(command.relative))
        implied_growth = reverse_dcf_growth(**asdict(command.reverse_dcf))
        input_payload, input_sha256 = canonical_payload(asdict(command))
        result_payload, result_sha256 = canonical_payload(
            {
                **{name: asdict(result) for name, result in scenario_map.items()},
                "weighted": asdict(weighted),
                "relative": asdict(relative),
                "reverse_dcf": {"implied_growth": implied_growth},
            }
        )
        existing = (
            await self.session.execute(
                sa.select(ValuationRun).where(
                    ValuationRun.thesis_version_id == command.thesis_version_id,
                    ValuationRun.model_type == "institutional_dcf_v1",
                    ValuationRun.input_sha256 == input_sha256,
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            rows = tuple(
                (
                    await self.session.scalars(
                        sa.select(ValuationResult)
                        .where(ValuationResult.valuation_run_id == existing.id)
                        .order_by(ValuationResult.scenario)
                    )
                ).all()
            )
            return ValuationExecution(existing, rows, True)

        run = ValuationRun(
            thesis_version_id=command.thesis_version_id,
            model_type="institutional_dcf_v1",
            code_version=command.code_version,
            input_sha256=input_sha256,
            input_payload=input_payload,
            result_sha256=result_sha256,
            data_as_of=command.data_as_of,
            status="completed",
            created_by=actor_subject,
        )
        self.session.add(run)
        await self.session.flush()
        for assumption in command.assumptions:
            source_fields = {
                "evidence_id": assumption.source_id if assumption.source_type == "evidence" else None,
                "financial_fact_id": assumption.source_id if assumption.source_type == "financial_fact" else None,
                "metric_observation_id": assumption.source_id
                if assumption.source_type == "metric_observation"
                else None,
            }
            self.session.add(
                ValuationAssumption(
                    valuation_run_id=run.id,
                    name=assumption.name,
                    value=assumption.value,
                    unit=assumption.unit,
                    horizon=assumption.horizon,
                    source_version=assumption.source_version,
                    approved_by=assumption.approved_by,
                    sensitivity_low=assumption.sensitivity_low,
                    sensitivity_high=assumption.sensitivity_high,
                    **source_fields,
                )
            )
        results = (
            *(
                self._result_row(run.id, name, result, probability_map[name], result_payload[name])
                for name, result in scenario_map.items()
            ),
            self._result_row(run.id, "weighted", weighted, None, result_payload["weighted"]),
            self._result_row(run.id, "relative", relative, None, result_payload["relative"]),
            ValuationResult(
                valuation_run_id=run.id,
                scenario="reverse_dcf",
                equity_value=Decimal(0),
                value_per_share=Decimal(0),
                probability=None,
                result_payload=result_payload["reverse_dcf"],
            ),
        )
        self.session.add_all(results)
        await self.session.flush()
        return ValuationExecution(run, results, False)

    async def get(self, run_id: UUID, permissions: frozenset[str]) -> ValuationExecution:
        if "valuations:read" not in permissions and "research:read" not in permissions:
            raise PermissionError("permission required: valuations:read")
        run = await self.session.get(ValuationRun, run_id)
        if run is None:
            raise LookupError("valuation run not found")
        rows = tuple(
            (
                await self.session.scalars(
                    sa.select(ValuationResult)
                    .where(ValuationResult.valuation_run_id == run.id)
                    .order_by(ValuationResult.scenario)
                )
            ).all()
        )
        return ValuationExecution(run, rows, True)

    async def _validate_assumption_source(self, assumption: AssumptionInput, cutoff: datetime) -> None:
        if (
            assumption.sensitivity_low is not None
            and assumption.sensitivity_high is not None
            and assumption.sensitivity_low > assumption.sensitivity_high
        ):
            raise ValueError(f"invalid sensitivity range for assumption {assumption.name}")
        if assumption.source_type == "evidence":
            evidence = await self.session.get(ResearchEvidence, assumption.source_id)
            if evidence is None:
                raise LookupError(f"evidence source not found for assumption {assumption.name}")
            if (
                evidence.knowledge_at > cutoff
                or evidence.revoked_at is not None
                or (evidence.valid_until is not None and evidence.valid_until <= cutoff)
            ):
                raise ValueError(f"evidence source is not valid at cutoff for assumption {assumption.name}")
            return
        if assumption.source_type == "financial_fact":
            fact = await self.session.get(FinancialFact, assumption.source_id)
            if fact is None:
                raise LookupError(f"financial fact source not found for assumption {assumption.name}")
            if (
                fact.knowledge_at > cutoff
                or fact.valid_from > cutoff
                or (fact.valid_to is not None and fact.valid_to <= cutoff)
                or fact.value_status not in {"reported", "calculated"}
            ):
                raise ValueError(f"financial fact source is not valid at cutoff for assumption {assumption.name}")
            quarantined = await self.session.scalar(
                sa.select(sa.func.count(QuarantineRecord.id)).where(
                    QuarantineRecord.source_object_version_id == fact.source_object_version_id,
                    QuarantineRecord.status == "blocked",
                )
            )
            if quarantined:
                raise ValueError(f"financial fact source is quarantined for assumption {assumption.name}")
            return
        if assumption.source_type == "metric_observation":
            metric = await self.session.get(MetricObservation, assumption.source_id)
            if metric is None:
                raise LookupError(f"metric observation source not found for assumption {assumption.name}")
            if (
                metric.data_as_of > cutoff
                or metric.value is None
                or metric.value_status not in {"reported", "calculated"}
            ):
                raise ValueError(f"metric source is not valid at cutoff for assumption {assumption.name}")
            return
        raise ValueError(f"unsupported assumption source type: {assumption.source_type}")

    @staticmethod
    def _result_row(
        run_id: UUID,
        scenario: str,
        result: DCFResult,
        probability: Decimal | None,
        payload: object,
    ) -> ValuationResult:
        if not isinstance(payload, dict):
            raise TypeError("valuation result payload must be an object")
        return ValuationResult(
            valuation_run_id=run_id,
            scenario=scenario,
            equity_value=result.equity_value,
            value_per_share=result.value_per_share,
            probability=probability,
            result_payload=payload,
        )
