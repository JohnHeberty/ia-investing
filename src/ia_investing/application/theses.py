from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.agents import AuditLog
from database.models.research import DomainOutboxEvent, ResearchClaim
from database.models.review import ReviewDecision
from database.models.thesis_domain import (
    ResearchThesis,
    ResearchThesisVersion,
    ThesisVersionClaim,
    ThesisVersionEvidence,
)
from ia_investing.application.research import ResearchConcurrencyError


@dataclass(frozen=True, slots=True)
class ThesisSnapshot:
    summary: str
    assumptions: list[dict[str, object]]
    catalysts: list[dict[str, object]]
    risks: list[dict[str, object]]
    invalidation_criteria: list[dict[str, object]]
    recommendation: str
    recommendation_confidence: Decimal
    data_as_of: datetime
    expires_at: datetime


def snapshot_hash(snapshot: ThesisSnapshot) -> str:
    encoded = json.dumps(asdict(snapshot), ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(encoded.encode()).hexdigest()


def _json_value(value: object) -> object:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json_value(item) for item in value]
    return value


def structured_diff(previous: ThesisSnapshot | None, current: ThesisSnapshot) -> dict[str, object]:
    current_data = asdict(current)
    if previous is None:
        return {key: {"before": None, "after": _json_value(value)} for key, value in current_data.items()}
    previous_data = asdict(previous)
    return {
        key: {"before": _json_value(previous_data[key]), "after": _json_value(value)}
        for key, value in current_data.items()
        if previous_data[key] != value
    }


def from_version(version: ResearchThesisVersion) -> ThesisSnapshot:
    return ThesisSnapshot(
        summary=version.summary,
        assumptions=version.assumptions,
        catalysts=version.catalysts,
        risks=version.risks,
        invalidation_criteria=version.invalidation_criteria,
        recommendation=version.recommendation,
        recommendation_confidence=version.recommendation_confidence,
        data_as_of=version.data_as_of,
        expires_at=version.expires_at,
    )


