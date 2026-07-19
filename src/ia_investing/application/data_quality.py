from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

import sqlalchemy as sa
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from data_quality._models import ValidationResult
from database.models.agents import AuditLog
from database.models.data_governance import QualityIncident, QualityRule, QuarantineRecord

ALLOWED_TRANSITIONS = {
    "open": frozenset({"acknowledged", "resolved", "waived"}),
    "acknowledged": frozenset({"resolved", "waived"}),
    "resolved": frozenset(),
    "waived": frozenset({"open"}),
}


class QualityIncidentV1(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: UUID
    quality_rule_id: UUID
    source_object_version_id: UUID
    status: str
    severity: str
    owner_role: str
    impact_summary: str
    resolution_notes: str | None
    waiver_reason: str | None
    waiver_approved_by: str | None
    waiver_expires_at: datetime | None
    created_at: datetime
    updated_at: datetime


def validate_transition(current: str, target: str) -> None:
    if target not in ALLOWED_TRANSITIONS.get(current, frozenset()):
        raise ValueError(f"invalid quality incident transition: {current} -> {target}")


@dataclass(frozen=True, slots=True)
class QualityGateResult:
    promotion_allowed: bool
    incident_id: UUID | None = None
    quarantine_id: UUID | None = None


class QualityGovernanceService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def apply_gate(
        self,
        source_object_version_id: UUID,
        quality_rule_id: UUID,
        validation: ValidationResult,
        payload_reference: str,
        owner_role: str,
        correlation_id: UUID,
    ) -> QualityGateResult:
        rule = await self.session.get(QualityRule, quality_rule_id)
        if rule is None:
            raise ValueError("quality rule not found")
        if validation.check_name != rule.code:
            raise ValueError("validation result does not match quality rule")
        if validation.passed or not rule.is_material:
            return QualityGateResult(True)

        existing = (
            await self.session.execute(
                sa.select(QualityIncident).where(
                    QualityIncident.quality_rule_id == rule.id,
                    QualityIncident.source_object_version_id == source_object_version_id,
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            quarantine = (
                await self.session.execute(
                    sa.select(QuarantineRecord).where(QuarantineRecord.quality_incident_id == existing.id)
                )
            ).scalar_one()
            return QualityGateResult(False, existing.id, quarantine.id)

        incident = QualityIncident(
            quality_rule_id=rule.id,
            source_object_version_id=source_object_version_id,
            status="open",
            severity=rule.severity,
            owner_role=owner_role,
            impact_summary=f"Material validation failed: {validation.check_name}",
            evidence={"entity_type": validation.entity_type, "entity_id": validation.entity_id, **validation.details},
        )
        self.session.add(incident)
        await self.session.flush()
        quarantine = QuarantineRecord(
            source_object_version_id=source_object_version_id,
            quality_incident_id=incident.id,
            stage="canonical-promotion",
            payload_reference=payload_reference,
            status="blocked",
        )
        self.session.add(quarantine)
        self.session.add(
            AuditLog(
                actor_type="system",
                actor_id="quality-gate",
                action="quality_incident.open",
                entity_type="quality_incident",
                entity_id=incident.id,
                correlation_id=correlation_id,
                details={"rule": rule.code, "source_object_version_id": str(source_object_version_id)},
            )
        )
        await self.session.flush()
        return QualityGateResult(False, incident.id, quarantine.id)

    async def transition(
        self,
        incident_id: UUID,
        target: str,
        actor_subject: str,
        permissions: frozenset[str],
        correlation_id: UUID,
        reason: str | None = None,
        waiver_expires_at: datetime | None = None,
    ) -> QualityIncident:
        if "quality_incidents:manage" not in permissions:
            raise PermissionError("quality_incidents:manage permission is required")
        incident = await self.session.get(QualityIncident, incident_id, with_for_update=True)
        if incident is None:
            raise LookupError("quality incident not found")
        validate_transition(incident.status, target)
        now = datetime.now(UTC)
        if target == "waived":
            if not reason or waiver_expires_at is None or waiver_expires_at <= now:
                raise ValueError("waiver requires a reason and a future expiration")
            incident.waiver_reason = reason
            incident.waiver_approved_by = actor_subject
            incident.waiver_expires_at = waiver_expires_at
        elif target == "resolved":
            if not reason:
                raise ValueError("resolution requires notes")
            incident.resolution_notes = reason
        elif target == "open":
            incident.waiver_reason = None
            incident.waiver_approved_by = None
            incident.waiver_expires_at = None
        previous = incident.status
        incident.status = target
        incident.updated_at = now
        if target in {"resolved", "waived"}:
            quarantine = (
                await self.session.execute(
                    sa.select(QuarantineRecord).where(QuarantineRecord.quality_incident_id == incident.id)
                )
            ).scalar_one_or_none()
            if quarantine is not None:
                quarantine.status = "released"
                quarantine.released_at = now
        self.session.add(
            AuditLog(
                actor_type="human",
                actor_id=actor_subject,
                action="quality_incident.transition",
                entity_type="quality_incident",
                entity_id=incident.id,
                correlation_id=correlation_id,
                details={"from": previous, "to": target, "reason": reason},
            )
        )
        return incident
