from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.financial_facts import FinancialFact, RestatementLog

VALUE_STATUSES = frozenset({"reported", "calculated", "missing", "not_applicable", "parse_error", "suppressed"})


def validate_fact_value(value: Decimal | None, status: str) -> None:
    if status not in VALUE_STATUSES:
        raise ValueError(f"unsupported value status: {status}")
    carries_value = status in {"reported", "calculated"}
    if carries_value != (value is not None):
        raise ValueError(f"status {status} and value presence are inconsistent")


def require_aware(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must include timezone information")


@dataclass(frozen=True, slots=True)
class FinancialFactInput:
    issuer_id: UUID
    reporting_period_id: UUID
    statement_type: str
    consolidation_scope: str
    original_account_code: str
    original_account_label: str
    taxonomy_account_id: UUID | None
    value: Decimal | None
    currency_code: str
    scale_factor: int
    value_status: str
    source_object_version_id: UUID
    parser_version: str
    mapping_rule_id: UUID | None
    published_at: datetime
    discovered_at: datetime
    ingested_at: datetime
    validated_at: datetime
    knowledge_at: datetime


@dataclass(frozen=True, slots=True)
class FactRevisionResult:
    fact: FinancialFact
    created: bool
    superseded_fact_id: UUID | None


class FinancialFactRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def revise(self, item: FinancialFactInput) -> FactRevisionResult:
        validate_fact_value(item.value, item.value_status)
        for field_name in ("published_at", "discovered_at", "ingested_at", "validated_at", "knowledge_at"):
            require_aware(getattr(item, field_name), field_name)
        if item.scale_factor <= 0:
            raise ValueError("scale_factor must be positive")

        identity = (
            FinancialFact.reporting_period_id == item.reporting_period_id,
            FinancialFact.statement_type == item.statement_type,
            FinancialFact.consolidation_scope == item.consolidation_scope,
            FinancialFact.original_account_code == item.original_account_code,
        )
        current = (
            await self.session.execute(
                sa.select(FinancialFact)
                .where(*identity, FinancialFact.valid_to.is_(None))
                .order_by(FinancialFact.revision_number.desc())
                .with_for_update()
            )
        ).scalar_one_or_none()
        if current is not None and (
            current.value == item.value
            and current.value_status == item.value_status
            and current.source_object_version_id == item.source_object_version_id
            and current.parser_version == item.parser_version
            and current.mapping_rule_id == item.mapping_rule_id
        ):
            return FactRevisionResult(current, False, None)
        if current is not None and item.knowledge_at <= current.valid_from:
            raise ValueError("new revision knowledge_at must be after the current revision")

        superseded_id = current.id if current else None
        restatement = None
        if current is not None:
            current.valid_to = item.knowledge_at
            if current.value != item.value or current.value_status != item.value_status:
                restatement = RestatementLog(
                    superseded_fact_id=current.id,
                    new_fact_id=None,
                    account_code=current.original_account_code,
                    old_value=current.value,
                    new_value=item.value,
                    old_value_status=current.value_status,
                    new_value_status=item.value_status,
                    revision_number=current.revision_number + 1,
                    created_at=item.knowledge_at,
                )
                self.session.add(restatement)
        fact = FinancialFact(
            issuer_id=item.issuer_id,
            reporting_period_id=item.reporting_period_id,
            statement_type=item.statement_type,
            consolidation_scope=item.consolidation_scope,
            original_account_code=item.original_account_code,
            original_account_label=item.original_account_label,
            taxonomy_account_id=item.taxonomy_account_id,
            value=item.value,
            currency_code=item.currency_code,
            scale_factor=item.scale_factor,
            value_status=item.value_status,
            source_object_version_id=item.source_object_version_id,
            parser_version=item.parser_version,
            mapping_rule_id=item.mapping_rule_id,
            published_at=item.published_at,
            discovered_at=item.discovered_at,
            ingested_at=item.ingested_at,
            validated_at=item.validated_at,
            knowledge_at=item.knowledge_at,
            valid_from=item.knowledge_at,
            valid_to=None,
            revision_number=(current.revision_number + 1) if current else 1,
        )
        self.session.add(fact)
        await self.session.flush()
        if restatement is not None:
            restatement.new_fact_id = fact.id
        return FactRevisionResult(fact, True, superseded_id)

    async def list_as_of(
        self,
        issuer_id: UUID,
        reporting_period_id: UUID,
        as_of: datetime,
    ) -> list[FinancialFact]:
        require_aware(as_of, "as_of")
        result = await self.session.execute(
            sa.select(FinancialFact)
            .where(
                FinancialFact.issuer_id == issuer_id,
                FinancialFact.reporting_period_id == reporting_period_id,
                FinancialFact.knowledge_at <= as_of,
                FinancialFact.valid_from <= as_of,
                sa.or_(FinancialFact.valid_to.is_(None), FinancialFact.valid_to > as_of),
            )
            .order_by(FinancialFact.statement_type, FinancialFact.original_account_code)
        )
        return list(result.scalars().all())
