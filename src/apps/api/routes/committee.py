from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field, model_validator

from apps.api._errors import map_error
from apps.api.dependencies import get_committee_service
from apps.api.security import AuthContext, actor_uuid, require_permission
from ia_investing.application._audit_mixin import AuditMixin
from ia_investing.application.committee_service import (
    CommitteeService,
    ConflictOfInterestError,
    DuplicateVoteError,
    InvalidTransitionError,
    MajorityNotReachedError,
    QuorumNotMetError,
)

router = APIRouter(prefix="/api/v1/committee", tags=["committee"])
_audit = AuditMixin()


class CommitteeMemberInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    member_id: str = Field(min_length=1, max_length=100)
    subject: str = Field(min_length=1, max_length=255)
    role: str = Field(min_length=1, max_length=100)
    conflicts: list[str] = Field(default_factory=list)


class ProposalInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    proposal_id: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=250)
    action: Literal["add", "increase", "maintain", "reduce", "exit", "replace", "watch", "no_action"]
    payload: dict[str, Any] = Field(default_factory=dict)


class CreateSessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    thesis_ids: list[str] = Field(min_length=1)
    members: list[CommitteeMemberInput] = Field(min_length=1)
    scheduled_at: datetime
    agenda: dict[str, Any] | None = None

    @model_validator(mode="after")
    def unique_members(self) -> CreateSessionRequest:
        ids = [member.member_id for member in self.members]
        subjects = [member.subject for member in self.members]
        if len(ids) != len(set(ids)) or len(subjects) != len(set(subjects)):
            raise ValueError("committee member_id and subject values must be unique")
        return self


class ConveneSessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    present_member_ids: list[str] = Field(min_length=1)


class StartVotingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    proposals: list[ProposalInput] = Field(min_length=1, max_length=1)


class CastVoteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    proposal_id: str = Field(min_length=1, max_length=100)
    vote: Literal["in_favor", "against", "abstain"]
    justification: str | None = Field(default=None, max_length=4000)


class PublishDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: Literal[
        "approve",
        "approve_with_conditions",
        "reject",
        "request_more_information",
        "defer",
        "watchlist",
    ]
    rationale: str | None = Field(default=None, max_length=10000)

    @model_validator(mode="after")
    def rationale_required_for_non_plain_approval(self) -> PublishDecisionRequest:
        if self.decision != "approve" and not (self.rationale or "").strip():
            raise ValueError("rationale is required unless decision is approve")
        return self


class CommitteeSessionCreatedResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    state: str
    scheduled_at: str


