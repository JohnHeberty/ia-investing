from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.investment_candidates import (
    CandidateAnalysisRunRecord,
    CandidateEventRecord,
    CandidateGapRecord,
    CandidateSourceRecord,
    ExplorationRunRecord,
    ExplorationSuggestionRecord,
    InvestmentCandidateRecord,
)
from database.models.research import DomainOutboxEvent
from ia_investing.candidate_intelligence.contracts import (
    CandidateCreateRequest,
    CandidateReanalysisRequest,
    CandidateSourceCreateRequest,
    ExplorationCreateRequest,
)
from ia_investing.candidate_intelligence.enums import CandidateStatus
from ia_investing.candidate_intelligence.models import normalize_ticker, normalize_url
from ia_investing.candidate_intelligence.readiness import DEFAULT_SOURCE_REQUIREMENTS


def utcnow() -> datetime:
    return datetime.now(UTC)


def _request_hash(payload: dict[str, object]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(encoded).hexdigest()


def _url_hash(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()


class CandidateIdempotencyConflictError(RuntimeError):
    pass


class CandidateConcurrencyError(RuntimeError):
    pass


class CandidateDuplicateError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class CandidateDetail:
    candidate: InvestmentCandidateRecord
    sources: tuple[CandidateSourceRecord, ...]
    gaps: tuple[CandidateGapRecord, ...]
    runs: tuple[CandidateAnalysisRunRecord, ...]
    events: tuple[CandidateEventRecord, ...]


@dataclass(frozen=True, slots=True)
class ExplorationDetail:
    run: ExplorationRunRecord
    suggestions: tuple[ExplorationSuggestionRecord, ...]


class InvestmentCandidateApplicationService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def _require(permissions: frozenset[str], *allowed: str) -> None:
        if not any(permission in permissions for permission in allowed):
            raise PermissionError(f"permission required: one of {', '.join(allowed)}")

    async def create_manual(
        self,
        *,
        organization_id: UUID,
        actor_id: str,
        permissions: frozenset[str],
        request: CandidateCreateRequest,
        data_as_of: datetime,
        idempotency_key: str,
        correlation_id: UUID,
    ) -> tuple[InvestmentCandidateRecord, CandidateAnalysisRunRecord, bool]:
        self._require(permissions, "candidates:create", "research_cases:create")
        payload = request.model_dump(mode="json") | {"data_as_of": data_as_of.isoformat()}
        digest = _request_hash(payload)
        existing = await self.session.scalar(
            sa.select(InvestmentCandidateRecord).where(
                InvestmentCandidateRecord.organization_id == organization_id,
                InvestmentCandidateRecord.idempotency_key == idempotency_key,
            )
        )
        if existing is not None:
            if existing.request_hash != digest:
                raise CandidateIdempotencyConflictError(
                    "idempotency key was already used with a different candidate request"
                )
            run = await self.session.scalar(
                sa.select(CandidateAnalysisRunRecord)
                .where(CandidateAnalysisRunRecord.candidate_id == existing.id)
                .order_by(CandidateAnalysisRunRecord.run_number.asc())
                .limit(1)
            )
            assert run is not None
            return existing, run, False

        ticker = normalize_ticker(request.ticker)
        duplicate = await self.session.scalar(
            sa.select(InvestmentCandidateRecord).where(
                InvestmentCandidateRecord.organization_id == organization_id,
                InvestmentCandidateRecord.exchange == request.exchange.upper(),
                InvestmentCandidateRecord.ticker == ticker,
                InvestmentCandidateRecord.status != CandidateStatus.CANCELLED.value,
            )
        )
        if duplicate is not None:
            raise CandidateDuplicateError(f"active candidate already exists for {request.exchange.upper()}:{ticker}")

        now = utcnow()
        candidate = InvestmentCandidateRecord(
            id=uuid4(),
            organization_id=organization_id,
            origin="manual",
            status=CandidateStatus.IDENTITY_RESOLUTION.value,
            ticker=ticker,
            exchange=request.exchange.upper(),
            legal_name=request.legal_name,
            trading_name=request.trading_name,
            cnpj=request.cnpj,
            cvm_code=request.cvm_code,
            rationale=request.rationale,
            approved_portfolio_eligible=False,
            created_by=actor_id,
            idempotency_key=idempotency_key,
            request_hash=digest,
            created_at=now,
            updated_at=now,
            lock_version=1,
        )
        self.session.add(candidate)
        await self.session.flush()

        for requirement in DEFAULT_SOURCE_REQUIREMENTS:
            self.session.add(
                CandidateGapRecord(
                    id=uuid4(),
                    candidate_id=candidate.id,
                    code=requirement.code,
                    title=f"Fonte ausente: {requirement.label}",
                    description=(
                        "O processo automático ainda precisa localizar e verificar esta fonte. "
                        "Quando a descoberta falhar, o usuário poderá informar a URL e reprocessar."
                    ),
                    source_kind=requirement.kind.value,
                    level=requirement.level.value,
                    status="open",
                    requested_user_action=f"Informe a URL oficial de {requirement.label.lower()}.",
                    created_at=now,
                )
            )
        run = CandidateAnalysisRunRecord(
            id=uuid4(),
            candidate_id=candidate.id,
            run_number=1,
            trigger="initial",
            status="queued",
            requested_by=actor_id,
            requested_at=now,
            data_as_of=data_as_of,
            blocker_codes=[],
            agent_run_ids=[],
        )
        self.session.add(run)
        self._add_event(
            candidate,
            "investment_candidate.created",
            actor_id,
            {"analysis_run_id": str(run.id), "ticker": ticker, "origin": "manual"},
        )
        self._add_outbox(
            candidate,
            "candidate.analysis.requested",
            {
                "candidate_id": str(candidate.id),
                "organization_id": str(candidate.organization_id),
                "analysis_run_id": str(run.id),
                "data_as_of": data_as_of.isoformat(),
                "allow_incomplete": False,
                "correlation_id": str(correlation_id),
            },
        )
        await self.session.commit()
        return candidate, run, True

    async def list_candidates(
        self,
        *,
        organization_id: UUID,
        permissions: frozenset[str],
        status: str | None,
        after: UUID | None,
        limit: int,
    ) -> list[InvestmentCandidateRecord]:
        self._require(permissions, "candidates:read", "research:read", "research_cases:read")
        stmt = sa.select(InvestmentCandidateRecord).where(InvestmentCandidateRecord.organization_id == organization_id)
        if status:
            stmt = stmt.where(InvestmentCandidateRecord.status == status)
        if after:
            anchor = await self.session.scalar(
                sa.select(InvestmentCandidateRecord).where(
                    InvestmentCandidateRecord.id == after,
                    InvestmentCandidateRecord.organization_id == organization_id,
                )
            )
            if anchor is not None:
                stmt = stmt.where(
                    sa.or_(
                        InvestmentCandidateRecord.created_at < anchor.created_at,
                        sa.and_(
                            InvestmentCandidateRecord.created_at == anchor.created_at,
                            InvestmentCandidateRecord.id < anchor.id,
                        ),
                    )
                )
        return list(
            (
                await self.session.scalars(
                    stmt.order_by(
                        InvestmentCandidateRecord.created_at.desc(),
                        InvestmentCandidateRecord.id.desc(),
                    ).limit(limit + 1)
                )
            ).all()
        )

    async def get_detail(
        self,
        *,
        candidate_id: UUID,
        organization_id: UUID,
        permissions: frozenset[str],
    ) -> CandidateDetail | None:
        self._require(permissions, "candidates:read", "research:read", "research_cases:read")
        candidate = await self.session.scalar(
            sa.select(InvestmentCandidateRecord).where(
                InvestmentCandidateRecord.id == candidate_id,
                InvestmentCandidateRecord.organization_id == organization_id,
            )
        )
        if candidate is None:
            return None
        sources = tuple(
            (
                await self.session.scalars(
                    sa.select(CandidateSourceRecord)
                    .where(CandidateSourceRecord.candidate_id == candidate_id)
                    .order_by(CandidateSourceRecord.kind, CandidateSourceRecord.created_at)
                )
            ).all()
        )
        gaps = tuple(
            (
                await self.session.scalars(
                    sa.select(CandidateGapRecord)
                    .where(CandidateGapRecord.candidate_id == candidate_id)
                    .order_by(CandidateGapRecord.status, CandidateGapRecord.level, CandidateGapRecord.created_at)
                )
            ).all()
        )
        runs = tuple(
            (
                await self.session.scalars(
                    sa.select(CandidateAnalysisRunRecord)
                    .where(CandidateAnalysisRunRecord.candidate_id == candidate_id)
                    .order_by(CandidateAnalysisRunRecord.run_number.desc())
                )
            ).all()
        )
        events = tuple(
            (
                await self.session.scalars(
                    sa.select(CandidateEventRecord)
                    .where(CandidateEventRecord.candidate_id == candidate_id)
                    .order_by(CandidateEventRecord.occurred_at.desc())
                    .limit(250)
                )
            ).all()
        )
        return CandidateDetail(candidate, sources, gaps, runs, events)

    async def add_source(
        self,
        *,
        candidate_id: UUID,
        organization_id: UUID,
        actor_id: str,
        permissions: frozenset[str],
        request: CandidateSourceCreateRequest,
        expected_version: int,
        correlation_id: UUID,
    ) -> CandidateSourceRecord:
        self._require(permissions, "candidates:update", "research_cases:update")
        candidate = await self._locked_candidate(candidate_id, organization_id, expected_version)
        if candidate.status == CandidateStatus.CANCELLED.value:
            raise ValueError("cancelled candidates cannot receive new sources")
        url = normalize_url(str(request.url))
        existing = await self.session.scalar(
            sa.select(CandidateSourceRecord).where(
                CandidateSourceRecord.candidate_id == candidate.id,
                CandidateSourceRecord.kind == request.kind.value,
                CandidateSourceRecord.normalized_url_hash == _url_hash(url),
            )
        )
        if existing is not None:
            return existing
        now = utcnow()
        source = CandidateSourceRecord(
            id=uuid4(),
            candidate_id=candidate.id,
            kind=request.kind.value,
            url=url,
            normalized_url_hash=_url_hash(url),
            status="discovered",
            verification_method="user_confirmed",
            confidence=Decimal("0.7000"),
            official=False,
            discovered_by=actor_id,
            notes=request.notes,
            evidence={"provided_by_user": True, "correlation_id": str(correlation_id)},
            created_at=now,
            verified_at=None,
            last_checked_at=None,
        )
        self.session.add(source)
        candidate.updated_at = now
        candidate.lock_version += 1
        self._add_event(
            candidate,
            "investment_candidate.source_supplied",
            actor_id,
            {"source_id": str(source.id), "kind": source.kind, "url": source.url},
        )
        self._add_outbox(
            candidate,
            "candidate.source.validation.requested",
            {
                "candidate_id": str(candidate.id),
                "organization_id": str(candidate.organization_id),
                "source_id": str(source.id),
                "correlation_id": str(correlation_id),
            },
        )
        await self.session.commit()
        return source

    async def resolve_gap(
        self,
        *,
        candidate_id: UUID,
        gap_id: UUID,
        organization_id: UUID,
        actor_id: str,
        permissions: frozenset[str],
        notes: str,
        expected_version: int,
    ) -> CandidateGapRecord:
        self._require(permissions, "candidates:update", "research_cases:update")
        candidate = await self._locked_candidate(candidate_id, organization_id, expected_version)
        gap = await self.session.scalar(
            sa.select(CandidateGapRecord).where(
                CandidateGapRecord.id == gap_id,
                CandidateGapRecord.candidate_id == candidate.id,
            )
        )
        if gap is None:
            raise LookupError("candidate gap not found")
        if gap.status != "open":
            raise ValueError("only open gaps can be resolved")
        if gap.level == "blocking":
            verified = await self.session.scalar(
                sa.select(sa.func.count(CandidateSourceRecord.id)).where(
                    CandidateSourceRecord.candidate_id == candidate.id,
                    CandidateSourceRecord.kind == gap.source_kind,
                    CandidateSourceRecord.status == "verified",
                    CandidateSourceRecord.official.is_(True),
                )
            )
            if not verified:
                raise ValueError("blocking source gap can only be resolved after the supplied URL is verified")
        now = utcnow()
        gap.status = "resolved"
        gap.resolved_at = now
        gap.resolved_by = actor_id
        gap.resolution_notes = notes
        candidate.updated_at = now
        candidate.lock_version += 1
        self._add_event(
            candidate,
            "investment_candidate.gap_resolved",
            actor_id,
            {"gap_id": str(gap.id), "code": gap.code},
        )
        await self.session.commit()
        return gap

    async def request_reanalysis(
        self,
        *,
        candidate_id: UUID,
        organization_id: UUID,
        actor_id: str,
        permissions: frozenset[str],
        request: CandidateReanalysisRequest,
        expected_version: int,
        correlation_id: UUID,
    ) -> CandidateAnalysisRunRecord:
        self._require(permissions, "candidates:reanalyze", "agents:run")
        candidate = await self._locked_candidate(candidate_id, organization_id, expected_version)
        allowed_statuses = {
            CandidateStatus.IDENTITY_RESOLUTION.value,
            CandidateStatus.SOURCE_DISCOVERY.value,
            CandidateStatus.AWAITING_USER_INPUT.value,
            CandidateStatus.SOURCE_VALIDATION.value,
            CandidateStatus.DOCUMENT_COLLECTION.value,
            CandidateStatus.DATA_QUALITY.value,
            CandidateStatus.FUNDAMENTAL_ANALYSIS.value,
            CandidateStatus.RISK_ANALYSIS.value,
            CandidateStatus.COMMITTEE_REVIEW.value,
            CandidateStatus.REJECTED.value,
            CandidateStatus.WATCHLIST.value,
        }
        if candidate.status not in allowed_statuses:
            raise ValueError(f"candidate in status {candidate.status!r} cannot restart onboarding analysis")
        blockers = list(
            (
                await self.session.scalars(
                    sa.select(CandidateGapRecord.code).where(
                        CandidateGapRecord.candidate_id == candidate.id,
                        CandidateGapRecord.status == "open",
                        CandidateGapRecord.level == "blocking",
                    )
                )
            ).all()
        )
        if blockers and not request.allow_incomplete:
            raise ValueError("candidate still has blocking gaps: " + ", ".join(sorted(blockers)))
        max_number = await self.session.scalar(
            sa.select(sa.func.coalesce(sa.func.max(CandidateAnalysisRunRecord.run_number), 0)).where(
                CandidateAnalysisRunRecord.candidate_id == candidate.id
            )
        )
        run = CandidateAnalysisRunRecord(
            id=uuid4(),
            candidate_id=candidate.id,
            run_number=int(max_number or 0) + 1,
            trigger=request.trigger.value,
            status="queued",
            requested_by=actor_id,
            requested_at=utcnow(),
            data_as_of=request.data_as_of,
            blocker_codes=blockers,
            agent_run_ids=[],
        )
        self.session.add(run)
        candidate.status = CandidateStatus.SOURCE_DISCOVERY.value
        candidate.updated_at = utcnow()
        candidate.lock_version += 1
        self._add_event(
            candidate,
            "investment_candidate.reanalysis_requested",
            actor_id,
            {"analysis_run_id": str(run.id), "allow_incomplete": request.allow_incomplete},
        )
        self._add_outbox(
            candidate,
            "candidate.analysis.requested",
            {
                "candidate_id": str(candidate.id),
                "organization_id": str(candidate.organization_id),
                "analysis_run_id": str(run.id),
                "data_as_of": request.data_as_of.isoformat(),
                "allow_incomplete": request.allow_incomplete,
                "correlation_id": str(correlation_id),
            },
        )
        await self.session.commit()
        return run

    async def create_exploration_run(
        self,
        *,
        organization_id: UUID,
        actor_id: str,
        permissions: frozenset[str],
        request: ExplorationCreateRequest,
        correlation_id: UUID,
    ) -> ExplorationRunRecord:
        self._require(permissions, "exploration:create", "agents:run")
        run = ExplorationRunRecord(
            id=uuid4(),
            organization_id=organization_id,
            status="queued",
            strategy_codes=list(request.strategy_codes),
            requested_by=actor_id,
            created_at=utcnow(),
            data_as_of=request.data_as_of,
            minimum_liquidity=request.minimum_liquidity,
            maximum_suggestions=request.maximum_suggestions,
            excluded_instrument_ids=[str(item) for item in request.excluded_instrument_ids],
            universe_size=0,
            eligible_size=0,
        )
        self.session.add(run)
        self.session.add(
            DomainOutboxEvent(
                id=uuid4(),
                aggregate_type="exploration_run",
                aggregate_id=run.id,
                aggregate_version=1,
                event_type="equity.exploration.requested",
                payload={
                    "exploration_run_id": str(run.id),
                    "organization_id": str(organization_id),
                    "data_as_of": request.data_as_of.isoformat(),
                    "correlation_id": str(correlation_id),
                },
                correlation_id=correlation_id,
                idempotency_key=f"equity.exploration.requested:{run.id}:1",
                occurred_at=utcnow(),
            )
        )
        await self.session.commit()
        return run

    async def list_exploration_runs(
        self,
        *,
        organization_id: UUID,
        permissions: frozenset[str],
        status: str | None,
        limit: int,
    ) -> list[ExplorationRunRecord]:
        self._require(permissions, "exploration:read", "candidates:read", "research:read")
        stmt = sa.select(ExplorationRunRecord).where(ExplorationRunRecord.organization_id == organization_id)
        if status:
            stmt = stmt.where(ExplorationRunRecord.status == status)
        return list(
            (
                await self.session.scalars(
                    stmt.order_by(
                        ExplorationRunRecord.created_at.desc(),
                        ExplorationRunRecord.id.desc(),
                    ).limit(limit)
                )
            ).all()
        )

    async def get_exploration_detail(
        self,
        *,
        exploration_run_id: UUID,
        organization_id: UUID,
        permissions: frozenset[str],
    ) -> ExplorationDetail | None:
        self._require(permissions, "exploration:read", "candidates:read", "research:read")
        run = await self.session.scalar(
            sa.select(ExplorationRunRecord).where(
                ExplorationRunRecord.id == exploration_run_id,
                ExplorationRunRecord.organization_id == organization_id,
            )
        )
        if run is None:
            return None
        suggestions = tuple(
            (
                await self.session.scalars(
                    sa.select(ExplorationSuggestionRecord)
                    .where(
                        ExplorationSuggestionRecord.exploration_run_id == run.id,
                        ExplorationSuggestionRecord.organization_id == organization_id,
                    )
                    .order_by(
                        ExplorationSuggestionRecord.quantitative_score.desc(),
                        ExplorationSuggestionRecord.created_at.asc(),
                    )
                )
            ).all()
        )
        return ExplorationDetail(run=run, suggestions=suggestions)

    async def dismiss_suggestion(
        self,
        *,
        suggestion_id: UUID,
        organization_id: UUID,
        actor_id: str,
        permissions: frozenset[str],
        reason: str,
    ) -> ExplorationSuggestionRecord:
        self._require(permissions, "exploration:update", "candidates:update")
        suggestion = await self.session.scalar(
            sa.select(ExplorationSuggestionRecord)
            .where(
                ExplorationSuggestionRecord.id == suggestion_id,
                ExplorationSuggestionRecord.organization_id == organization_id,
            )
            .with_for_update()
        )
        if suggestion is None:
            raise LookupError("exploration suggestion not found")
        now = utcnow()
        if suggestion.expires_at is not None and suggestion.expires_at <= now:
            suggestion.status = "expired"
            await self.session.commit()
            raise ValueError("expired exploration suggestions cannot be dismissed")
        if suggestion.status != "new":
            raise ValueError("only new suggestions can be dismissed")
        suggestion.status = "dismissed"
        suggestion.dismissed_at = now
        suggestion.dismissed_by = actor_id
        suggestion.dismissal_reason = reason.strip()
        await self.session.commit()
        return suggestion

    async def promote_suggestion(
        self,
        *,
        suggestion_id: UUID,
        organization_id: UUID,
        actor_id: str,
        permissions: frozenset[str],
        idempotency_key: str,
        correlation_id: UUID,
    ) -> InvestmentCandidateRecord:
        self._require(permissions, "candidates:create", "exploration:promote")
        suggestion = await self.session.scalar(
            sa.select(ExplorationSuggestionRecord).where(
                ExplorationSuggestionRecord.id == suggestion_id,
                ExplorationSuggestionRecord.organization_id == organization_id,
            )
        )
        if suggestion is None:
            raise LookupError("exploration suggestion not found")
        now = utcnow()
        if suggestion.expires_at is not None and suggestion.expires_at <= now:
            suggestion.status = "expired"
            await self.session.commit()
            raise ValueError("expired exploration suggestions cannot be promoted")
        if suggestion.status == "promoted" and suggestion.promoted_candidate_id:
            existing = await self.session.get(
                InvestmentCandidateRecord,
                suggestion.promoted_candidate_id,
            )
            assert existing is not None
            return existing
        if suggestion.status != "new":
            raise ValueError("only new suggestions can be promoted")
        duplicate = await self.session.scalar(
            sa.select(InvestmentCandidateRecord).where(
                InvestmentCandidateRecord.organization_id == organization_id,
                InvestmentCandidateRecord.exchange == suggestion.exchange,
                InvestmentCandidateRecord.ticker == suggestion.ticker,
                InvestmentCandidateRecord.status != CandidateStatus.CANCELLED.value,
            )
        )
        if duplicate is not None:
            suggestion.status = "duplicate"
            await self.session.commit()
            return duplicate
        candidate = InvestmentCandidateRecord(
            id=uuid4(),
            organization_id=organization_id,
            origin="explorer",
            status=CandidateStatus.SUGGESTED.value,
            ticker=suggestion.ticker,
            exchange=suggestion.exchange,
            issuer_id=suggestion.issuer_id,
            instrument_id=suggestion.instrument_id,
            rationale=suggestion.rationale,
            exploration_suggestion_id=suggestion.id,
            approved_portfolio_eligible=False,
            created_by=actor_id,
            idempotency_key=idempotency_key,
            request_hash=_request_hash({"suggestion_id": str(suggestion.id)}),
            created_at=now,
            updated_at=now,
            lock_version=1,
        )
        self.session.add(candidate)
        await self.session.flush()
        suggestion.status = "promoted"
        suggestion.promoted_candidate_id = candidate.id
        for requirement in DEFAULT_SOURCE_REQUIREMENTS:
            self.session.add(
                CandidateGapRecord(
                    id=uuid4(),
                    candidate_id=candidate.id,
                    code=requirement.code,
                    title=f"Fonte ausente: {requirement.label}",
                    description="A exploração ainda precisa verificar esta fonte antes de promover a pesquisa.",
                    source_kind=requirement.kind.value,
                    level=requirement.level.value,
                    status="open",
                    requested_user_action=f"Informe a URL oficial de {requirement.label.lower()} se a descoberta falhar.",
                    created_at=now,
                )
            )
        analysis_run = CandidateAnalysisRunRecord(
            id=uuid4(),
            candidate_id=candidate.id,
            run_number=1,
            trigger="explorer_refresh",
            status="queued",
            requested_by=actor_id,
            requested_at=now,
            data_as_of=now,
            blocker_codes=[],
            agent_run_ids=[],
        )
        self.session.add(analysis_run)
        for item in suggestion.source_snapshot or []:
            try:
                url = normalize_url(str(item["url"]))
            except (KeyError, ValueError):
                continue
            self.session.add(
                CandidateSourceRecord(
                    id=uuid4(),
                    candidate_id=candidate.id,
                    kind=str(item.get("kind", "company_website")),
                    url=url,
                    normalized_url_hash=_url_hash(url),
                    status=str(item.get("status", "discovered")),
                    verification_method=str(item.get("verification_method", "agent_inference")),
                    confidence=Decimal(str(item.get("confidence", "0.5000"))),
                    official=False,
                    discovered_by="agent:autonomous-equity-explorer",
                    evidence=dict(item.get("evidence", {})),
                    created_at=now,
                )
            )
        self._add_event(
            candidate,
            "investment_candidate.promoted_from_explorer",
            actor_id,
            {"suggestion_id": str(suggestion.id)},
        )
        self._add_outbox(
            candidate,
            "candidate.analysis.requested",
            {
                "candidate_id": str(candidate.id),
                "organization_id": str(candidate.organization_id),
                "analysis_run_id": str(analysis_run.id),
                "data_as_of": now.isoformat(),
                "allow_incomplete": False,
                "correlation_id": str(correlation_id),
            },
        )
        await self.session.commit()
        return candidate

    async def _locked_candidate(
        self,
        candidate_id: UUID,
        organization_id: UUID,
        expected_version: int,
    ) -> InvestmentCandidateRecord:
        candidate = await self.session.scalar(
            sa.select(InvestmentCandidateRecord)
            .where(
                InvestmentCandidateRecord.id == candidate_id,
                InvestmentCandidateRecord.organization_id == organization_id,
            )
            .with_for_update()
        )
        if candidate is None:
            raise LookupError("investment candidate not found")
        if candidate.lock_version != expected_version:
            raise CandidateConcurrencyError(
                f"expected candidate version {expected_version}, found {candidate.lock_version}"
            )
        return candidate

    def _add_event(
        self,
        candidate: InvestmentCandidateRecord,
        event_type: str,
        actor_id: str,
        payload: dict[str, object],
    ) -> None:
        self.session.add(
            CandidateEventRecord(
                id=uuid4(),
                candidate_id=candidate.id,
                organization_id=candidate.organization_id,
                event_type=event_type,
                actor_type="human" if not actor_id.startswith("agent:") else "agent",
                actor_id=actor_id,
                occurred_at=utcnow(),
                aggregate_version=candidate.lock_version,
                payload=payload,
            )
        )

    def _add_outbox(
        self,
        candidate: InvestmentCandidateRecord,
        event_type: str,
        payload: dict[str, object],
    ) -> None:
        self.session.add(
            DomainOutboxEvent(
                id=uuid4(),
                aggregate_type="investment_candidate",
                aggregate_id=candidate.id,
                aggregate_version=candidate.lock_version,
                event_type=event_type,
                payload=payload,
                correlation_id=UUID(str(payload.get("correlation_id", uuid4()))),
                idempotency_key=f"{event_type}:{candidate.id}:{candidate.lock_version}",
                occurred_at=utcnow(),
            )
        )
