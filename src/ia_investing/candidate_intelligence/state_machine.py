from __future__ import annotations

from .enums import CandidateStatus


_ALLOWED_TRANSITIONS: dict[CandidateStatus, frozenset[CandidateStatus]] = {
    CandidateStatus.SUGGESTED: frozenset(
        {
            CandidateStatus.IDENTITY_RESOLUTION,
            CandidateStatus.REJECTED,
            CandidateStatus.CANCELLED,
        }
    ),
    CandidateStatus.IDENTITY_RESOLUTION: frozenset(
        {
            CandidateStatus.SOURCE_DISCOVERY,
            CandidateStatus.AWAITING_USER_INPUT,
            CandidateStatus.REJECTED,
            CandidateStatus.CANCELLED,
        }
    ),
    CandidateStatus.SOURCE_DISCOVERY: frozenset(
        {
            CandidateStatus.SOURCE_VALIDATION,
            CandidateStatus.AWAITING_USER_INPUT,
            CandidateStatus.REJECTED,
            CandidateStatus.CANCELLED,
        }
    ),
    CandidateStatus.AWAITING_USER_INPUT: frozenset(
        {
            CandidateStatus.SOURCE_DISCOVERY,
            CandidateStatus.SOURCE_VALIDATION,
            CandidateStatus.REJECTED,
            CandidateStatus.CANCELLED,
        }
    ),
    CandidateStatus.SOURCE_VALIDATION: frozenset(
        {
            CandidateStatus.DOCUMENT_COLLECTION,
            CandidateStatus.AWAITING_USER_INPUT,
            CandidateStatus.REJECTED,
            CandidateStatus.CANCELLED,
        }
    ),
    CandidateStatus.DOCUMENT_COLLECTION: frozenset(
        {
            CandidateStatus.DATA_QUALITY,
            CandidateStatus.AWAITING_USER_INPUT,
            CandidateStatus.REJECTED,
            CandidateStatus.CANCELLED,
        }
    ),
    CandidateStatus.DATA_QUALITY: frozenset(
        {
            CandidateStatus.FUNDAMENTAL_ANALYSIS,
            CandidateStatus.AWAITING_USER_INPUT,
            CandidateStatus.REJECTED,
            CandidateStatus.CANCELLED,
        }
    ),
    CandidateStatus.FUNDAMENTAL_ANALYSIS: frozenset(
        {
            CandidateStatus.RISK_ANALYSIS,
            CandidateStatus.AWAITING_USER_INPUT,
            CandidateStatus.WATCHLIST,
            CandidateStatus.REJECTED,
            CandidateStatus.CANCELLED,
        }
    ),
    CandidateStatus.RISK_ANALYSIS: frozenset(
        {
            CandidateStatus.COMMITTEE_REVIEW,
            CandidateStatus.AWAITING_USER_INPUT,
            CandidateStatus.WATCHLIST,
            CandidateStatus.REJECTED,
            CandidateStatus.CANCELLED,
        }
    ),
    CandidateStatus.COMMITTEE_REVIEW: frozenset(
        {
            CandidateStatus.APPROVED,
            CandidateStatus.REJECTED,
            CandidateStatus.WATCHLIST,
            CandidateStatus.AWAITING_USER_INPUT,
            CandidateStatus.CANCELLED,
        }
    ),
    CandidateStatus.WATCHLIST: frozenset(
        {
            CandidateStatus.SOURCE_DISCOVERY,
            CandidateStatus.FUNDAMENTAL_ANALYSIS,
            CandidateStatus.RISK_ANALYSIS,
            CandidateStatus.COMMITTEE_REVIEW,
            CandidateStatus.REJECTED,
            CandidateStatus.CANCELLED,
        }
    ),
    CandidateStatus.APPROVED: frozenset(
        {
            CandidateStatus.WATCHLIST,
            CandidateStatus.REJECTED,
            CandidateStatus.CANCELLED,
        }
    ),
    CandidateStatus.REJECTED: frozenset(
        {
            CandidateStatus.IDENTITY_RESOLUTION,
            CandidateStatus.SOURCE_DISCOVERY,
            CandidateStatus.CANCELLED,
        }
    ),
    CandidateStatus.CANCELLED: frozenset(),
}


def can_transition(current: CandidateStatus, target: CandidateStatus) -> bool:
    return target in _ALLOWED_TRANSITIONS[current]


def require_transition(current: CandidateStatus, target: CandidateStatus) -> None:
    if not can_transition(current, target):
        raise ValueError(f"invalid candidate transition: {current.value} -> {target.value}")