class CommitteeSessionListItem(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    state: str
    scheduled_at: str | None = None
    total_members: int
    present_members: int
    created_at: str | None = None


class PaginatedCommitteeSessions(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    items: list[CommitteeSessionListItem]
    total: int
    limit: int
    offset: int


class CommitteeSessionDetailResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    state: str
    present_members: int | None = None


class CommitteeVotingResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    state: str
    proposals: list[Any]


class CommitteeVoteResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    vote: str
    proposal_id: str


class CommitteeFinalizeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    state: str
    votes_in_favor: int
    votes_against: int


class CommitteePublishResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    state: str
    decision: str
    published_at: str | None = None


@router.post("/sessions", status_code=201, response_model=CommitteeSessionCreatedResponse)
async def create_session(
    body: CreateSessionRequest,
    auth: AuthContext = Depends(require_permission("committee:create")),
    service: CommitteeService = Depends(get_committee_service),
) -> CommitteeSessionCreatedResponse:
    session = await service.create_session(
        thesis_ids=body.thesis_ids,
        members=[member.model_dump(mode="json") for member in body.members],
        scheduled_at=body.scheduled_at,
        agenda=body.agenda,
        actor_id=actor_uuid(auth),
    )
    await _audit._audit(
        session=service._session,
        tenant_id=auth.organization_id,
        actor_id=UUID(auth.subject) if auth.subject else None,
        action="create",
        resource_type="committee_session",
        resource_id=session.id,
    )
    return CommitteeSessionCreatedResponse(
        id=str(session.id), state=session.state, scheduled_at=session.scheduled_at.isoformat()
    )


@router.get("/sessions", response_model=PaginatedCommitteeSessions)
async def list_sessions(
    state: str | None = Query(None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    auth: AuthContext = Depends(require_permission("committee:read")),
    service: CommitteeService = Depends(get_committee_service),
) -> PaginatedCommitteeSessions:
    sessions, total = await service.list_sessions(state=state, limit=limit, offset=offset)
    return PaginatedCommitteeSessions(
        items=[
            CommitteeSessionListItem(
                id=str(item.id),
                state=item.state,
                scheduled_at=item.scheduled_at.isoformat() if item.scheduled_at else None,
                total_members=item.total_members,
                present_members=item.present_members,
                created_at=item.created_at.isoformat() if item.created_at else None,
            )
            for item in sessions
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/sessions/pending", response_model=list[dict[str, Any]])
async def get_pending(
    auth: AuthContext = Depends(require_permission("committee:read")),
    service: CommitteeService = Depends(get_committee_service),
) -> list[dict[str, Any]]:
    return await service.get_pending_sessions()


@router.get("/sessions/{session_id}", response_model=dict[str, Any])
async def get_session(
    session_id: UUID,
    auth: AuthContext = Depends(require_permission("committee:read")),
    service: CommitteeService = Depends(get_committee_service),
) -> dict[str, Any]:
    try:
        return await service.get_session(session_id)
    except LookupError as exc:
        raise map_error(exc) from exc


@router.post("/sessions/{session_id}/convene", response_model=CommitteeSessionDetailResponse)
async def convene_session(
    session_id: UUID,
    body: ConveneSessionRequest,
    auth: AuthContext = Depends(require_permission("committee:chair")),
    service: CommitteeService = Depends(get_committee_service),
) -> CommitteeSessionDetailResponse:
    try:
        session = await service.convene_session(
            session_id=session_id,
            present_member_ids=body.present_member_ids,
            actor_id=actor_uuid(auth),
        )
    except (LookupError, InvalidTransitionError, ValueError) as exc:
        raise map_error(exc) from exc
    await _audit._audit(
        session=service._session,
        tenant_id=auth.organization_id,
        actor_id=UUID(auth.subject) if auth.subject else None,
        action="update",
        resource_type="committee_session",
        resource_id=session_id,
        changes={"action": "convene"},
    )
    return CommitteeSessionDetailResponse(
        id=str(session.id), state=session.state, present_members=session.present_members
    )


@router.post("/sessions/{session_id}/voting", response_model=CommitteeVotingResponse)
async def start_voting(
    session_id: UUID,
    body: StartVotingRequest,
    auth: AuthContext = Depends(require_permission("committee:chair")),
    service: CommitteeService = Depends(get_committee_service),
) -> CommitteeVotingResponse:
    try:
        session = await service.start_voting(
            session_id=session_id,
            proposals=[proposal.model_dump(mode="json") for proposal in body.proposals],
            actor_id=actor_uuid(auth),
        )
    except (LookupError, InvalidTransitionError, QuorumNotMetError, ValueError) as exc:
        raise map_error(exc) from exc
    await _audit._audit(
        session=service._session,
        tenant_id=auth.organization_id,
        actor_id=UUID(auth.subject) if auth.subject else None,
        action="update",
        resource_type="committee_session",
        resource_id=session_id,
        changes={"action": "start_voting"},
    )
    return CommitteeVotingResponse(
        id=str(session.id), state=session.state, proposals=session.agenda.get("proposals", [])
    )


@router.post("/sessions/{session_id}/vote", response_model=CommitteeVoteResponse)
async def cast_vote(
    session_id: UUID,
    body: CastVoteRequest,
    auth: AuthContext = Depends(require_permission("committee:vote")),
    service: CommitteeService = Depends(get_committee_service),
) -> CommitteeVoteResponse:
    try:
        vote = await service.cast_vote(
            session_id=session_id,
            member_id=auth.subject,
            proposal_id=body.proposal_id,
            vote=body.vote,
            justification=body.justification,
            actor_id=actor_uuid(auth),
            actor_subject=auth.subject,
        )
    except (
        LookupError,
        PermissionError,
        ConflictOfInterestError,
        InvalidTransitionError,
        DuplicateVoteError,
    ) as exc:
        raise map_error(exc) from exc
    await _audit._audit(
        session=service._session,
        tenant_id=auth.organization_id,
        actor_id=UUID(auth.subject) if auth.subject else None,
        action="vote",
        resource_type="committee_vote",
        resource_id=vote.id,
        changes={"proposal_id": body.proposal_id, "vote": body.vote},
    )
    return CommitteeVoteResponse(id=str(vote.id), vote=vote.vote, proposal_id=vote.proposal_id)


@router.post("/sessions/{session_id}/finalize", response_model=CommitteeFinalizeResponse)
async def finalize_voting(
    session_id: UUID,
    auth: AuthContext = Depends(require_permission("committee:chair")),
    service: CommitteeService = Depends(get_committee_service),
) -> CommitteeFinalizeResponse:
    try:
        session = await service.finalize_voting(session_id=session_id, actor_id=actor_uuid(auth))
    except (LookupError, InvalidTransitionError, MajorityNotReachedError) as exc:
        raise map_error(exc) from exc
    await _audit._audit(
        session=service._session,
        tenant_id=auth.organization_id,
        actor_id=UUID(auth.subject) if auth.subject else None,
        action="update",
        resource_type="committee_session",
        resource_id=session_id,
        changes={"action": "finalize_voting"},
    )
    return CommitteeFinalizeResponse(
        id=str(session.id),
        state=session.state,
        votes_in_favor=session.votes_in_favor,
        votes_against=session.votes_against,
    )


@router.post("/sessions/{session_id}/publish", response_model=CommitteePublishResponse)
async def publish_decision(
    session_id: UUID,
    body: PublishDecisionRequest,
    auth: AuthContext = Depends(require_permission("committee:publish")),
    service: CommitteeService = Depends(get_committee_service),
) -> CommitteePublishResponse:
    try:
        session = await service.publish_decision(
            session_id=session_id,
            decision=body.decision,
            rationale=body.rationale,
            actor_id=actor_uuid(auth),
            actor_subject=auth.subject,
        )
    except (LookupError, PermissionError, InvalidTransitionError, ValueError) as exc:
        raise map_error(exc) from exc
    await _audit._audit(
        session=service._session,
        tenant_id=auth.organization_id,
        actor_id=UUID(auth.subject) if auth.subject else None,
        action="approve" if body.decision == "approve" else "reject",
        resource_type="committee_decision",
        resource_id=session_id,
        changes={"decision": body.decision},
    )
    return CommitteePublishResponse(
        id=str(session.id),
        state=session.state,
        decision=session.decision,
        published_at=session.published_at.isoformat() if session.published_at else None,
    )
