from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from apps.api.dependencies import get_committee_service
from apps.api.security import AuthContext, require_permission
from ia_investing.application.committee_service import (  # type: ignore[attr-defined]
    CommitteeService,
    DuplicateVoteError,
    InvalidTransitionError,
    MajorityNotReachedError,
)

router = APIRouter(prefix="/api/v1/committee", tags=["committee"])


class CreateSessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    thesis_ids: list[str] = Field(min_length=1)
    members: list[dict[str, Any]] = Field(min_length=1)
    scheduled_at: datetime
    agenda: dict[str, Any] | None = None


class CastVoteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    member_id: str = Field(min_length=1, max_length=100)
    proposal_id: str = Field(min_length=1, max_length=100)
    vote: str = Field(pattern=r"^(in_favor|against|abstain)$")
    justification: str | None = None


class PublishDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: str = Field(min_length=1)
    rationale: str | None = None


@router.post("/sessions", status_code=201)
async def create_session(
    body: CreateSessionRequest,
    _auth: AuthContext = Depends(require_permission("committee:*")),
    service: CommitteeService = Depends(get_committee_service),
) -> dict[str, Any]:
    session = await service.create_session(
        thesis_ids=body.thesis_ids,
        members=body.members,
        scheduled_at=body.scheduled_at,
        agenda=body.agenda,
        actor_id=UUID(_auth.subject) if _auth.subject else None,
    )
    return {"id": str(session.id), "state": session.state, "scheduled_at": session.scheduled_at.isoformat()}


@router.get("/sessions")
async def list_sessions(
    state: str | None = Query(None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    _auth: AuthContext = Depends(require_permission("committee:*")),
    service: CommitteeService = Depends(get_committee_service),
) -> dict[str, Any]:
    sessions, total = await service.list_sessions(state=state, limit=limit, offset=offset)
    return {
        "items": [
            {
                "id": str(s.id),
                "state": s.state,
                "scheduled_at": s.scheduled_at.isoformat() if s.scheduled_at else None,
                "total_members": s.total_members,
                "present_members": s.present_members,
                "created_at": s.created_at.isoformat() if s.created_at else None,
            }
            for s in sessions
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/sessions/{session_id}")
async def get_session(
    session_id: UUID,
    _auth: AuthContext = Depends(require_permission("committee:*")),
    service: CommitteeService = Depends(get_committee_service),
) -> dict[str, Any]:
    try:
        return await service.get_session(session_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/sessions/{session_id}/convene")
async def convene_session(
    session_id: UUID,
    _auth: AuthContext = Depends(require_permission("committee:*")),
    service: CommitteeService = Depends(get_committee_service),
) -> dict[str, Any]:
    try:
        session = await service.convene_session(
            session_id=session_id,
            actor_id=UUID(_auth.subject) if _auth.subject else None,
        )
    except (LookupError, InvalidTransitionError) as exc:
        raise HTTPException(status_code=404 if isinstance(exc, LookupError) else 409, detail=str(exc)) from exc
    return {"id": str(session.id), "state": session.state}


@router.post("/sessions/{session_id}/vote")
async def cast_vote(
    session_id: UUID,
    body: CastVoteRequest,
    _auth: AuthContext = Depends(require_permission("committee:*")),
    service: CommitteeService = Depends(get_committee_service),
) -> dict[str, Any]:
    try:
        vote = await service.cast_vote(
            session_id=session_id,
            member_id=body.member_id,
            proposal_id=body.proposal_id,
            vote=body.vote,
            justification=body.justification,
            actor_id=UUID(_auth.subject) if _auth.subject else None,
        )
    except (LookupError, InvalidTransitionError) as exc:
        raise HTTPException(status_code=404 if isinstance(exc, LookupError) else 409, detail=str(exc)) from exc
    except DuplicateVoteError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"id": str(vote.id), "vote": vote.vote, "proposal_id": vote.proposal_id}


@router.post("/sessions/{session_id}/finalize")
async def finalize_voting(
    session_id: UUID,
    _auth: AuthContext = Depends(require_permission("committee:*")),
    service: CommitteeService = Depends(get_committee_service),
) -> dict[str, Any]:
    try:
        session = await service.finalize_voting(
            session_id=session_id,
            actor_id=UUID(_auth.subject) if _auth.subject else None,
        )
    except (LookupError, InvalidTransitionError, MajorityNotReachedError) as exc:
        status = 404 if isinstance(exc, LookupError) else 409
        raise HTTPException(status_code=status, detail=str(exc)) from exc
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
    _auth: AuthContext = Depends(require_permission("committee:*")),
    service: CommitteeService = Depends(get_committee_service),
) -> dict[str, Any]:
    try:
        session = await service.publish_decision(
            session_id=session_id,
            decision=body.decision,
            rationale=body.rationale,
            actor_id=UUID(_auth.subject) if _auth.subject else None,
        )
    except (LookupError, InvalidTransitionError) as exc:
        raise HTTPException(status_code=404 if isinstance(exc, LookupError) else 409, detail=str(exc)) from exc
    return {
        "id": str(session.id),
        "state": session.state,
        "decision": session.decision,
        "published_at": session.published_at.isoformat() if session.published_at else None,
    }


@router.get("/sessions/pending")
async def get_pending(
    _auth: AuthContext = Depends(require_permission("committee:*")),
    service: CommitteeService = Depends(get_committee_service),
) -> list[dict[str, Any]]:
    return await service.get_pending_sessions()
