from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.agents import AuditLog
from database.models.research import (
    ClaimEvidenceLink,
    DomainOutboxEvent,
    ResearchCase,
    ResearchClaim,
    ResearchEvidence,
    ResearchQuestion,
)

CASE_TRANSITIONS = {
    "draft": {"triage": "research_cases:submit"},
    "triage": {"in_research": "research_cases:assign"},
    "in_research": {"review": "research_cases:submit"},
    "review": {"approved": "research_cases:review", "rejected": "research_cases:review"},
    "approved": {"closed": "research_cases:close"},
    "rejected": {"closed": "research_cases:close"},
    "closed": {"triage": "research_cases:reopen"},
}


class ResearchConcurrencyError(RuntimeError):
    pass


class ResearchIdempotencyConflictError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class CreateResearchCase:
    case_type: str
    title: str
    priority: str
    issuer_id: UUID
    instrument_id: UUID | None
    data_as_of: datetime
    due_at: datetime | None
    questions: tuple[str, ...]

    def request_hash(self) -> str:
        payload = {
            "case_type": self.case_type,
            "title": self.title,
            "priority": self.priority,
            "issuer_id": str(self.issuer_id),
            "instrument_id": str(self.instrument_id) if self.instrument_id else None,
            "data_as_of": self.data_as_of.isoformat(),
            "due_at": self.due_at.isoformat() if self.due_at else None,
            "questions": self.questions,
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def required_permission(current: str, target: str) -> str:
    permission = CASE_TRANSITIONS.get(current, {}).get(target)
    if permission is None:
        raise ValueError(f"invalid research case transition: {current} -> {target}")
    return permission


class ResearchCaseService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        command: CreateResearchCase,
        actor_subject: str,
        permissions: frozenset[str],
        idempotency_key: str,
        correlation_id: UUID,
    ) -> tuple[ResearchCase, bool]:
        if "research_cases:create" not in permissions:
            raise PermissionError("permission required: research_cases:create")
        for name, value in (("data_as_of", command.data_as_of), ("due_at", command.due_at)):
            if value is not None and value.tzinfo is None:
                raise ValueError(f"{name} must include timezone information")
        request_hash = command.request_hash()
        existing = (
            await self.session.execute(sa.select(ResearchCase).where(ResearchCase.idempotency_key == idempotency_key))
        ).scalar_one_or_none()
        if existing is not None:
            if existing.request_hash != request_hash:
                raise ResearchIdempotencyConflictError("idempotency key was used with a different research case")
            return existing, False
        case = ResearchCase(
            case_type=command.case_type,
            title=command.title,
            priority=command.priority,
            state="draft",
            issuer_id=command.issuer_id,
            instrument_id=command.instrument_id,
            data_as_of=command.data_as_of,
            due_at=command.due_at,
            created_by=actor_subject,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
            lock_version=1,
        )
        self.session.add(case)
        await self.session.flush()
        for ordinal, question in enumerate(command.questions):
            self.session.add(
                ResearchQuestion(
                    research_case_id=case.id,
                    question=question,
                    is_required=True,
                    status="open",
                    ordinal=ordinal,
                )
            )
        self.session.add(
            DomainOutboxEvent(
                aggregate_type="research_case",
                aggregate_id=case.id,
                aggregate_version=1,
                event_type="ResearchCaseCreated",
                payload={"actor": actor_subject, "question_count": len(command.questions)},
                correlation_id=correlation_id,
                idempotency_key=f"research-case:{case.id}:v1:ResearchCaseCreated",
            )
        )
        self.session.add(
            AuditLog(
                actor_type="human",
                actor_id=actor_subject,
                action="research_case.create",
                entity_type="research_case",
                entity_id=case.id,
                correlation_id=correlation_id,
                details={"request_hash": request_hash, "question_count": len(command.questions)},
            )
        )
        return case, True

    async def transition(
        self,
        case_id: UUID,
        target: str,
        expected_version: int,
        actor_subject: str,
        permissions: frozenset[str],
        correlation_id: UUID,
        reason: str,
    ) -> ResearchCase:
        case = await self.session.get(ResearchCase, case_id, with_for_update=True)
        if case is None:
            raise LookupError("research case not found")
        if case.lock_version != expected_version:
            raise ResearchConcurrencyError("research case ETag no longer matches")
        permission = required_permission(case.state, target)
        if permission not in permissions:
            raise PermissionError(f"permission required: {permission}")
        if target == "closed":
            pending = await self.session.scalar(
                sa.select(sa.func.count(ResearchQuestion.id)).where(
                    ResearchQuestion.research_case_id == case.id,
                    ResearchQuestion.is_required.is_(True),
                    ResearchQuestion.status == "open",
                )
            )
            if pending:
                raise ValueError("required research questions are still open")

        previous = case.state
        case.state = target
        case.lock_version += 1
        case.updated_at = datetime.now(UTC)
        event_type = {
            "triage": "ResearchCaseOpened" if previous == "draft" else "ResearchCaseReopened",
            "approved": "ResearchCaseApproved",
            "rejected": "ResearchCaseRejected",
            "closed": "ResearchCaseClosed",
        }.get(target, "ResearchCaseStateChanged")
        event = DomainOutboxEvent(
            aggregate_type="research_case",
            aggregate_id=case.id,
            aggregate_version=case.lock_version,
            event_type=event_type,
            payload={"from": previous, "to": target, "actor": actor_subject, "reason": reason},
            correlation_id=correlation_id,
            idempotency_key=f"research-case:{case.id}:v{case.lock_version}:{event_type}",
        )
        self.session.add(event)
        self.session.add(
            AuditLog(
                actor_type="human",
                actor_id=actor_subject,
                action="research_case.transition",
                entity_type="research_case",
                entity_id=case.id,
                correlation_id=correlation_id,
                details={"from": previous, "to": target, "reason": reason, "version": case.lock_version},
            )
        )
        return case

    async def list_cases(
        self,
        state: str | None,
        as_of: datetime | None,
        after: UUID | None,
        limit: int,
    ) -> list[ResearchCase]:
        if as_of is not None and as_of.tzinfo is None:
            raise ValueError("as_of must include timezone information")
        capped_limit = min(limit, 100)
        stmt = sa.select(ResearchCase).order_by(ResearchCase.id).limit(capped_limit + 1)
        if state is not None:
            stmt = stmt.where(ResearchCase.state == state)
        if as_of is not None:
            stmt = stmt.where(ResearchCase.data_as_of <= as_of)
        if after is not None:
            stmt = stmt.where(ResearchCase.id > after)
        return list((await self.session.scalars(stmt)).all())

    async def get_case(self, case_id: UUID) -> ResearchCase | None:
        return await self.session.get(ResearchCase, case_id)


