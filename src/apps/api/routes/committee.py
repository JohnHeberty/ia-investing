from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, model_validator

from apps.api.dependencies import get_committee_service
from apps.api.security import AuthContext, actor_uuid, require_permission
from ia_investing.application.committee_service import (
    CommitteeService,
    ConflictOfInterestError,
    DuplicateVoteError,
    InvalidTransitionError,
    MajorityNotReachedError,
    QuorumNotMetError,
)

router = APIRouter(prefix="/api/v1/committee", tags=["committee"])


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


def _committee_error(exc: Exception) -> HTTPException:
    if isinstance(exc, LookupError):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, PermissionError | ConflictOfInterestError):
        return HTTPException(status_code=403, detail=str(exc))
    return HTTPException(status_code=409, detail=str(exc))


@router.post("/sessions", status_code=201)
async def create_session(
    body: CreateSessionRequest,
    auth: AuthContext = Depends(require_permission("committee:create")),
    service: CommitteeService = Depends(get_committee_service),
) -> dict[str, Any]:
    session = await service.create_session(
        thesis_ids=body.thesis_ids,
        members=[member.model_dump(mode="json") for member in body.members],
        scheduled_at=body.scheduled_at,
        agenda=body.agenda,
        actor_id=actor_uuid(auth),
    )
    return {"id": str(session.id), "state": session.state, "scheduled_at": session.scheduled_at.isoformat()}


@router.get("/sessions")
async def list_sessions(
    state: str | None = Query(None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    _auth: AuthContext = Depends(require_permission("committee:read")),
    service: CommitteeService = Depends(get_committee_service),
) -> dict[str, Any]:
    sessions, total = await service.list_sessions(state=state, limit=limit, offset=offset)
    return {
        "items": [
            {
                "id": str(item.id),
                "state": item.state,
                "scheduled_at": item.scheduled_at.isoformat() if item.scheduled_at else None,
                "total_members": item.total_members,
                "present_members": item.present_members,
                "created_at": item.created_at.isoformat() if item.created_at else None,
            }
            for item in sessions
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/sessions/pending")
async def get_pending(
    _auth: AuthContext = Depends(require_permission("committee:read")),
    service: CommitteeService = Depends(get_committee_service),
) -> list[dict[str, Any]]:
    return await service.get_pending_sessions()


@router.get("/sessions/{session_id}")
async def get_session(
    session_id: UUID,
    _auth: AuthContext = Depends(require_permission("committee:read")),
    service: CommitteeService = Depends(get_committee_service),
) -> dict[str, Any]:
    try:
        return await service.get_session(session_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/sessions/{session_id}/convene")
async def convene_session(
    session_id: UUID,
    body: ConveneSessionRequest,
    auth: AuthContext = Depends(require_permission("committee:chair")),
    service: CommitteeService = Depends(get_committee_service),
) -> dict[str, Any]:
    try:
        session = await service.convene_session(
            session_id=session_id,
            present_member_ids=body.present_member_ids,
            actor_id=actor_uuid(auth),
        )
    except (LookupError, InvalidTransitionError, ValueError) as exc:
        raise _committee_error(exc) from exc
    return {"id": str(session.id), "state": session.state, "present_members": session.present_members}


@router.post("/sessions/{session_id}/voting")
async def start_voting(
    session_id: UUID,
    body: StartVotingRequest,
    auth: AuthContext = Depends(require_permission("committee:chair")),
    service: CommitteeService = Depends(get_committee_service),
) -> dict[str, Any]:
    try:
        session = await service.start_voting(
            session_id=session_id,
            proposals=[proposal.model_dump(mode="json") for proposal in body.proposals],
            actor_id=actor_uuid(auth),
        )
    except (LookupError, InvalidTransitionError, QuorumNotMetError, ValueError) as exc:
        raise _committee_error(exc) from exc
    return {"id": str(session.id), "state": session.state, "proposals": session.agenda.get("proposals", [])}


@router.post("/sessions/{session_id}/vote")
async def cast_vote(
    session_id: UUID,
    body: CastVoteRequest,
    auth: AuthContext = Depends(require_permission("committee:vote")),
    service: CommitteeService = Depends(get_committee_service),
) -> dict[str, Any]:
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
        raise _committee_error(exc) from exc
    return {"id": str(vote.id), "vote": vote.vote, "proposal_id": vote.proposal_id}


@router.post("/sessions/{session_id}/finalize")
async def finalize_voting(
    session_id: UUID,
    auth: AuthContext = Depends(require_permission("committee:chair")),
    service: CommitteeService = Depends(get_committee_service),
) -> dict[str, Any]:
    try:
        session = await service.finalize_voting(session_id=session_id, actor_id=actor_uuid(auth))
    except (LookupError, InvalidTransitionError, MajorityNotReachedError) as exc:
        raise _committee_error(exc) from exc
    return {
        "id": str(session.id),
        "state": session.state,
        "votes_in_favor": session.votes_in_favor,
        "votes_against": session.votes_against,
    }


@router.post("/sessions/{session_id}/publish")
async def publish_decision(
    session_id: UUID,
    body: PublishDecisionRequest,
    auth: AuthContext = Depends(require_permission("committee:publish")),
    service: CommitteeService = Depends(get_committee_service),
) -> dict[str, Any]:
    try:
        session = await service.publish_decision(
            session_id=session_id,
            decision=body.decision,
            rationale=body.rationale,
            actor_id=actor_uuid(auth),
            actor_subject=auth.subject,
        )
    except (LookupError, PermissionError, InvalidTransitionError, ValueError) as exc:
        raise _committee_error(exc) from exc
    return {
        "id": str(session.id),
        "state": session.state,
        "decision": session.decision,
        "published_at": session.published_at.isoformat() if session.published_at else None,
    }
