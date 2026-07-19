"""Verify material quality gate, quarantine, transitions, and audit persistence."""

from __future__ import annotations

import asyncio
from uuid import uuid4

import sqlalchemy as sa

from data_quality._models import ValidationResult
from database.core import session_scope
from database.models.agents import AuditLog
from database.models.data_foundation import SourceObjectVersion
from database.models.data_governance import QualityIncident, QualityRule, QuarantineRecord
from ia_investing.application.data_quality import QualityGovernanceService


async def main() -> None:
    correlation_id = uuid4()
    async with session_scope() as session:
        rule_id = await session.scalar(sa.select(QualityRule.id).where(QualityRule.code == "balance_sheet_balances"))
        source_version_id = await session.scalar(
            sa.select(SourceObjectVersion.id)
            .outerjoin(QualityIncident, QualityIncident.source_object_version_id == SourceObjectVersion.id)
            .where(QualityIncident.id.is_(None))
            .limit(1)
        )
        if rule_id is None or source_version_id is None:
            raise RuntimeError("a quality rule and an untested raw source version are required")
        failure = ValidationResult(
            check_name="balance_sheet_balances",
            passed=False,
            entity_type="financial_statement",
            entity_id=str(source_version_id),
            severity="error",
            details={"difference": "100.00"},
        )
        first = await QualityGovernanceService(session).apply_gate(
            source_version_id,
            rule_id,
            failure,
            payload_reference=f"source-object-version://{source_version_id}",
            owner_role="data-steward-cvm",
            correlation_id=correlation_id,
        )
    async with session_scope() as session:
        repeated = await QualityGovernanceService(session).apply_gate(
            source_version_id,
            rule_id,
            failure,
            payload_reference=f"source-object-version://{source_version_id}",
            owner_role="data-steward-cvm",
            correlation_id=correlation_id,
        )
        await QualityGovernanceService(session).transition(
            first.incident_id,
            "acknowledged",
            "quality-reviewer-fixture",
            frozenset({"quality_incidents:manage"}),
            correlation_id,
        )
    async with session_scope() as session:
        await QualityGovernanceService(session).transition(
            first.incident_id,
            "resolved",
            "quality-reviewer-fixture",
            frozenset({"quality_incidents:manage"}),
            correlation_id,
            reason="Fixture reconciled against source.",
        )
    async with session_scope() as session:
        quarantine = await session.scalar(
            sa.select(QuarantineRecord).where(QuarantineRecord.quality_incident_id == first.incident_id)
        )
        audit_count = await session.scalar(
            sa.select(sa.func.count(AuditLog.id)).where(AuditLog.correlation_id == correlation_id)
        )

    assert not first.promotion_allowed and first.incident_id == repeated.incident_id
    assert quarantine is not None and quarantine.status == "released"
    assert audit_count == 3
    print("quality-gate-ok blocked=true idempotent=true transition=resolved audit_events=3")


if __name__ == "__main__":
    asyncio.run(main())
