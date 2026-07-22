from __future__ import annotations

from enum import StrEnum


class CandidateOrigin(StrEnum):
    MANUAL = "manual"
    EXPLORER = "explorer"


class CandidateStatus(StrEnum):
    SUGGESTED = "suggested"
    IDENTITY_RESOLUTION = "identity_resolution"
    SOURCE_DISCOVERY = "source_discovery"
    AWAITING_USER_INPUT = "awaiting_user_input"
    SOURCE_VALIDATION = "source_validation"
    DOCUMENT_COLLECTION = "document_collection"
    DATA_QUALITY = "data_quality"
    FUNDAMENTAL_ANALYSIS = "fundamental_analysis"
    RISK_ANALYSIS = "risk_analysis"
    COMMITTEE_REVIEW = "committee_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    WATCHLIST = "watchlist"
    CANCELLED = "cancelled"


class SourceKind(StrEnum):
    COMPANY_WEBSITE = "company_website"
    INVESTOR_RELATIONS = "investor_relations"
    FINANCIAL_REPORTS = "financial_reports"
    CVM_PROFILE = "cvm_profile"
    CVM_FILINGS = "cvm_filings"
    B3_LISTING = "b3_listing"
    GOVERNANCE = "governance"
    NEWSROOM = "newsroom"
    REGULATOR = "regulator"
    MARKET_DATA = "market_data"


class SourceStatus(StrEnum):
    DISCOVERED = "discovered"
    VERIFIED = "verified"
    REJECTED = "rejected"
    STALE = "stale"
    UNREACHABLE = "unreachable"


class VerificationMethod(StrEnum):
    OFFICIAL_REGISTRY_LINK = "official_registry_link"
    CROSS_SOURCE_MATCH = "cross_source_match"
    DOMAIN_OWNERSHIP = "domain_ownership"
    DOCUMENT_IDENTITY_MATCH = "document_identity_match"
    USER_CONFIRMED = "user_confirmed"
    AGENT_INFERENCE = "agent_inference"


class RequirementLevel(StrEnum):
    BLOCKING = "blocking"
    REQUIRED = "required"
    OPTIONAL = "optional"


class GapStatus(StrEnum):
    OPEN = "open"
    RESOLVED = "resolved"
    WAIVED = "waived"


class AnalysisTrigger(StrEnum):
    INITIAL = "initial"
    USER_COMPLETION = "user_completion"
    MANUAL_RETRY = "manual_retry"
    EXPLORER_REFRESH = "explorer_refresh"
    PERIODIC_REFRESH = "periodic_refresh"


class AnalysisRunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    BLOCKED = "blocked"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class CandidateDecision(StrEnum):
    APPROVE = "approve"
    REJECT = "reject"
    PENDING = "pending"
    WATCHLIST = "watchlist"


class ExplorationRunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    PARTIAL = "partial"
    FAILED = "failed"
    CANCELLED = "cancelled"


class SuggestionStatus(StrEnum):
    NEW = "new"
    PROMOTED = "promoted"
    DISMISSED = "dismissed"
    DUPLICATE = "duplicate"
    EXPIRED = "expired"
