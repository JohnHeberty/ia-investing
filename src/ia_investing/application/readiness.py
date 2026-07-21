from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.agents import AuditLog
from database.models.readiness import (
    ReadinessControl,
    ReadinessDecision,
    ReadinessDecisionPack,
    ReadinessEvidence,
    ReadinessFinding,
    ReadinessVote,
)
from ia_investing.domain.identity import InstitutionalAccessContext
from ia_investing.domain.readiness import (
    EvidenceStatus,
    FindingStatus,
    VoteStatus,
    evaluate_readiness_gate,
    freeze_pack_manifest,
)


class ReadinessService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def _require(context: InstitutionalAccessContext, permission: str) -> None:
        if permission not in context.permissions:
            raise PermissionError(f"permission required: {permission}")

    async def register_evidence(
        self, payload: dict[str, object], context: InstitutionalAccessContext, correlation_id: UUID
    ) -> ReadinessEvidence:
        self._require(context, "readiness:submit")
        evidence = ReadinessEvidence(organization_id=context.organization_id, status="pending", **payload)
        self.session.add(evidence)
        await self.session.flush()
        self._audit("readiness_evidence.register", "readiness_evidence", evidence.id, context, correlation_id)
        return evidence

    async def verify_evidence(
        self,
        evidence_id: UUID,
        *,
        accepted: bool,
        context: InstitutionalAccessContext,
        correlation_id: UUID,
    ) -> ReadinessEvidence:
        self._require(context, "readiness:verify")
        evidence = await self.session.get(ReadinessEvidence, evidence_id, with_for_update=True)
        if evidence is None or evidence.organization_id != context.organization_id:
            raise LookupError("readiness evidence not found")
        if evidence.status != "pending":
            raise ValueError("readiness evidence has already been decided")
        evidence.status = "verified" if accepted else "rejected"
        evidence.verified_by = context.subject
        evidence.verified_at = datetime.now(UTC)
        self._audit("readiness_evidence.verify", "readiness_evidence", evidence.id, context, correlation_id)
        return evidence

    async def freeze_pack(
        self,
        *,
        manifest: dict[str, object],
        expires_at: datetime,
        context: InstitutionalAccessContext,
        correlation_id: UUID,
    ) -> ReadinessDecisionPack:
        self._require(context, "readiness:freeze")
        now = datetime.now(UTC)
        if expires_at <= now:
            raise ValueError("decision pack expiration must be in the future")
        digest, canonical = freeze_pack_manifest(manifest)
        existing = await self.session.scalar(
            sa.select(ReadinessDecisionPack).where(
                ReadinessDecisionPack.organization_id == context.organization_id,
                ReadinessDecisionPack.content_sha256 == digest,
            )
        )
        if existing is not None:
            return existing
        version = (
            await self.session.scalar(
                sa.select(sa.func.max(ReadinessDecisionPack.version)).where(
                    ReadinessDecisionPack.organization_id == context.organization_id
                )
            )
            or 0
        ) + 1
        pack = ReadinessDecisionPack(
            organization_id=context.organization_id,
            version=version,
            content_sha256=digest,
            manifest=canonical,
            frozen_by=context.subject,
            frozen_at=now,
            expires_at=expires_at,
        )
        self.session.add(pack)
        await self.session.flush()
        self._audit("readiness_pack.freeze", "readiness_decision_pack", pack.id, context, correlation_id)
        return pack

    async def vote(
        self,
        pack_id: UUID,
        *,
        role: str,
        vote: str,
        rationale: str,
        conflicts: list[str],
        context: InstitutionalAccessContext,
        correlation_id: UUID,
    ) -> ReadinessVote:
        self._require(context, "readiness:vote")
        pack = await self.session.get(ReadinessDecisionPack, pack_id)
        if pack is None or pack.organization_id != context.organization_id:
            raise LookupError("readiness decision pack not found")
        if pack.expires_at <= datetime.now(UTC):
            raise ValueError("cannot vote on an expired decision pack")
        row = ReadinessVote(
            decision_pack_id=pack.id,
            voter_subject=context.subject,
            voter_role=role,
            vote=vote,
            rationale=rationale,
            conflicts=conflicts,
            signed_at=datetime.now(UTC),
        )
        self.session.add(row)
        await self.session.flush()
        self._audit("readiness_vote.sign", "readiness_vote", row.id, context, correlation_id)
        return row

    async def decide(
        self,
        pack_id: UUID,
        *,
        context: InstitutionalAccessContext,
        correlation_id: UUID,
    ) -> ReadinessDecision:
        self._require(context, "readiness:decide")
        pack = await self.session.get(ReadinessDecisionPack, pack_id, with_for_update=True)
        if pack is None or pack.organization_id != context.organization_id:
            raise LookupError("readiness decision pack not found")
        existing = await self.session.scalar(
            sa.select(ReadinessDecision).where(ReadinessDecision.decision_pack_id == pack.id)
        )
        if existing is not None:
            return existing
        evidence_ids = self._manifest_ids(pack.manifest, "evidence_ids")
        evidence = list(
            (
                await self.session.scalars(
                    sa.select(ReadinessEvidence).where(
                        ReadinessEvidence.organization_id == context.organization_id,
                        ReadinessEvidence.id.in_(evidence_ids),
                    )
                )
            ).all()
        )
        findings = list(
            (
                await self.session.scalars(
                    sa.select(ReadinessFinding).where(ReadinessFinding.organization_id == context.organization_id)
                )
            ).all()
        )
        votes = list(
            (
                await self.session.scalars(sa.select(ReadinessVote).where(ReadinessVote.decision_pack_id == pack.id))
            ).all()
        )
        now = datetime.now(UTC)
        evaluation = evaluate_readiness_gate(
            at=now,
            pack_expires_at=pack.expires_at,
            evidence=tuple(
                EvidenceStatus(item.evidence_type, item.status, item.independent, item.expires_at) for item in evidence
            ),
            findings=tuple(
                FindingStatus(item.finding_key, item.severity, item.status, item.exception_expires_at)
                for item in findings
            ),
            votes=tuple(VoteStatus(item.voter_role, item.vote, bool(item.conflicts)) for item in votes),
        )
        decision = ReadinessDecision(
            decision_pack_id=pack.id,
            result=evaluation.result,
            authorized_scope=evaluation.authorized_scope,
            blockers=[{"description": item} for item in evaluation.blockers],
            conditions=[{"description": item} for item in evaluation.conditions],
            dissent=[
                {"role": item.voter_role, "vote": item.vote, "rationale": item.rationale}
                for item in votes
                if item.vote != evaluation.result
            ],
            decided_by=context.subject,
            decided_at=now,
            expires_at=pack.expires_at,
        )
        self.session.add(decision)
        await self.session.flush()
        self._audit("readiness_decision.record", "readiness_decision", decision.id, context, correlation_id)
        return decision

    @staticmethod
    def _manifest_ids(manifest: dict[str, object], key: str) -> list[UUID]:
        values = manifest.get(key, [])
        if not isinstance(values, list):
            raise ValueError(f"decision pack manifest {key} must be a list")
        try:
            return [UUID(str(value)) for value in values]
        except ValueError as exc:
            raise ValueError(f"decision pack manifest {key} contains an invalid UUID") from exc

    def _audit(
        self,
        action: str,
        entity_type: str,
        entity_id: UUID,
        context: InstitutionalAccessContext,
        correlation_id: UUID,
    ) -> None:
        self.session.add(
            AuditLog(
                actor_type="human",
                actor_id=context.subject,
                action=action,
                entity_type=entity_type,
                entity_id=entity_id,
                correlation_id=correlation_id,
                details={"organization_id": str(context.organization_id)},
            )
        )

    async def list_evidence(
        self,
        context: InstitutionalAccessContext,
        *,
        limit: int = 50,
    ) -> list[ReadinessEvidence]:
        result = await self.session.scalars(
            sa.select(ReadinessEvidence)
            .where(ReadinessEvidence.organization_id == context.organization_id)
            .order_by(ReadinessEvidence.issued_at.desc())
            .limit(limit)
        )
        return list(result.all())

    async def list_findings(
        self,
        context: InstitutionalAccessContext,
        *,
        status: str | None = None,
        limit: int = 50,
    ) -> list[ReadinessFinding]:
        stmt = sa.select(ReadinessFinding).where(ReadinessFinding.organization_id == context.organization_id)
        if status is not None:
            stmt = stmt.where(ReadinessFinding.status == status)
        result = await self.session.scalars(stmt.order_by(ReadinessFinding.opened_at.desc()).limit(limit))
        return list(result.all())

    async def create_finding(
        self,
        payload: dict[str, object],
        context: InstitutionalAccessContext,
        correlation_id: UUID,
    ) -> ReadinessFinding:
        self._require(context, "readiness:verify")
        finding = ReadinessFinding(organization_id=context.organization_id, status="open", **payload)
        self.session.add(finding)
        await self.session.flush()
        self._audit("readiness_finding.create", "readiness_finding", finding.id, context, correlation_id)
        return finding

    async def update_finding(
        self,
        finding_id: UUID,
        *,
        status: str | None = None,
        remediation: str | None = None,
        exception_expires_at: datetime | None = None,
        retest_evidence_id: UUID | None = None,
        context: InstitutionalAccessContext,
        correlation_id: UUID,
    ) -> ReadinessFinding:
        self._require(context, "readiness:verify")
        finding = await self.session.get(ReadinessFinding, finding_id, with_for_update=True)
        if finding is None or finding.organization_id != context.organization_id:
            raise LookupError("readiness finding not found")
        if status is not None:
            finding.status = status
            if status == "closed":
                finding.closed_at = datetime.now(UTC)
                if retest_evidence_id is not None:
                    finding.retest_evidence_id = retest_evidence_id
        if remediation is not None:
            finding.remediation = remediation
        if exception_expires_at is not None:
            finding.exception_expires_at = exception_expires_at
        self._audit("readiness_finding.update", "readiness_finding", finding.id, context, correlation_id)
        return finding

    async def list_decision_packs(
        self,
        context: InstitutionalAccessContext,
        *,
        limit: int = 20,
    ) -> list[ReadinessDecisionPack]:
        result = await self.session.scalars(
            sa.select(ReadinessDecisionPack)
            .where(ReadinessDecisionPack.organization_id == context.organization_id)
            .order_by(ReadinessDecisionPack.version.desc())
            .limit(limit)
        )
        return list(result.all())

    async def list_decisions(
        self,
        context: InstitutionalAccessContext,
        *,
        limit: int = 20,
    ) -> list[ReadinessDecision]:
        packs = await self.list_decision_packs(context, limit=limit)
        pack_ids = [p.id for p in packs]
        if not pack_ids:
            return []
        result = await self.session.scalars(
            sa.select(ReadinessDecision)
            .where(ReadinessDecision.decision_pack_id.in_(pack_ids))
            .order_by(ReadinessDecision.decided_at.desc())
            .limit(limit)
        )
        return list(result.all())

    async def list_controls(
        self,
        context: InstitutionalAccessContext,
        *,
        limit: int = 50,
    ) -> list[ReadinessControl]:
        result = await self.session.scalars(
            sa.select(ReadinessControl)
            .where(ReadinessControl.organization_id == context.organization_id)
            .order_by(ReadinessControl.domain)
            .limit(limit)
        )
        return list(result.all())