class ThesisService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_draft(
        self,
        issuer_id: UUID,
        instrument_id: UUID | None,
        snapshot: ThesisSnapshot,
        actor_subject: str,
        permissions: frozenset[str],
        evidence_ids: list[UUID],
        claim_ids: list[UUID],
    ) -> tuple[ResearchThesis, ResearchThesisVersion]:
        if "research_theses:create" not in permissions:
            raise PermissionError("permission required: research_theses:create")
        thesis = ResearchThesis(
            issuer_id=issuer_id,
            instrument_id=instrument_id,
            status="draft",
            lock_version=1,
            created_by=actor_subject,
        )
        self.session.add(thesis)
        await self.session.flush()
        version = await self._add_version(thesis, None, snapshot, actor_subject, evidence_ids, claim_ids)
        return thesis, version

    async def revise(
        self,
        thesis_id: UUID,
        expected_version: int,
        snapshot: ThesisSnapshot,
        actor_subject: str,
        permissions: frozenset[str],
        evidence_ids: list[UUID],
        claim_ids: list[UUID],
    ) -> ResearchThesisVersion:
        if "research_theses:revise" not in permissions:
            raise PermissionError("permission required: research_theses:revise")
        thesis = await self.session.get(ResearchThesis, thesis_id, with_for_update=True)
        if thesis is None:
            raise LookupError("research thesis not found")
        if thesis.lock_version != expected_version:
            raise ResearchConcurrencyError("research thesis ETag no longer matches")
        parent = (
            await self.session.execute(
                sa.select(ResearchThesisVersion)
                .where(ResearchThesisVersion.thesis_id == thesis.id)
                .order_by(ResearchThesisVersion.version_number.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        thesis.lock_version += 1
        return await self._add_version(thesis, parent, snapshot, actor_subject, evidence_ids, claim_ids)

    async def _add_version(
        self,
        thesis: ResearchThesis,
        parent: ResearchThesisVersion | None,
        snapshot: ThesisSnapshot,
        actor_subject: str,
        evidence_ids: list[UUID],
        claim_ids: list[UUID],
    ) -> ResearchThesisVersion:
        if snapshot.data_as_of.tzinfo is None or snapshot.expires_at.tzinfo is None:
            raise ValueError("thesis timestamps must include timezone information")
        if snapshot.expires_at <= snapshot.data_as_of:
            raise ValueError("thesis expiry must be after data_as_of")
        version = ResearchThesisVersion(
            thesis_id=thesis.id,
            version_number=(parent.version_number + 1) if parent else 1,
            parent_version_id=parent.id if parent else None,
            status="draft",
            **asdict(snapshot),
            content_sha256=snapshot_hash(snapshot),
            change_set=structured_diff(from_version(parent) if parent else None, snapshot),
            created_by=actor_subject,
        )
        self.session.add(version)
        await self.session.flush()
        for evidence_id in evidence_ids:
            self.session.add(
                ThesisVersionEvidence(thesis_version_id=version.id, evidence_id=evidence_id, role="supporting")
            )
        for claim_id in claim_ids:
            self.session.add(ThesisVersionClaim(thesis_version_id=version.id, claim_id=claim_id, role="supporting"))
        return version

    async def activate(
        self,
        version_id: UUID,
        review_decision_id: UUID,
        actor_subject: str,
        permissions: frozenset[str],
        correlation_id: UUID,
    ) -> ResearchThesisVersion:
        if "research_theses:approve" not in permissions:
            raise PermissionError("permission required: research_theses:approve")
        version = await self.session.get(ResearchThesisVersion, version_id, with_for_update=True)
        if version is None:
            raise LookupError("thesis version not found")
        if version.status != "draft":
            raise ValueError("only a draft thesis version can be activated")
        decision = await self.session.get(ReviewDecision, review_decision_id)
        if decision is None or decision.decision != "approved":
            raise ValueError("an approved independent review is required")
        if decision.reviewer_id != actor_subject:
            raise PermissionError("the recorded reviewer must activate the thesis")
        evidence_count = await self.session.scalar(
            sa.select(sa.func.count(ThesisVersionEvidence.evidence_id)).where(
                ThesisVersionEvidence.thesis_version_id == version.id
            )
        )
        verified_claims = await self.session.scalar(
            sa.select(sa.func.count(ThesisVersionClaim.claim_id))
            .join(ResearchClaim, ResearchClaim.id == ThesisVersionClaim.claim_id)
            .where(ThesisVersionClaim.thesis_version_id == version.id, ResearchClaim.status == "verified")
        )
        if not evidence_count or not verified_claims:
            raise ValueError("thesis activation requires evidence and at least one verified claim")
        now = datetime.now(UTC)
        if version.expires_at <= now:
            raise ValueError("expired thesis version cannot be activated")
        current = (
            await self.session.execute(
                sa.select(ResearchThesisVersion)
                .where(
                    ResearchThesisVersion.thesis_id == version.thesis_id,
                    ResearchThesisVersion.status == "active",
                )
                .with_for_update()
            )
        ).scalar_one_or_none()
        if current is not None:
            current.status = "superseded"
            current.valid_to = now
        version.status = "active"
        version.valid_from = now
        version.approved_by = actor_subject
        version.approved_at = now
        version.review_decision_id = review_decision_id
        thesis = await self.session.get(ResearchThesis, version.thesis_id, with_for_update=True)
        thesis.status = "active"
        thesis.lock_version += 1
        self.session.add(
            DomainOutboxEvent(
                aggregate_type="research_thesis",
                aggregate_id=thesis.id,
                aggregate_version=thesis.lock_version,
                event_type="ThesisVersionApproved",
                payload={"version_id": str(version.id), "recommendation": version.recommendation},
                correlation_id=correlation_id,
                idempotency_key=f"thesis:{thesis.id}:version:{version.version_number}:approved",
            )
        )
        self.session.add(
            AuditLog(
                actor_type="human",
                actor_id=actor_subject,
                action="research_thesis.activate",
                entity_type="research_thesis",
                entity_id=thesis.id,
                correlation_id=correlation_id,
                details={"version_id": str(version.id), "content_sha256": version.content_sha256},
            )
        )
        return version

    async def active_as_of(self, thesis_id: UUID, as_of: datetime) -> ResearchThesisVersion | None:
        if as_of.tzinfo is None:
            raise ValueError("as_of must include timezone information")
        return (
            await self.session.execute(
                sa.select(ResearchThesisVersion)
                .where(
                    ResearchThesisVersion.thesis_id == thesis_id,
                    ResearchThesisVersion.status.in_(("active", "superseded")),
                    ResearchThesisVersion.valid_from <= as_of,
                    sa.or_(ResearchThesisVersion.valid_to.is_(None), ResearchThesisVersion.valid_to > as_of),
                )
                .order_by(ResearchThesisVersion.version_number.desc())
                .limit(1)
            )
        ).scalar_one_or_none()

    async def mark_expired_stale(self, now: datetime) -> int:
        result = await self.session.execute(
            sa.update(ResearchThesis)
            .where(
                ResearchThesis.status == "active",
                ResearchThesis.id.in_(
                    sa.select(ResearchThesisVersion.thesis_id).where(
                        ResearchThesisVersion.status == "active", ResearchThesisVersion.expires_at <= now
                    )
                ),
            )
            .values(status="stale", lock_version=ResearchThesis.lock_version + 1)
        )
        return int(result.rowcount)
