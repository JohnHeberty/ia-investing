from __future__ import annotations

import contextlib
import dataclasses
import hashlib
import logging
import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from connectors.base import HttpClient
from database.models.catalog import Issuer
from database.models.committee import CommitteeDecision, CommitteeSession, CommitteeVote
from database.models.instrument_master import Instrument, Listing
from database.models.investment_candidates import (
    CandidateEventRecord,
    CandidateGapRecord,
    CandidateSourceRecord,
    ExplorationSuggestionRecord,
    InvestmentCandidateRecord,
)
from database.models.market_data import MarketBar, MarketQuote
from ia_investing.ai._runner import AgentResult
from ia_investing.ai.execution import AgentExecutionService
from ia_investing.ai.gateway import create_gateway_provider
from ia_investing.ai.provider import AgentProvider, MockProvider
from ia_investing.application.agent_runtime import AgentRuntimeService
from ia_investing.application.candidate_repository import CandidateRepository
from ia_investing.application.instruments import InstrumentMasterService
from ia_investing.data.raw_zone import ImmutableObjectStore
from ia_investing.integrations.connectors.b3_resolver import B3Resolver
from ia_investing.integrations.connectors.cvm_resolver import CVMResolver
from ia_investing.orchestration.activities.candidate_intelligence import (
    CandidateCheckpoint,
    CandidateSourceValidationInput,
    CandidateSourceValidationResult,
    CandidateWorkflowInput,
    CandidateWorkflowResult,
    ExplorationFindings,
    ExplorationShortlist,
    ExplorationWorkflowInput,
    ExplorationWorkflowResult,
    SourceDiscoveryCheckpoint,
)
from ia_investing.orchestration.activities.gap_catalog import CANONICAL_GAP_CODES
from ia_investing.platform.database.runtime import DatabaseRuntime
from ia_investing.platform.http.safe_client import EgressPolicy, SafeHttpClient
from ia_investing.settings import get_settings

logger = logging.getLogger(__name__)


def _extract_text_from_html(raw: bytes) -> str:
    """Best-effort HTML-to-text extraction without external dependencies."""
    import re

    text = raw.decode("utf-8", errors="replace")
    text = re.sub(r"<script[^>]*>.*?</script>", " ", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<style[^>]*>.*?</style>", " ", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&[a-zA-Z]+;", " ", text)
    text = re.sub(r"&#\d+;", " ", text)
    return text.lower()


def _provider_for_runner() -> AgentProvider:
    settings = get_settings()
    if settings.ai.provider == "mock":
        return MockProvider()
    if settings.ai.provider in ("gateway", "litellm"):
        gw = settings.ai.gateway
        return create_gateway_provider(
            provider=gw.provider,
            api_key=gw.api_key.get_secret_value(),
            default_model=gw.model,
            base_url=gw.base_url,
            timeout=gw.timeout,
            max_retries=gw.max_retries,
            rpm=gw.rpm,
            tpm=gw.tpm,
        )
    return MockProvider()


async def _execute_governed_agent(
    db: DatabaseRuntime,
    capability: str,
    organization_id: uuid.UUID,
    input_data: dict[str, Any],
    data_as_of: datetime,
    knowledge_cutoff: datetime,
    actor_id: str = "candidate_runtime",
    agent_run_id: str | None = None,
) -> AgentResult:
    """Execute an agent through the governed runtime path (AgentRuntimeService + AgentExecutionService)."""
    async with db.session() as session:
        service = AgentRuntimeService(session)
        run = await service.create_run(
            organization_id=organization_id,
            capability=capability,
            case_id=None,
            input_payload=input_data,
            data_as_of=data_as_of,
            knowledge_cutoff=knowledge_cutoff,
            actor_id=actor_id,
            permissions=frozenset({"agent_runs:create"}),
            workflow_id=f"candidate_{capability}",
            idempotency_key=uuid.uuid4().hex,
        )
        run_id = run.id
        await session.commit()

    async with db.session() as session:
        provider = _provider_for_runner()
        metadata = {
            "org_id": str(organization_id),
            "workflow_id": f"candidate_{capability}",
        }
        if agent_run_id:
            metadata["agent_run_id"] = agent_run_id
        executed = await AgentExecutionService(session, provider).execute(run_id, metadata=metadata)
        await session.commit()

    if executed.status == "succeeded":
        return AgentResult(
            agent_name=capability,
            output_data=executed.output_payload,
            model_used=str(executed.prompt_tokens) + "/" + str(executed.completion_tokens),
            tokens_prompt=executed.prompt_tokens or 0,
            tokens_completion=executed.completion_tokens or 0,
            cost_usd=float(executed.cost_usd) if executed.cost_usd else 0.0,
            duration_ms=executed.duration_ms or 0.0,
            status="completed",
        )
    return AgentResult(
        agent_name=capability,
        output_data=None,
        model_used="",
        tokens_prompt=0,
        tokens_completion=0,
        cost_usd=0.0,
        duration_ms=0.0,
        status="failed",
        error_message=executed.error_detail or executed.error_code or "unknown error",
    )


_STAGE_NAMES = (
    "identity_resolution",
    "source_discovery",
    "source_validation",
    "document_collection",
    "data_quality",
    "fundamental_analysis",
    "risk_analysis",
    "committee_review",
)


def _stage_blocked(
    command: CandidateWorkflowInput,
    stage: str,
    reason: str,
    *,
    blocker_codes: tuple[str, ...] = (),
) -> CandidateCheckpoint:
    return CandidateCheckpoint(
        candidate_id=command.candidate_id,
        stage=stage,
        blocked=True,
        decision="pending",
        reason=reason,
        blocker_codes=blocker_codes,
    )


def _stage_passed(
    command: CandidateWorkflowInput,
    stage: str,
    *,
    reason: str = "ok",
    payload: dict[str, object] | None = None,
) -> CandidateCheckpoint:
    return CandidateCheckpoint(
        candidate_id=command.candidate_id,
        stage=stage,
        blocked=False,
        decision="continue",
        reason=reason,
        payload=payload,
    )


def _now() -> datetime:
    return datetime.now(UTC)


_DECISION_FINAL = frozenset({"approve", "approve_with_conditions", "reject", "deferred", "defer"})
_DECISION_APPROVED = frozenset({"approve", "approve_with_conditions"})


@dataclasses.dataclass(frozen=True, slots=True)
class _ResolvedDecision:
    run_decision: str
    candidate_status: str | None
    final_decision: str | None
    final_decision_reason: str | None
    approved_eligible: bool | None


def _resolve_run_decision(
    checkpoint: CandidateCheckpoint,
    payload: dict[str, Any],
) -> _ResolvedDecision:
    cp_decision = str(checkpoint.decision or "").lower()
    pl_decision = str(payload.get("decision", "")).lower()

    if checkpoint.blocked:
        return _ResolvedDecision(
            run_decision=cp_decision or "blocked",
            candidate_status="blocked",
            final_decision=None,
            final_decision_reason=checkpoint.reason,
            approved_eligible=None,
        )

    for decision in (cp_decision, pl_decision):
        if decision in _DECISION_FINAL:
            approved = decision in _DECISION_APPROVED
            return _ResolvedDecision(
                run_decision=decision,
                candidate_status="approved" if approved else "rejected",
                final_decision=decision,
                final_decision_reason=checkpoint.reason,
                approved_eligible=approved,
            )

    return _ResolvedDecision(
        run_decision=cp_decision or "completed",
        candidate_status=None,
        final_decision=None,
        final_decision_reason=checkpoint.reason,
        approved_eligible=None,
    )


