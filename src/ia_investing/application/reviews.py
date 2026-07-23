from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from database.models.agents import AuditLog
from database.models.research import DomainOutboxEvent
from database.models.review import ResearchAssessment, ReviewDecision, ReviewRequest


def canonical_hash(payload: dict[str, object]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode()).hexdigest()


def ensure_segregation(author_id: str, reviewer_id: str) -> None:
    if author_id == reviewer_id:
        raise ValueError("assessment author cannot approve their own work")


class ResearchReviewService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_assessment(
        self,
        research_case_id: UUID,
        assessment_type: str,
        author_type: str,
        author_id: str,
        schema_name: str,
        schema_version: str,
        result: dict[str, object],
        data_as_of: datetime,
        expires_at: datetime,
        permissions: frozenset[str],
    ) -> ResearchAssessment:
        if "research_assessments:create" not in permissions:
            raise PermissionError("permission required: research_assessments:create")
        if data_as_of.tzinfo is None or expires_at.tzinfo is None or expires_at <= data_as_of:
            raise ValueError("assessment requires aware timestamps and expiry after data_as_of")
        assessment = ResearchAssessment(
            research_case_id=research_case_id,
            assessment_type=assessment_type,
            author_type=author_type,
            author_id=author_id,
            schema_name=schema_name,
            schema_version=schema_version,
            result=result,
            result_sha256=canonical_hash(result),
            data_as_of=data_as_of,
            expires_at=expires_at,
        )
        self.session.add(assessment)
        await self.session.flush()
        return assessment

    async def request_review(
        self,
        assessment_id: UUID,
        reviewer_role: str,
        requested_by: str,
        due_at: datetime | None,
        permissions: frozenset[str],
    ) -> ReviewRequest:
        if "research_reviews:request" not in permissions:
            raise PermissionError("permission required: research_reviews:request")
        existing = await self.session.get(ResearchAssessment, assessment_id)
        if existing is None:
            raise LookupError("assessment not found")
        request = ReviewRequest(
            assessment_id=assessment_id,
            required_reviewer_role=reviewer_role,
            status="pending",
            requested_by=requested_by,
            due_at=due_at,
        )
        self.session.add(request)
        await self.session.flush()
        return request

    async def decide(
        self,
        review_request_id: UUID,
        decision: str,
        reviewer_id: str,
        reviewer_roles: frozenset[str],
        permissions: frozenset[str],
        comment: str,
        reason: str,
        correlation_id: UUID,
    ) -> ReviewDecision:
        if "research_reviews:decide" not in permissions:
            raise PermissionError("permission required: research_reviews:decide")
        request = await self.session.get(ReviewRequest, review_request_id, with_for_update=True)
        if request is None:
            raise LookupError("review request not found")
        if request.status != "pending":
            raise ValueError("review request was already decided")
        if request.required_reviewer_role not in reviewer_roles:
            raise PermissionError("reviewer does not hold the required role")
        assessment = await self.session.get(ResearchAssessment, request.assessment_id)
        assert assessment is not None
        if assessment.expires_at <= datetime.now(UTC):
            request.status = "expired"
            raise ValueError("assessment expired before review")
        ensure_segregation(assessment.author_id, reviewer_id)
        if decision not in {"approved", "rejected", "changes_requested"}:
            raise ValueError("invalid review decision")
        request.status = decision
        record = ReviewDecision(
            review_request_id=request.id,
            reviewer_id=reviewer_id,
            decision=decision,
            comment=comment,
            reason=reason,
            before_hash=assessment.result_sha256,
            after_hash=canonical_hash(assessment.result),
            correlation_id=correlation_id,
        )
        self.session.add(record)
        self.session.add(
            DomainOutboxEvent(
                aggregate_type="research_assessment",
                aggregate_id=assessment.id,
                aggregate_version=1,
                event_type=f"Assessment{decision.title().replace('_', '')}",
                payload={"reviewer": reviewer_id, "reason": reason, "comment": comment},
                correlation_id=correlation_id,
                idempotency_key=f"assessment:{assessment.id}:review:{request.id}",
            )
        )
        self.session.add(
            AuditLog(
                actor_type="human",
                actor_id=reviewer_id,
                action="research_assessment.review",
                entity_type="research_assessment",
                entity_id=assessment.id,
                correlation_id=correlation_id,
                details={
                    "decision": decision,
                    "reason": reason,
                    "before_hash": record.before_hash,
                    "after_hash": record.after_hash,
                },
            )
        )
        await self.session.flush()
        return record
