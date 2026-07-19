from __future__ import annotations

from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.evidence import DocumentChunk
from database.models.financial_facts import MetricDefinition, MetricObservation
from database.models.research import ResearchEvidence
from ia_investing.domain.valuation import DCFInput, discounted_cash_flow

from .tools import (
    EvidenceSearchInput,
    EvidenceSearchOutput,
    FinancialMetricsInput,
    FinancialMetricsOutput,
    ToolRegistry,
    TypedTool,
    ValuationInput,
    ValuationOutput,
)


def build_read_only_tool_registry(session: AsyncSession) -> ToolRegistry:
    registry = ToolRegistry()

    async def get_financial_metrics(request: FinancialMetricsInput) -> FinancialMetricsOutput:
        conditions = [
            MetricObservation.issuer_id == request.issuer_id,
            MetricDefinition.name.in_(request.metric_names),
            MetricObservation.data_as_of <= request.as_of,
        ]
        if request.reporting_period_id is not None:
            conditions.append(MetricObservation.reporting_period_id == request.reporting_period_id)
        ranked = (
            sa.select(
                MetricObservation,
                MetricDefinition.name.label("metric_name"),
                sa.func.row_number()
                .over(
                    partition_by=(MetricObservation.reporting_period_id, MetricDefinition.name),
                    order_by=MetricObservation.data_as_of.desc(),
                )
                .label("rank"),
            )
            .join(MetricDefinition, MetricDefinition.id == MetricObservation.metric_definition_id)
            .where(*conditions)
            .subquery()
        )
        rows = (await session.execute(sa.select(ranked).where(ranked.c.rank == 1))).mappings()
        return FinancialMetricsOutput(
            observations=[
                {
                    "observation_id": str(row["id"]),
                    "metric_name": row["metric_name"],
                    "reporting_period_id": str(row["reporting_period_id"]),
                    "value": str(row["value"]) if row["value"] is not None else None,
                    "value_status": row["value_status"],
                    "data_as_of": row["data_as_of"].isoformat(),
                    "quality_score": str(row["quality_score"]),
                }
                for row in rows
            ]
        )

    async def search_evidence(request: EvidenceSearchInput) -> EvidenceSearchOutput:
        query = request.query.strip()
        if not query:
            raise ValueError("evidence query cannot be empty")
        rows = (
            await session.execute(
                sa.select(ResearchEvidence, DocumentChunk)
                .join(DocumentChunk, DocumentChunk.id == ResearchEvidence.document_chunk_id)
                .where(
                    ResearchEvidence.research_case_id == request.case_id,
                    ResearchEvidence.knowledge_at <= request.knowledge_cutoff,
                    ResearchEvidence.revoked_at.is_(None),
                    sa.or_(
                        ResearchEvidence.valid_until.is_(None),
                        ResearchEvidence.valid_until > request.knowledge_cutoff,
                    ),
                    DocumentChunk.text.ilike(f"%{query}%"),
                )
                .order_by(ResearchEvidence.quality_score.desc(), DocumentChunk.ordinal)
                .limit(request.limit)
            )
        ).all()
        return EvidenceSearchOutput(
            evidence=[
                {
                    "evidence_id": str(evidence.id),
                    "chunk_id": str(chunk.id),
                    "quote": evidence.excerpt,
                    "page_start": evidence.page_start,
                    "page_end": evidence.page_end,
                    "content_sha256": evidence.excerpt_sha256,
                    "knowledge_at": evidence.knowledge_at.isoformat(),
                }
                for evidence, chunk in rows
            ]
        )

    async def calculate_valuation(request: ValuationInput) -> ValuationOutput:
        assumptions = request.assumptions
        required = {"free_cash_flows", "discount_rate", "terminal_growth", "net_debt", "shares_outstanding"}
        missing = required - assumptions.keys()
        if missing:
            raise ValueError(f"valuation assumptions are missing: {sorted(missing)}")
        cash_flows = assumptions["free_cash_flows"]
        if not isinstance(cash_flows, list):
            raise ValueError("free_cash_flows must be a list")
        result = discounted_cash_flow(
            DCFInput(
                free_cash_flows=tuple(Decimal(str(value)) for value in cash_flows),
                discount_rate=Decimal(str(assumptions["discount_rate"])),
                terminal_growth=Decimal(str(assumptions["terminal_growth"])),
                net_debt=Decimal(str(assumptions["net_debt"])),
                shares_outstanding=Decimal(str(assumptions["shares_outstanding"])),
            )
        )
        return ValuationOutput(
            results=[
                {
                    "model_type": "dcf",
                    "enterprise_value": str(result.enterprise_value),
                    "equity_value": str(result.equity_value),
                    "value_per_share": str(result.value_per_share),
                }
            ]
        )

    registry.register(
        TypedTool("get_financial_metrics", 1, FinancialMetricsInput, FinancialMetricsOutput, get_financial_metrics)
    )
    registry.register(TypedTool("search_evidence", 1, EvidenceSearchInput, EvidenceSearchOutput, search_evidence))
    registry.register(TypedTool("calculate_valuation", 1, ValuationInput, ValuationOutput, calculate_valuation))
    return registry