class ClaimService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def verify(
        self,
        claim_id: UUID,
        cutoff: datetime,
        actor_subject: str,
        permissions: frozenset[str],
        correlation_id: UUID,
    ) -> ResearchClaim:
        if "research_claims:verify" not in permissions:
            raise PermissionError("permission required: research_claims:verify")
        if cutoff.tzinfo is None:
            raise ValueError("cutoff must include timezone information")
        claim = await self.session.get(ResearchClaim, claim_id, with_for_update=True)
        if claim is None:
            raise LookupError("research claim not found")
        supporting = list(
            (
                await self.session.execute(
                    sa.select(ResearchEvidence)
                    .join(ClaimEvidenceLink, ClaimEvidenceLink.evidence_id == ResearchEvidence.id)
                    .where(
                        ClaimEvidenceLink.claim_id == claim.id,
                        ClaimEvidenceLink.stance == "supporting",
                        ResearchEvidence.knowledge_at <= cutoff,
                        ResearchEvidence.revoked_at.is_(None),
                        sa.or_(ResearchEvidence.valid_until.is_(None), ResearchEvidence.valid_until > cutoff),
                    )
                )
            ).scalars()
        )
        if claim.is_material and not supporting:
            raise ValueError("material claim cannot be verified without valid supporting evidence")
        previous = claim.status
        claim.status = "verified"
        self.session.add(
            DomainOutboxEvent(
                aggregate_type="research_claim",
                aggregate_id=claim.id,
                aggregate_version=1,
                event_type="ClaimVerified",
                payload={"actor": actor_subject, "cutoff": cutoff.isoformat(), "evidence_count": len(supporting)},
                correlation_id=correlation_id,
                idempotency_key=f"claim:{claim.id}:verified:{hashlib.sha256(cutoff.isoformat().encode()).hexdigest()}",
            )
        )
        self.session.add(
            AuditLog(
                actor_type="human",
                actor_id=actor_subject,
                action="research_claim.verify",
                entity_type="research_claim",
                entity_id=claim.id,
                correlation_id=correlation_id,
                details={"from": previous, "to": "verified", "supporting_evidence": len(supporting)},
            )
        )
        return claim