class ProductionCandidateRuntime:
    def __init__(
        self,
        db: DatabaseRuntime,
        http_client: SafeHttpClient | None = None,
        *,
        agent_runtime_service: object | None = None,
        cvm_resolver: CVMResolver | None = None,
        b3_resolver: B3Resolver | None = None,
        object_store: ImmutableObjectStore | None = None,
    ) -> None:
        self._db = db
        self._http = http_client or SafeHttpClient(policy=EgressPolicy())
        self._client = HttpClient(timeout=60.0)
        self._agent_runtime_service = agent_runtime_service
        self._cvm = cvm_resolver or CVMResolver(self._http, self._client)
        self._b3 = b3_resolver or B3Resolver(db)
        self._object_store = object_store

    # ------------------------------------------------------------------
    # Phase 1 — Identity Resolution
    # ------------------------------------------------------------------

    async def resolve_candidate_identity(self, command: CandidateWorkflowInput) -> CandidateCheckpoint:
        async with self._db.session() as session:
            repo = CandidateRepository(session, command.organization_id)
            candidate = await repo.get_candidate(command.candidate_id)
            if candidate is None:
                return _stage_blocked(
                    command,
                    "identity_resolution",
                    "Candidate record not found.",
                    blocker_codes=("candidate_not_found",),
                )

            if candidate.instrument_id is not None and candidate.issuer_id is not None:
                return _stage_passed(
                    command,
                    "identity_resolution",
                    reason="Identity already resolved in a prior run.",
                )

            resolver = InstrumentMasterService(session)
            as_of = command.data_as_of.date()
            result = await resolver.resolve(candidate.ticker, as_of)

            if result is None:
                return _stage_blocked(
                    command,
                    "identity_resolution",
                    f"Instrument/issuer not found for ticker {candidate.ticker}.",
                    blocker_codes=("ticker_not_found",),
                )

            candidate.instrument_id = result.instrument_id
            candidate.issuer_id = result.issuer_id
            candidate.legal_name = result.issuer_name or candidate.legal_name
            session.add(
                CandidateEventRecord(
                    candidate_id=candidate.id,
                    organization_id=candidate.organization_id,
                    event_type="identity_resolved",
                    actor_type="system",
                    actor_id="candidate_runtime",
                    occurred_at=_now(),
                    aggregate_version=candidate.lock_version,
                    payload={
                        "instrument_id": str(result.instrument_id) if result.instrument_id else "",
                        "issuer_id": str(result.issuer_id),
                        "ticker": result.ticker or "",
                        "issuer_name": result.issuer_name,
                    },
                )
            )
            candidate.lock_version += 1
            await session.commit()

            return _stage_passed(
                command,
                "identity_resolution",
                reason=f"Resolved {candidate.ticker} → instrument {result.instrument_id} issuer {result.issuer_id}",
                payload={
                    "instrument_id": str(result.instrument_id) if result.instrument_id else "",
                    "issuer_id": str(result.issuer_id),
                    "ticker": result.ticker or candidate.ticker,
                    "issuer_name": result.issuer_name,
                },
            )

    # ------------------------------------------------------------------
    # Phase 2 — Source Discovery (deterministic)
    # ------------------------------------------------------------------

    async def discover_candidate_sources(self, command: CandidateWorkflowInput) -> SourceDiscoveryCheckpoint:
        async with self._db.session() as session:
            repo = CandidateRepository(session, command.organization_id)
            candidate = await repo.get_candidate(command.candidate_id)
            if candidate is None:
                return SourceDiscoveryCheckpoint(
                    command=command,
                    output={
                        "stage": "source_discovery",
                        "sources": [],
                        "gaps": [{"code": "candidate_not_found", "title": "Candidate not found"}],
                        "summary": "Candidate record not found.",
                    },
                )

            issuer_id = candidate.issuer_id
            sources: list[dict[str, object]] = []
            gaps: list[dict[str, object]] = []

            if issuer_id is not None:
                issuer = await session.get(Issuer, issuer_id)
                if issuer is not None:
                    sources.append(
                        {
                            "kind": "issuer_record",
                            "url": "",
                            "status": "verified",
                            "verification_method": "database",
                            "confidence": 1.0,
                            "official": True,
                            "discovered_by": "system",
                            "evidence": {"issuer_id": str(issuer_id), "issuer_name": issuer.name_pt},
                        }
                    )

                    if issuer.cnpj:
                        cvm_profile = await self._cvm.lookup_by_cnpj(issuer.cnpj)
                        if cvm_profile is not None:
                            evidence: dict[str, object] = {
                                "cnpj": cvm_profile.cnpj,
                                "cvm_code": cvm_profile.cvm_code,
                                "legal_name": cvm_profile.legal_name,
                                "registration_status": cvm_profile.registration_status or "",
                                "issuer_status": cvm_profile.issuer_status or "",
                            }
                            if cvm_profile.website:
                                evidence["website"] = cvm_profile.website
                            sources.append(
                                {
                                    "kind": "cvm_profile",
                                    "url": "",
                                    "status": "verified",
                                    "verification_method": "cvm_api",
                                    "confidence": 1.0,
                                    "official": True,
                                    "discovered_by": "system",
                                    "evidence": evidence,
                                }
                            )

                            securities = await self._cvm.lookup_securities_by_cnpj(issuer.cnpj)
                            if securities:
                                sources.append(
                                    {
                                        "kind": "cvm_filings",
                                        "url": "",
                                        "status": "verified",
                                        "verification_method": "cvm_fca",
                                        "confidence": 0.95,
                                        "official": True,
                                        "discovered_by": "system",
                                        "evidence": {
                                            "cnpj": issuer.cnpj,
                                            "security_count": len(securities),
                                            "tickers": [s.trading_code for s in securities if s.trading_code],
                                        },
                                    }
                                )

                            if cvm_profile.website and all(
                                s.get("kind") != "investor_relations" for s in sources if s.get("kind") != "cvm_profile"
                            ):
                                sources.append(
                                    {
                                        "kind": "investor_relations",
                                        "url": cvm_profile.website,
                                        "status": "verified",
                                        "verification_method": "cvm_api",
                                        "confidence": 0.9,
                                        "official": True,
                                        "discovered_by": "system",
                                        "evidence": {
                                            "cnpj": cvm_profile.cnpj,
                                            "source": "cvm_registration",
                                            "website": cvm_profile.website,
                                        },
                                    }
                                )

                    # RI portal from issuer record (best-effort)
                    if issuer.website_ri_url and not any(s.get("kind") == "ri_portal" for s in sources):
                        sources.append(
                            {
                                "kind": "ri_portal",
                                "url": issuer.website_ri_url,
                                "status": "discovered",
                                "verification_method": "issuer_record",
                                "confidence": 0.8,
                                "official": True,
                                "discovered_by": "system",
                                "evidence": {
                                    "issuer_id": str(issuer_id),
                                    "source": "issuer_website_ri_url",
                                    "website": issuer.website_ri_url,
                                },
                            }
                        )

            if candidate.ticker:
                b3_profile = await self._b3.lookup_by_ticker(candidate.ticker)
                if b3_profile is not None:
                    b3_evidence: dict[str, object] = {
                        "ticker": b3_profile.ticker,
                        "exchange": b3_profile.exchange,
                        "market_segment": b3_profile.market_segment or "",
                        "listing_status": b3_profile.listing_status,
                    }
                    if b3_profile.closing_price is not None:
                        b3_evidence["closing_price"] = str(b3_profile.closing_price)
                    if b3_profile.average_volume_30d is not None:
                        b3_evidence["average_volume_30d"] = str(b3_profile.average_volume_30d)
                    if b3_profile.last_trade_date is not None:
                        b3_evidence["last_trade_date"] = b3_profile.last_trade_date.isoformat()
                    sources.append(
                        {
                            "kind": "b3_listing",
                            "url": "",
                            "status": "verified",
                            "verification_method": "b3_cotahist",
                            "confidence": 1.0,
                            "official": True,
                            "discovered_by": "system",
                            "evidence": b3_evidence,
                        }
                    )

            if not sources:
                gaps.append(
                    {
                        "code": "issuer_not_found",
                        "title": "Issuer identity not yet resolved",
                        "level": "blocking",
                        "requested_user_action": "Complete identity resolution first.",
                    }
                )
            else:
                source_kinds = {s.get("kind") for s in sources}

                missing_ri = "investor_relations" not in source_kinds
                if missing_ri:
                    gaps.append(
                        {
                            "code": "investor_relations_missing",
                            "title": "Investor relations page not found",
                            "description": "Could not determine IR page from available data.",
                            "level": "blocking",
                            "requested_user_action": "Provide the investor relations URL manually.",
                            "source_kind": "investor_relations",
                        }
                    )

                missing_cvm_filings = "cvm_filings" not in source_kinds
                if missing_cvm_filings:
                    gaps.append(
                        {
                            "code": "cvm_filings_missing",
                            "title": "CVM regulatory filings not found",
                            "description": "FCA/DFP/ITR data not available for this issuer.",
                            "level": "blocking",
                            "requested_user_action": "Verify CNPJ is correct and CVM data is accessible.",
                            "source_kind": "cvm_filings",
                        }
                    )

                missing_b3 = "b3_listing" not in source_kinds
                if missing_b3:
                    gaps.append(
                        {
                            "code": "b3_listing_missing",
                            "title": "B3 listing not found",
                            "description": "Ticker not found in B3 COTAHIST or instrument master.",
                            "level": "blocking",
                            "requested_user_action": "Verify ticker is listed on B3.",
                            "source_kind": "b3_listing",
                        }
                    )

            return SourceDiscoveryCheckpoint(
                command=command,
                output={
                    "stage": "source_discovery",
                    "sources": sources,
                    "gaps": gaps,
                    "summary": f"Found {len(sources)} sources, {len(gaps)} gaps.",
                },
            )

    async def persist_candidate_sources_and_gaps(self, checkpoint: SourceDiscoveryCheckpoint) -> None:
        async with self._db.session() as session:
            repo = CandidateRepository(session, checkpoint.command.organization_id)
            candidate = await repo.get_candidate(checkpoint.command.candidate_id)
            if candidate is None:
                logger.warning("persist_sources: candidate %s not found", checkpoint.command.candidate_id)
                return

            output = checkpoint.output
            for src in output.get("sources", []):
                existing = (
                    await session.execute(
                        sa.select(CandidateSourceRecord).where(
                            CandidateSourceRecord.candidate_id == candidate.id,
                            CandidateSourceRecord.kind == src["kind"],
                        )
                    )
                ).scalar_one_or_none()
                if existing is not None:
                    continue
                status = str(src.get("status", "discovered"))
                verified_at = _now() if status == "verified" else None
                session.add(
                    CandidateSourceRecord(
                        candidate_id=candidate.id,
                        kind=str(src["kind"]),
                        url=str(src.get("url", "")),
                        normalized_url_hash=hashlib.sha256(str(src.get("url", "")).encode()).hexdigest(),
                        status=status,
                        verified_at=verified_at,
                        verification_method=str(src.get("verification_method", "system")),
                        confidence=float(src.get("confidence", 0.5)),
                        official=bool(src.get("official", False)),
                        discovered_by=str(src.get("discovered_by", "system")),
                        evidence=src.get("evidence", {}),
                    )
                )

            for gap in output.get("gaps", []):
                existing_gap = (
                    await session.execute(
                        sa.select(CandidateGapRecord).where(
                            CandidateGapRecord.candidate_id == candidate.id,
                            CandidateGapRecord.code == gap["code"],
                            CandidateGapRecord.status == "open",
                        )
                    )
                ).scalar_one_or_none()
                if existing_gap is not None:
                    continue
                session.add(
                    CandidateGapRecord(
                        candidate_id=candidate.id,
                        code=str(gap["code"]),
                        title=str(gap.get("title", "")),
                        description=str(gap.get("description", "")),
                        source_kind=str(gap.get("source_kind")) if gap.get("source_kind") else None,
                        level=str(gap.get("level", "blocking")),
                        status="open",
                        requested_user_action=str(gap.get("requested_user_action", "")),
                    )
                )

            session.add(
                CandidateEventRecord(
                    candidate_id=candidate.id,
                    organization_id=candidate.organization_id,
                    event_type="sources_persisted",
                    actor_type="system",
                    actor_id="candidate_runtime",
                    occurred_at=_now(),
                    aggregate_version=candidate.lock_version,
                    payload={"source_count": len(output.get("sources", [])), "gap_count": len(output.get("gaps", []))},
                )
            )
            candidate.lock_version += 1
            await session.commit()

    # ------------------------------------------------------------------
    # Phase 3 — Source Validation (SafeHttpClient)
    # ------------------------------------------------------------------

    async def validate_supplied_candidate_source(
        self,
        command: CandidateSourceValidationInput,
    ) -> CandidateSourceValidationResult:
        # P0-10: Verify source belongs to candidate (which has organization_id).
        async with self._db.session() as session:
            repo = CandidateRepository(session, command.organization_id)
            candidate = await repo.get_candidate(command.candidate_id)
            if candidate is None or candidate.organization_id != command.organization_id:
                return CandidateSourceValidationResult(
                    candidate_id=command.candidate_id,
                    source_id=command.source_id,
                    status="rejected",
                    official=False,
                    reason="Candidate not found or does not belong to this organization.",
                )

            source = await repo.get_source(command.candidate_id, command.source_id)
            if source is None or source.candidate_id != candidate.id:
                return CandidateSourceValidationResult(
                    candidate_id=command.candidate_id,
                    source_id=command.source_id,
                    status="rejected",
                    official=False,
                    reason="Source record not found or does not belong to this candidate.",
                )

            try:
                response = await self._http.get(source.url)
            except Exception as exc:
                logger.warning("validate_source %s: %s", source.url, exc)
                return CandidateSourceValidationResult(
                    candidate_id=command.candidate_id,
                    source_id=command.source_id,
                    status="unreachable",
                    official=False,
                    reason=f"Failed to fetch URL: {exc}",
                )

            if response.status_code >= 400:
                return CandidateSourceValidationResult(
                    candidate_id=command.candidate_id,
                    source_id=command.source_id,
                    status="unreachable",
                    official=False,
                    reason=f"HTTP {response.status_code}",
                )

            raw_content = response.content
            raw_hash = hashlib.sha256(raw_content).hexdigest()

            if self._object_store is not None:
                try:
                    raw_key = f"candidates/{command.candidate_id}/raw/{source.id}/{raw_hash}"
                    media_type = response.headers.get("content-type", "application/octet-stream")
                    await self._object_store.put_once(raw_key, raw_content, media_type, raw_hash)
                except Exception as exc:
                    logger.warning("S3 raw store failed for source %s: %s", source.id, exc)

            content_type = response.headers.get("content-type", "")
            if "html" in content_type or "xml" in content_type:
                content = _extract_text_from_html(raw_content)
            else:
                content = raw_content.decode("utf-8", errors="replace").lower()

            # P0-09: Strong signal requirement.
            # Ticker alone NEVER confirms officiality.
            # Must have >= 2 strong signals OR 1 strong + ticker.
            strong_signals = []
            has_ticker = False
            if candidate is not None:
                if candidate.legal_name and candidate.legal_name.lower() in content:
                    strong_signals.append("legal_name")
                if candidate.trading_name and candidate.trading_name.lower() in content:
                    strong_signals.append("trading_name")
                if candidate.cnpj and candidate.cnpj in content:
                    strong_signals.append("cnpj")
                if candidate.ticker and candidate.ticker.lower() in content:
                    has_ticker = True

            if not strong_signals and not has_ticker:
                source.status = "rejected"
                source.last_checked_at = _now()
                source.evidence = {
                    "status_code": response.status_code,
                    "final_url": response.final_url,
                    "reason": "No matching identity signals found in page content",
                    "raw_content_hash": raw_hash,
                    "raw_storage_key": f"candidates/{command.candidate_id}/raw/{source.id}/{raw_hash}",
                }
                await session.commit()
                return CandidateSourceValidationResult(
                    candidate_id=command.candidate_id,
                    source_id=command.source_id,
                    status="rejected",
                    official=False,
                    reason="No matching identity signals found. The page may belong to a different entity.",
                )

            # P0-09: Strong signal requirement for official status.
            official = (
                len(strong_signals) >= 2
                or (
                    len(strong_signals) == 1
                    and has_ticker
                    and strong_signals[0] in ("cnpj", "legal_name")
                )
            )

            if official:
                source.official = True
                source.status = "verified"
                source.verified_at = _now()
                source.last_checked_at = _now()
                source.evidence = {
                    "status_code": response.status_code,
                    "final_url": response.final_url,
                    "redirect_chain": list(response.redirect_chain),
                    "identity_signals": strong_signals + (["ticker"] if has_ticker else []),
                    "raw_content_hash": raw_hash,
                    "raw_storage_key": f"candidates/{command.candidate_id}/raw/{source.id}/{raw_hash}",
                }
                await session.commit()
                gap_codes = CANONICAL_GAP_CODES.get(source.kind, ())
                return CandidateSourceValidationResult(
                    candidate_id=command.candidate_id,
                    source_id=command.source_id,
                    status="verified",
                    official=True,
                    reason=f"Verified: strong signals {', '.join(strong_signals)}"
                    + (" + ticker" if has_ticker else ""),
                    resolved_gap_codes=gap_codes,
                )

            source.status = "rejected"
            source.last_checked_at = _now()
            source.evidence = {
                "status_code": response.status_code,
                "final_url": response.final_url,
                "reason": "Insufficient identity signals for official status (ticker alone is not enough)",
                "raw_content_hash": raw_hash,
                "raw_storage_key": f"candidates/{command.candidate_id}/raw/{source.id}/{raw_hash}",
            }
            await session.commit()

            return CandidateSourceValidationResult(
                candidate_id=command.candidate_id,
                source_id=command.source_id,
                status="rejected",
                official=False,
                reason="Insufficient identity signals for official status. "
                "Ticker alone is not enough to confirm officiality.",
            )

    # ------------------------------------------------------------------
    # Phase 4 — Document Collection
    # ------------------------------------------------------------------

    async def collect_candidate_documents(self, command: CandidateWorkflowInput) -> CandidateCheckpoint:
        async with self._db.session() as session:
            sources = (
                (
                    await session.execute(
                        sa.select(CandidateSourceRecord).where(
                            CandidateSourceRecord.candidate_id == command.candidate_id,
                            CandidateSourceRecord.status == "verified",
                        )
                    )
                )
                .scalars()
                .all()
            )

            candidate = (
                (
                    await session.execute(
                        sa.select(InvestmentCandidateRecord).where(
                            InvestmentCandidateRecord.id == command.candidate_id,
                        )
                    )
                )
                .scalars()
                .one_or_none()
            )

            if not candidate:
                return _stage_blocked(
                    command,
                    "document_collection",
                    f"Candidate {command.candidate_id} not found.",
                    blocker_codes=("candidate_not_found",),
                )

            start_version = candidate.lock_version

        if not sources:
            return _stage_blocked(
                command,
                "document_collection",
                "No verified sources available. Complete source validation first.",
                blocker_codes=("no_verified_sources",),
            )

        collected = 0
        failed = 0
        stored_to_s3 = 0
        version = start_version
        for source in sources:
            if not source.url:
                continue
            try:
                response = await self._http.get(source.url)
                content = response.content
                content_hash = hashlib.sha256(content).hexdigest()
                async with self._db.session() as session:
                    session.add(
                        CandidateEventRecord(
                            candidate_id=command.candidate_id,
                            organization_id=command.organization_id,
                            event_type="document_collected",
                            actor_type="system",
                            actor_id="candidate_runtime",
                            occurred_at=_now(),
                            aggregate_version=version,
                            payload={
                                "source_id": str(source.id),
                                "kind": source.kind,
                                "url": source.url,
                                "content_hash": content_hash,
                                "content_length": len(content),
                                "status_code": response.status_code,
                            },
                        )
                    )
                    version += 1
                    await session.commit()
                collected += 1

                if self._object_store is not None:
                    try:
                        storage_key = f"candidates/{command.candidate_id}/docs/{source.id}/{content_hash}"
                        media_type = response.headers.get("content-type", "application/octet-stream")
                        await self._object_store.put_once(storage_key, content, media_type, content_hash)
                        stored_to_s3 += 1
                    except Exception as exc:
                        logger.warning("S3 put_once failed for source %s: %s", source.id, exc)

            except Exception as exc:
                logger.warning("collect_document %s: %s", source.url, exc)
                failed += 1

        if collected == 0:
            return _stage_blocked(
                command,
                "document_collection",
                f"Failed to download documents from {failed} source(s).",
                blocker_codes=("document_download_failed",),
            )

        async with self._db.session() as session:
            await session.execute(
                sa.update(InvestmentCandidateRecord)
                .where(
                    InvestmentCandidateRecord.id == command.candidate_id,
                    InvestmentCandidateRecord.lock_version == start_version,
                )
                .values(lock_version=start_version + collected)
            )
            await session.commit()

        return _stage_passed(
            command,
            "document_collection",
            reason=f"Downloaded {collected} document(s), {stored_to_s3} stored to S3, {failed} failure(s).",
            payload={"collected": collected, "stored_to_s3": stored_to_s3, "failed": failed},
        )

    # ------------------------------------------------------------------
    # Phase 4b — Financial Data Ingestion
    # ------------------------------------------------------------------

    async def ingest_candidate_financial_data(self, command: CandidateWorkflowInput) -> CandidateCheckpoint:
        from collections import defaultdict

        from connectors.cvm._financials import FinancialEntry, StatementType, get_dfp, parse_value_status
        from database.models.data_foundation import DataSource, SourceLicense, SourceObject, SourceObjectVersion
        from database.models.financial_facts import FinancialFact, ReportingPeriod
        from ia_investing.application.financial_facts import FinancialFactInput, FinancialFactRepository

        async with self._db.session() as session:
            repo = CandidateRepository(session, command.organization_id)
            candidate = await repo.get_candidate(command.candidate_id)
            if candidate is None or candidate.issuer_id is None:
                return _stage_blocked(
                    command,
                    "data_quality",
                    "Issuer not resolved. Complete identity resolution first.",
                    blocker_codes=("issuer_not_resolved",),
                )
            if not candidate.cnpj:
                return _stage_blocked(
                    command,
                    "data_quality",
                    "No CNPJ available for this candidate.",
                    blocker_codes=("cnpj_missing",),
                )

            issuer_id = candidate.issuer_id
            cnpj = candidate.cnpj
            now = _now()

            year = command.data_as_of.year
            entries_by_stmt: dict[StatementType, list[FinancialEntry]] = defaultdict(list)
            for y in (year, year - 1):
                for stmt in (StatementType.DRE_CON, StatementType.BPA_CON, StatementType.BPP_CON):
                    try:
                        result = await get_dfp(y, statement=stmt, cnpj=cnpj, client=self._client)
                        entries_by_stmt[stmt].extend(result)
                    except Exception as exc:
                        logger.warning("DFP fetch failed for year=%d stmt=%s: %s", y, stmt.value, exc)

            total_entries = sum(len(v) for v in entries_by_stmt.values())
            if total_entries == 0:
                return _stage_blocked(
                    command,
                    "data_quality",
                    f"No DFP data found for CNPJ {cnpj}.",
                    blocker_codes=("financial_facts_missing",),
                )

            ds_code = "cvm_dfp"
            ds = (await session.execute(sa.select(DataSource).where(DataSource.code == ds_code))).scalar_one_or_none()
            if ds is None:
                lic = (await session.execute(sa.select(SourceLicense).where(SourceLicense.code == "cvm_open_data"))).scalar_one_or_none()
                if lic is None:
                    lic = SourceLicense(
                        code="cvm_open_data",
                        name="CVM Dados Abertos",
                        terms_url="https://dados.cvm.gov.br/",
                        permits_redistribution=True,
                    )
                    session.add(lic)
                    await session.flush()
                ds = DataSource(
                    code=ds_code,
                    name="CVM DFP - Demonstrativos Financeiros Padronizados",
                    base_url="https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/DFP/DADOS/",
                    owner_role="system",
                    schema_version="v1",
                    license_id=lic.id,
                )
                session.add(ds)
                await session.flush()

            so_by_year: dict[int, SourceObject] = {}
            sov_by_year: dict[int, SourceObjectVersion] = {}
            rp_cache: dict[tuple[UUID, date, date, str, str], ReportingPeriod] = {}
            fact_repo = FinancialFactRepository(session)
            ingested = 0

            for stmt, entries in entries_by_stmt.items():
                consolidation = "consolidated" if stmt.value.endswith("_con") else "individual"
                statement_name = stmt.value.rsplit("_", 1)[0].upper()

                for entry in entries:
                    try:
                        period_end = date.fromisoformat(entry.dt_referencia)
                    except (ValueError, TypeError):
                        continue
                    if entry.dt_inicio_exercicio:
                        try:
                            period_start = date.fromisoformat(entry.dt_inicio_exercicio)
                        except (ValueError, TypeError):
                            period_start = date(period_end.year, 1, 1)
                    else:
                        period_start = date(period_end.year, 1, 1)

                    rp_key = (issuer_id, period_start, period_end, "annual", consolidation)
                    rp = rp_cache.get(rp_key)
                    if rp is None:
                        rp = (
                            await session.execute(
                                sa.select(ReportingPeriod).where(
                                    ReportingPeriod.issuer_id == issuer_id,
                                    ReportingPeriod.period_start == period_start,
                                    ReportingPeriod.period_end == period_end,
                                    ReportingPeriod.period_type == "annual",
                                    ReportingPeriod.consolidation_scope == consolidation,
                                )
                            )
                        ).scalar_one_or_none()
                        if rp is None:
                            rp = ReportingPeriod(
                                issuer_id=issuer_id,
                                period_start=period_start,
                                period_end=period_end,
                                fiscal_year=period_end.year,
                                period_type="annual",
                                consolidation_scope=consolidation,
                            )
                            session.add(rp)
                            await session.flush()
                        rp_cache[rp_key] = rp

                    logical_uri = f"cvm://dfp/{period_end.year}/{cnpj}"
                    so = so_by_year.get(period_end.year)
                    if so is None:
                        so = (
                            await session.execute(
                                sa.select(SourceObject).where(
                                    SourceObject.source_id == ds.id,
                                    SourceObject.logical_uri == logical_uri,
                                )
                            )
                        ).scalar_one_or_none()
                        if so is None:
                            so = SourceObject(
                                source_id=ds.id,
                                logical_uri=logical_uri,
                                object_type="cvm_dfp_zip",
                            )
                            session.add(so)
                            await session.flush()
                        so_by_year[period_end.year] = so

                    sov = sov_by_year.get(period_end.year)
                    if sov is None:
                        synthetic_hash = hashlib.sha256(f"cvm_dfp_{cnpj}_{period_end.year}".encode()).hexdigest()
                        storage_key = f"cvm/dfp/{period_end.year}/{cnpj}"
                        sov = (
                            await session.execute(
                                sa.select(SourceObjectVersion).where(
                                    SourceObjectVersion.source_object_id == so.id,
                                    SourceObjectVersion.content_sha256 == synthetic_hash,
                                )
                            )
                        ).scalar_one_or_none()
                        if sov is None:
                            sov = SourceObjectVersion(
                                source_object_id=so.id,
                                version_number=1,
                                content_sha256=synthetic_hash,
                                storage_key=storage_key,
                                size_bytes=0,
                                media_type="application/zip",
                                discovered_at=now,
                                ingested_at=now,
                                parser_version="cvm-dfp-ingest-v1",
                            )
                            session.add(sov)
                            await session.flush()
                        sov_by_year[period_end.year] = sov

                    value, value_status = parse_value_status(str(entry.valor))
                    scale_factor = 1000 if entry.escala.upper() == "MIL" else 1

                    try:
                        await fact_repo.revise(
                            FinancialFactInput(
                                issuer_id=issuer_id,
                                reporting_period_id=rp.id,
                                statement_type=statement_name,
                                consolidation_scope=consolidation,
                                original_account_code=entry.cod_conta,
                                original_account_label=entry.desc_conta,
                                taxonomy_account_id=None,
                                value=value,
                                currency_code="BRL",
                                scale_factor=scale_factor,
                                value_status=value_status,
                                source_object_version_id=sov.id,
                                parser_version="cvm-dfp-ingest-v1",
                                mapping_rule_id=None,
                                published_at=now,
                                discovered_at=now,
                                ingested_at=now,
                                validated_at=now,
                                knowledge_at=now,
                            )
                        )
                        ingested += 1
                    except Exception as exc:
                        logger.debug("revise failed for account=%s: %s", entry.cod_conta, exc)

            await session.commit()

            count = (
                await session.execute(
                    sa.select(sa.func.count(FinancialFact.id)).where(
                        FinancialFact.issuer_id == issuer_id,
                    )
                )
            ).scalar()

            if count and count > 0:
                return _stage_passed(
                    command,
                    "data_quality",
                    reason=f"Ingested {ingested} entries, {count} total facts for issuer.",
                    payload={"fact_count": count, "ingested": ingested},
                )

            return _stage_blocked(
                command,
                "data_quality",
                "Failed to ingest any financial facts from DFP data.",
                blocker_codes=("financial_facts_missing",),
            )

    # ------------------------------------------------------------------
    # Phase 5 — Readiness, Validation, Analysis
    # ------------------------------------------------------------------

    async def evaluate_candidate_readiness(self, command: CandidateWorkflowInput) -> CandidateCheckpoint:
        async with self._db.session() as session:
            repo = CandidateRepository(session, command.organization_id)
            candidate = await repo.get_candidate(command.candidate_id)
            if candidate is None:
                return _stage_blocked(
                    command,
                    "readiness",
                    "Candidate not found.",
                    blocker_codes=("candidate_not_found",),
                )

            gaps = (
                (
                    await session.execute(
                        sa.select(CandidateGapRecord).where(
                            CandidateGapRecord.candidate_id == candidate.id,
                            CandidateGapRecord.status == "open",
                            CandidateGapRecord.level == "blocking",
                        )
                    )
                )
                .scalars()
                .all()
            )

            if gaps:
                return _stage_blocked(
                    command,
                    "readiness",
                    f"{len(gaps)} blocking gap(s) remain.",
                    blocker_codes=tuple(g.code for g in gaps),
                )

            return _stage_passed(command, "readiness", reason="All blocking gaps resolved.")

    async def validate_candidate_sources(self, command: CandidateWorkflowInput) -> CandidateCheckpoint:
        async with self._db.session() as session:
            unverified = (
                await session.execute(
                    sa.select(sa.func.count(CandidateSourceRecord.id)).where(
                        CandidateSourceRecord.candidate_id == command.candidate_id,
                        CandidateSourceRecord.status == "discovered",
                    )
                )
            ).scalar()

            if unverified and unverified > 0:
                return _stage_blocked(
                    command,
                    "source_validation",
                    f"{unverified} source(s) await verification.",
                    blocker_codes=("unverified_sources",),
                )

            sources = (
                (
                    await session.execute(
                        sa.select(CandidateSourceRecord).where(
                            CandidateSourceRecord.candidate_id == command.candidate_id,
                        )
                    )
                )
                .scalars()
                .all()
            )

            return _stage_passed(
                command,
                "source_validation",
                reason=f"{len(sources)} source(s) verified.",
                payload={"source_count": len(sources)},
            )

    async def validate_candidate_financial_data(self, command: CandidateWorkflowInput) -> CandidateCheckpoint:
        async with self._db.session() as session:
            repo = CandidateRepository(session, command.organization_id)
            candidate = await repo.get_candidate(command.candidate_id)
            if candidate is None or candidate.issuer_id is None:
                return _stage_blocked(
                    command,
                    "data_quality",
                    "Issuer not resolved. Complete identity resolution first.",
                    blocker_codes=("issuer_not_resolved",),
                )

            from database.models.financial_facts import FinancialFact

            count = (
                await session.execute(
                    sa.select(sa.func.count(FinancialFact.id)).where(
                        FinancialFact.issuer_id == candidate.issuer_id,
                    )
                )
            ).scalar()

            if count and count > 0:
                return _stage_passed(
                    command,
                    "data_quality",
                    reason=f"Found {count} financial facts for issuer.",
                    payload={"fact_count": count},
                )

            return _stage_blocked(
                command,
                "data_quality",
                "No financial facts found for this issuer. Financial data connectors not yet wired.",
                blocker_codes=("financial_facts_missing",),
            )

    async def run_candidate_fundamental_analysis(self, command: CandidateWorkflowInput) -> CandidateCheckpoint:
        async with self._db.session() as session:
            repo = CandidateRepository(session, command.organization_id)
            candidate = await repo.get_candidate(command.candidate_id)
            if candidate is None or candidate.issuer_id is None:
                return _stage_blocked(
                    command,
                    "fundamental_analysis",
                    "Issuer not resolved. Complete identity resolution first.",
                    blocker_codes=("issuer_not_resolved",),
                )
            input_data = {
                "ticker": candidate.ticker,
                "legal_name": candidate.legal_name or "",
                "issuer_id": str(candidate.issuer_id),
                "data_as_of": command.data_as_of.isoformat(),
            }
        result: AgentResult = await _execute_governed_agent(
            self._db,
            "fundamentalist_analyst",
            command.organization_id,
            input_data,
            command.data_as_of,
            command.data_as_of,
        )
        if result.status != "completed":
            return _stage_blocked(
                command,
                "fundamental_analysis",
                f"Fundamental analysis agent failed: {result.error_message or 'unknown error'}",
                blocker_codes=("fundamental_analysis_failed",),
            )
        async with self._db.session() as session:
            repo = CandidateRepository(session, command.organization_id)
            c = await repo.get_candidate(command.candidate_id)
            if c is not None:
                session.add(
                    CandidateEventRecord(
                        candidate_id=c.id,
                        organization_id=c.organization_id,
                        event_type="fundamental_analysis_completed",
                        actor_type="system",
                        actor_id="candidate_runtime",
                        occurred_at=_now(),
                        aggregate_version=c.lock_version,
                        payload={
                            "model_used": result.model_used,
                            "output": result.output_data if isinstance(result.output_data, dict) else {},
                            "cost_usd": result.cost_usd,
                            "duration_ms": result.duration_ms,
                        },
                    )
                )
                c.lock_version += 1
                await session.commit()
        return _stage_passed(
            command,
            "fundamental_analysis",
            reason=f"Fundamental analysis completed via {result.model_used}",
            payload={"model_used": result.model_used, "cost_usd": result.cost_usd},
        )

    async def run_candidate_risk_analysis(self, command: CandidateWorkflowInput) -> CandidateCheckpoint:
        async with self._db.session() as session:
            repo = CandidateRepository(session, command.organization_id)
            candidate = await repo.get_candidate(command.candidate_id)
            if candidate is None or candidate.issuer_id is None:
                return _stage_blocked(
                    command,
                    "risk_analysis",
                    "Issuer not resolved. Complete identity resolution first.",
                    blocker_codes=("issuer_not_resolved",),
                )
            input_data = {
                "ticker": candidate.ticker,
                "legal_name": candidate.legal_name or "",
                "issuer_id": str(candidate.issuer_id),
                "data_as_of": command.data_as_of.isoformat(),
            }
        result: AgentResult = await _execute_governed_agent(
            self._db,
            "risk_director",
            command.organization_id,
            input_data,
            command.data_as_of,
            command.data_as_of,
        )
        if result.status != "completed":
            return _stage_blocked(
                command,
                "risk_analysis",
                f"Risk analysis agent failed: {result.error_message or 'unknown error'}",
                blocker_codes=("risk_analysis_failed",),
            )
        async with self._db.session() as session:
            repo = CandidateRepository(session, command.organization_id)
            c = await repo.get_candidate(command.candidate_id)
            if c is not None:
                session.add(
                    CandidateEventRecord(
                        candidate_id=c.id,
                        organization_id=c.organization_id,
                        event_type="risk_analysis_completed",
                        actor_type="system",
                        actor_id="candidate_runtime",
                        occurred_at=_now(),
                        aggregate_version=c.lock_version,
                        payload={
                            "model_used": result.model_used,
                            "output": result.output_data if isinstance(result.output_data, dict) else {},
                            "cost_usd": result.cost_usd,
                            "duration_ms": result.duration_ms,
                        },
                    )
                )
                c.lock_version += 1
                await session.commit()
        return _stage_passed(
            command,
            "risk_analysis",
            reason=f"Risk analysis completed via {result.model_used}",
            payload={"model_used": result.model_used, "cost_usd": result.cost_usd},
        )

    async def create_committee_pack(self, command: CandidateWorkflowInput) -> CandidateCheckpoint:
        async with self._db.session() as session:
            repo = CandidateRepository(session, command.organization_id)
            candidate = await repo.get_candidate(command.candidate_id)
            if candidate is None or candidate.issuer_id is None:
                return _stage_blocked(
                    command,
                    "committee_review",
                    "Issuer not resolved. Complete identity resolution first.",
                    blocker_codes=("issuer_not_resolved",),
                )
            events = (
                (
                    await session.execute(
                        sa.select(CandidateEventRecord)
                        .where(
                            CandidateEventRecord.candidate_id == candidate.id,
                            CandidateEventRecord.event_type.in_(
                                {"fundamental_analysis_completed", "risk_analysis_completed"}
                            ),
                        )
                        .order_by(CandidateEventRecord.occurred_at.desc())
                    )
                )
                .scalars()
                .all()
            )
            input_data = {
                "ticker": candidate.ticker,
                "legal_name": candidate.legal_name or "",
                "analysis_run_id": str(command.analysis_run_id),
                "data_as_of": command.data_as_of.isoformat(),
                "analysis_events": [
                    {
                        "event_type": e.event_type,
                        "payload": e.payload,
                        "occurred_at": e.occurred_at.isoformat(),
                    }
                    for e in events
                ],
            }
        result: AgentResult = await _execute_governed_agent(
            self._db,
            "investment_committee",
            command.organization_id,
            input_data,
            command.data_as_of,
            command.data_as_of,
        )
        if result.status != "completed":
            return _stage_blocked(
                command,
                "committee_review",
                f"Committee agent unavailable: {result.error_message or 'no AI provider'}. Requires human review.",
                blocker_codes=("committee_ai_unavailable",),
            )
        if not isinstance(result.output_data, dict):
            return _stage_blocked(
                command,
                "committee_review",
                "Committee agent returned no decision payload. Requires human review.",
                blocker_codes=("committee_no_decision",),
            )
        decision_output: dict[str, Any] = result.output_data
        decision_value = str(decision_output.get("decision", decision_output.get("action", ""))).lower()
        if not decision_value:
            return _stage_blocked(
                command,
                "committee_review",
                "Committee agent returned empty decision. Requires human review.",
                blocker_codes=("committee_no_decision",),
            )
        committee_decision_id = await self._create_institutional_committee_decision(
            session=session,
            candidate=candidate,
            command=command,
            decision=decision_value,
            rationale=str(decision_output.get("rationale", decision_output.get("reason", ""))),
            model_used=result.model_used,
        )
        async with self._db.session() as db_session:
            repo = CandidateRepository(db_session, command.organization_id)
            c = await repo.get_candidate(command.candidate_id)
            if c is not None:
                db_session.add(
                    CandidateEventRecord(
                        candidate_id=c.id,
                        organization_id=c.organization_id,
                        event_type="committee_decision_recorded",
                        actor_type="system",
                        actor_id="candidate_runtime",
                        occurred_at=_now(),
                        aggregate_version=c.lock_version,
                        payload={
                            "model_used": result.model_used,
                            "decision": decision_value,
                            "committee_decision_id": str(committee_decision_id),
                        },
                    )
                )
                c.lock_version += 1
                await db_session.commit()
        return _stage_passed(
            command,
            "committee_review",
            reason=f"Committee decision recorded: {decision_value} via {result.model_used}",
            payload={
                "model_used": result.model_used,
                "decision": decision_value,
                "committee_decision_id": str(committee_decision_id),
            },
        )

    async def _create_institutional_committee_decision(
        self,
        session: AsyncSession,
        candidate: InvestmentCandidateRecord,
        command: CandidateWorkflowInput,
        decision: str,
        rationale: str,
        model_used: str,
    ) -> UUID:
        now = _now()
        session_id = uuid.uuid4()
        committee_members: list[dict[str, Any]] = [
            {"member_id": "agent_committee", "subject": model_used, "role": "analyst", "conflicts": []},
        ]
        committee_session = CommitteeSession(
            id=session_id,
            organization_id=candidate.organization_id,
            thesis_ids=[f"candidate-{candidate.id}"],
            members=committee_members,
            scheduled_at=now,
            agenda={
                "proposer": "candidate_runtime",
                "candidate_id": str(candidate.id),
                "ticker": candidate.ticker,
                "model_used": model_used,
            },
            state="scheduled",
            total_members=1,
            present_members=1,
            votes_in_favor=1 if decision in ("approve", "approve_with_conditions") else 0,
            votes_against=1 if decision == "reject" else 0,
            members_notified=True,
            decision=decision,
            rationale=rationale,
            published_at=now,
            created_at=now,
            updated_at=now,
        )
        session.add(committee_session)
        await session.flush()
        decision_record = CommitteeDecision(
            id=uuid.uuid4(),
            organization_id=candidate.organization_id,
            session_id=session_id,
            decision=decision,
            rationale=rationale,
            votes_summary={
                "in_favor": 1 if decision in ("approve", "approve_with_conditions") else 0,
                "against": 1 if decision == "reject" else 0,
                "abstain": 0,
                "total": 1,
            },
            published_at=now,
            created_at=now,
        )
        session.add(decision_record)
        vote_record = CommitteeVote(
            id=uuid.uuid4(),
            organization_id=candidate.organization_id,
            session_id=session_id,
            member_id="agent_committee",
            proposal_id="candidate_proposal",
            vote="in_favor" if decision in ("approve", "approve_with_conditions") else "against",
            justification=rationale,
            created_at=now,
        )
        session.add(vote_record)
        await session.flush()
        return decision_record.id

    # ------------------------------------------------------------------
    # Phase 6 — Final Completion
    # ------------------------------------------------------------------

    async def complete_candidate_analysis_run(
        self,
        command: CandidateWorkflowInput,
        checkpoint: CandidateCheckpoint,
    ) -> CandidateWorkflowResult:
        checkpoint_payload: dict[str, Any] = checkpoint.payload or {}
        committee_decision_id_str = checkpoint_payload.get("committee_decision_id")
        resolved = _resolve_run_decision(checkpoint, checkpoint_payload)

        async with self._db.session() as session:
            repo = CandidateRepository(session, command.organization_id)
            run = await repo.get_analysis_run(command.candidate_id, command.analysis_run_id)
            if run is not None:
                run.completed_at = _now()
                run.status = "blocked" if checkpoint.blocked else "succeeded"
                run.decision = resolved.run_decision
                run.blocker_codes = list(checkpoint.blocker_codes)
                run.summary = checkpoint.reason
                if committee_decision_id_str:
                    with contextlib.suppress(ValueError, AttributeError):
                        run.committee_decision_id = uuid.UUID(committee_decision_id_str)
                await session.commit()

            candidate = await repo.get_candidate(command.candidate_id)
            if candidate is not None:
                if resolved.candidate_status:
                    candidate.status = resolved.candidate_status
                if resolved.final_decision:
                    candidate.final_decision = resolved.final_decision
                if resolved.final_decision_reason:
                    candidate.final_decision_reason = resolved.final_decision_reason
                if resolved.approved_eligible is not None:
                    candidate.approved_portfolio_eligible = resolved.approved_eligible
                await session.commit()

        logger.info(
            "complete_run candidate=%s status=%s stage=%s",
            command.candidate_id,
            "blocked" if checkpoint.blocked else "succeeded",
            checkpoint.stage,
        )
        return CandidateWorkflowResult(
            candidate_id=command.candidate_id,
            analysis_run_id=command.analysis_run_id,
            status="blocked" if checkpoint.blocked else "succeeded",
            decision=checkpoint.decision,
            reason=checkpoint.reason,
            blocker_codes=checkpoint.blocker_codes,
        )

    # ------------------------------------------------------------------
    # Phase 7 — Equity Universe & Explorer
    # ------------------------------------------------------------------

    async def screen_equity_universe(self, command: ExplorationWorkflowInput) -> ExplorationShortlist:
        settings = get_settings().candidate_intelligence
        cutoff_30d = _now() - timedelta(days=30)

        async with self._db.session() as session:
            stmt = (
                sa.select(
                    Instrument.id,
                    Listing.ticker,
                    Listing.exchange_code,
                    Issuer.id,
                    Issuer.name_pt,
                )
                .select_from(Instrument)
                .join(Issuer, Instrument.issuer_id == Issuer.id)
                .join(Listing, Listing.instrument_id == Instrument.id)
                .where(
                    Instrument.is_active.is_(True),
                    Listing.valid_to.is_(None),
                    sa.or_(
                        Listing.market_segment.is_(None),
                        Listing.market_segment.notin_(("FRACIONARIO",)),
                    ),
                )
            )

            # Subquery: average daily volume over last 30 days per listing
            avg_volume_sq = (
                sa.select(
                    MarketBar.listing_id,
                    sa.func.avg(MarketBar.volume).label("avg_vol_30d"),
                )
                .where(MarketBar.bar_at >= cutoff_30d)
                .group_by(MarketBar.listing_id)
                .subquery()
            )
            stmt = stmt.join(avg_volume_sq, avg_volume_sq.c.listing_id == Listing.id, isouter=True).where(
                sa.or_(
                    avg_volume_sq.c.avg_vol_30d.is_(None),
                    avg_volume_sq.c.avg_vol_30d >= settings.min_avg_volume_30d,
                )
            )

            # Subquery: latest spread per listing
            latest_quote_sq = sa.select(
                MarketQuote.listing_id,
                MarketQuote.bid_price,
                MarketQuote.ask_price,
                sa.func.row_number()
                .over(partition_by=MarketQuote.listing_id, order_by=MarketQuote.quoted_at.desc())
                .label("rn"),
            ).subquery()
            latest_quote_filtered = (
                sa.select(
                    latest_quote_sq.c.listing_id,
                    latest_quote_sq.c.bid_price,
                    latest_quote_sq.c.ask_price,
                )
                .where(latest_quote_sq.c.rn == 1)
                .subquery()
            )
            stmt = stmt.join(
                latest_quote_filtered,
                latest_quote_filtered.c.listing_id == Listing.id,
            ).where(
                latest_quote_filtered.c.bid_price.isnot(None),
                latest_quote_filtered.c.ask_price.isnot(None),
                sa.func.abs(
                    (latest_quote_filtered.c.ask_price - latest_quote_filtered.c.bid_price)
                    / sa.func.nullif(latest_quote_filtered.c.bid_price, 0)
                )
                <= settings.max_spread_pct,
            )

            stmt = stmt.distinct()
            rows = (await session.execute(stmt)).all()

            securities = tuple(
                {
                    "listing_id": str(row[0]),
                    "instrument_id": str(row[1]),
                    "symbol": str(row[2]),
                    "exchange": str(row[3] or ""),
                    "issuer_id": str(row[4]),
                    "issuer_name": str(row[5]),
                }
                for row in rows
            )

            return ExplorationShortlist(
                command=command,
                securities=securities,
                universe_size=len(rows),
                eligible_size=len(rows),
            )

    async def run_equity_explorer_agent(self, shortlist: ExplorationShortlist) -> ExplorationFindings:
        securities_sample = shortlist.securities[:20]
        input_data = {
            "exploration_run_id": str(shortlist.command.exploration_run_id),
            "universe_size": shortlist.universe_size,
            "eligible_size": shortlist.eligible_size,
            "securities": [
                {
                    "instrument_id": s.get("instrument_id", ""),
                    "symbol": s.get("symbol", ""),
                    "issuer_name": s.get("issuer_name", ""),
                }
                for s in securities_sample
            ],
        }
        result: AgentResult = await _execute_governed_agent(
            self._db,
            "research_coordinator",
            shortlist.command.organization_id,
            input_data,
            shortlist.command.data_as_of,
            shortlist.command.data_as_of,
        )
        if result.status != "completed" or not isinstance(result.output_data, dict):
            return ExplorationFindings(
                shortlist=shortlist,
                suggestions=(),
                limitations=(
                    f"Equity explorer agent had no AI provider; {result.error_message or 'unavailable'}. "
                    f"Universe available: {shortlist.universe_size} instruments.",
                ),
            )
        output: dict[str, object] = result.output_data
        raw_suggestions = output.get("suggestions", [])
        if isinstance(raw_suggestions, list):
            suggestions = tuple(
                {
                    "instrument_id": str(s.get("instrument_id", "")),
                    "symbol": str(s.get("symbol", "")),
                    "issuer_name": str(s.get("issuer_name", "")),
                    "rationale": str(s.get("rationale", "")),
                    "score": float(s.get("score", 0)),
                }
                for s in raw_suggestions
                if isinstance(s, dict)
            )
        else:
            suggestions = ()
        return ExplorationFindings(
            shortlist=shortlist,
            suggestions=suggestions,
            limitations=(),
        )

    async def persist_exploration_suggestions(self, findings: ExplorationFindings) -> ExplorationWorkflowResult:
        suggestions_persisted = 0
        async with self._db.session() as session:
            repo = CandidateRepository(session, findings.shortlist.command.organization_id)
            run = await repo.get_exploration_run(findings.shortlist.command.exploration_run_id)
            if run is None:
                return ExplorationWorkflowResult(
                    exploration_run_id=findings.shortlist.command.exploration_run_id,
                    status="failed",
                    universe_size=0,
                    eligible_size=0,
                    suggestion_count=0,
                )

            {s["listing_id"]: s for s in findings.shortlist.securities}
            security_by_instrument_id = {s["instrument_id"]: s for s in findings.shortlist.securities}

            for suggestion in findings.suggestions:
                inst_id = suggestion.get("instrument_id", "")
                if not inst_id:
                    continue
                security = security_by_instrument_id.get(inst_id)
                if security is None:
                    continue

                inst_uuid = uuid.UUID(inst_id) if isinstance(inst_id, str) else inst_id
                listing_uuid = (
                    uuid.UUID(security["listing_id"])
                    if isinstance(security["listing_id"], str)
                    else security["listing_id"]
                )
                issuer_uuid = (
                    uuid.UUID(security["issuer_id"])
                    if isinstance(security["issuer_id"], str)
                    else security["issuer_id"]
                )

                existing = (
                    await session.execute(
                        sa.select(ExplorationSuggestionRecord.id).where(
                            ExplorationSuggestionRecord.organization_id == run.organization_id,
                            ExplorationSuggestionRecord.instrument_id == inst_uuid,
                        )
                    )
                ).scalar_one_or_none()
                if existing is not None:
                    logger.debug(
                        "Skipping duplicate suggestion instrument=%s org=%s",
                        inst_id,
                        run.organization_id,
                    )
                    continue

                llm_score = float(suggestion.get("score", 0))
                quant_score = await self._compute_quantitative_score(session, listing_uuid, issuer_uuid)

                quantize_4 = Decimal("0.0001")
                final_score = Decimal(str(round((llm_score * 0.4 + quant_score * 0.6), 4)))
                record = ExplorationSuggestionRecord(
                    id=uuid.uuid4(),
                    exploration_run_id=run.id,
                    organization_id=run.organization_id,
                    instrument_id=inst_uuid,
                    issuer_id=issuer_uuid,
                    ticker=str(suggestion.get("symbol", security.get("symbol", ""))),
                    exchange=str(security.get("exchange", "")),
                    status="new",
                    quantitative_score=final_score.quantize(quantize_4),
                    data_coverage_score=Decimal(str(suggestion.get("data_coverage", 0))).quantize(quantize_4),
                    source_discovery_score=Decimal(str(suggestion.get("source_discovery", 0))).quantize(quantize_4),
                    rationale=str(suggestion.get("rationale", "")),
                    signals=suggestion.get("signals", []),
                    risks=suggestion.get("risks", []),
                    source_snapshot=suggestion.get("source_snapshot", []),
                    expires_at=_now() + timedelta(days=30),
                )
                session.add(record)
                suggestions_persisted += 1

            run.completed_at = _now()
            run.status = "succeeded"
            run.universe_size = findings.shortlist.universe_size
            run.eligible_size = findings.shortlist.eligible_size
            await session.commit()

        return ExplorationWorkflowResult(
            exploration_run_id=findings.shortlist.command.exploration_run_id,
            status="succeeded",
            universe_size=findings.shortlist.universe_size,
            eligible_size=findings.shortlist.eligible_size,
            suggestion_count=suggestions_persisted,
        )

    async def _compute_quantitative_score(
        self, session: AsyncSession, listing_id: UUID, issuer_id: UUID
    ) -> float:
        """Compute a deterministic 0-1 score from available market + fundamental data."""
        from database.models.financial_facts import FinancialFact

        scores: list[float] = []

        vol_row = (
            await session.execute(
                sa.select(sa.func.avg(MarketBar.volume)).where(
                    MarketBar.listing_id == listing_id,
                    MarketBar.bar_at >= _now() - timedelta(days=30),
                )
            )
        ).scalar()
        if vol_row and vol_row > 0:
            scores.append(min(float(vol_row) / 1_000_000, 1.0))
        else:
            scores.append(0.0)

        spread_row = (
            await session.execute(
                sa.select(
                    sa.func.abs(MarketQuote.ask_price - MarketQuote.bid_price)
                    / sa.func.nullif(MarketQuote.bid_price, 0)
                )
                .where(
                    MarketQuote.listing_id == listing_id,
                    MarketQuote.quoted_at >= _now() - timedelta(days=5),
                )
                .order_by(MarketQuote.quoted_at.desc())
                .limit(1)
            )
        ).scalar()
        if spread_row is not None:
            scores.append(max(0.0, 1.0 - float(spread_row) * 10))
        else:
            scores.append(0.5)

        fact_count = (
            await session.execute(
                sa.select(sa.func.count(FinancialFact.id)).where(FinancialFact.issuer_id == issuer_id)
            )
        ).scalar()
        scores.append(min((fact_count or 0) / 100, 1.0))

        source_count = (
            await session.execute(
                sa.select(sa.func.count(CandidateSourceRecord.id)).where(
                    CandidateSourceRecord.candidate_id.in_(
                        sa.select(InvestmentCandidateRecord.id).where(InvestmentCandidateRecord.issuer_id == issuer_id)
                    )
                )
            )
        ).scalar()
        scores.append(min((source_count or 0) / 5, 1.0))

        return sum(scores) / len(scores) if scores else 0.0

    # ------------------------------------------------------------------
    # Phase 8 — Suggestion Expiration & Restricted List
    # ------------------------------------------------------------------

    async def expire_stale_suggestions(self) -> int:
        """Mark suggestions past their expiration date as expired. Returns count expired."""
        async with self._db.session() as session:
            now = _now()
            result = await session.execute(
                sa.update(ExplorationSuggestionRecord)
                .where(
                    ExplorationSuggestionRecord.status.in_(["new", "reviewed"]),
                    ExplorationSuggestionRecord.expires_at.isnot(None),
                    ExplorationSuggestionRecord.expires_at < now,
                )
                .values(status="expired")
            )
            await session.commit()
            return int(result.rowcount)  # type: ignore[attr-defined]

    async def apply_restricted_list_block(self, restricted_instrument_ids: list[UUID]) -> int:
        """Mark suggestions for restricted instruments as blocked. Returns count blocked."""
        if not restricted_instrument_ids:
            return 0
        async with self._db.session() as session:
            result = await session.execute(
                sa.update(ExplorationSuggestionRecord)
                .where(
                    ExplorationSuggestionRecord.instrument_id.in_(restricted_instrument_ids),
                    ExplorationSuggestionRecord.status.in_(["new", "reviewed"]),
                )
                .values(status="blocked")
            )
            await session.commit()
            return int(result.rowcount)  # type: ignore[attr-defined]


async def create_production_runtime(db: DatabaseRuntime) -> ProductionCandidateRuntime:
    import boto3

    from ia_investing.data.raw_zone import S3ImmutableObjectStore
    from ia_investing.platform.http.safe_client import EgressPolicy
    from ia_investing.settings import get_settings

    settings = get_settings()
    http_client = SafeHttpClient(policy=EgressPolicy())

    s3_client = boto3.client(
        "s3",
        endpoint_url=settings.storage.endpoint,
        aws_access_key_id=settings.storage.access_key.get_secret_value(),
        aws_secret_access_key=settings.storage.secret_key.get_secret_value(),
        region_name="us-east-1",
    )
    object_store = S3ImmutableObjectStore(s3_client, settings.storage.bucket)

    return ProductionCandidateRuntime(db=db, http_client=http_client, object_store=object_store)
