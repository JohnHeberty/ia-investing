from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import UTC, datetime
from decimal import Decimal

import sqlalchemy as sa

from database.models.catalog import Issuer
from database.models.instrument_master import Instrument, Listing
from database.models.investment_candidates import (
    CandidateAnalysisRunRecord,
    CandidateEventRecord,
    CandidateGapRecord,
    CandidateSourceRecord,
    ExplorationRunRecord,
    ExplorationSuggestionRecord,
    InvestmentCandidateRecord,
)
from ia_investing.ai._config import (
    FUNDAMENTALIST_ANALYST,
    INVESTMENT_COMMITTEE,
    RESEARCH_COORDINATOR,
    RISK_DIRECTOR,
)
from ia_investing.ai._runner import AgentResult, AgentRunner
from ia_investing.application.instruments import InstrumentMasterService
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
from ia_investing.platform.database.runtime import DatabaseRuntime
from ia_investing.platform.http.safe_client import EgressPolicy, SafeHttpClient

logger = logging.getLogger(__name__)


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


class ProductionCandidateRuntime:
    def __init__(
        self,
        db: DatabaseRuntime,
        http_client: SafeHttpClient | None = None,
        *,
        agent_runtime_service: object | None = None,
        cvm_resolver: CVMResolver | None = None,
        b3_resolver: B3Resolver | None = None,
    ) -> None:
        self._db = db
        self._http = http_client or SafeHttpClient(policy=EgressPolicy())
        self._agent_runtime_service = agent_runtime_service
        self._cvm = cvm_resolver or CVMResolver(self._http)
        self._b3 = b3_resolver or B3Resolver(db)

    # ------------------------------------------------------------------
    # Phase 1 — Identity Resolution
    # ------------------------------------------------------------------

    async def resolve_candidate_identity(self, command: CandidateWorkflowInput) -> CandidateCheckpoint:
        async with self._db.session() as session:
            candidate = await session.get(InvestmentCandidateRecord, command.candidate_id)
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
            candidate = await session.get(InvestmentCandidateRecord, command.candidate_id)
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

                listings = (
                    (
                        await session.execute(
                            sa.select(Listing).where(
                                Listing.instrument_id == candidate.instrument_id,
                                Listing.valid_to.is_(None),
                            )
                        )
                    )
                    .scalars()
                    .all()
                )

                for listing in listings:
                    exchange_label = listing.exchange_code or "UNKNOWN"
                    sources.append(
                        {
                            "kind": f"listing:{exchange_label}",
                            "url": "",
                            "status": "verified",
                            "verification_method": "database",
                            "confidence": 1.0,
                            "official": True,
                            "discovered_by": "system",
                            "evidence": {"listing_id": str(listing.id), "exchange": exchange_label},
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
                missing_ri = all(s.get("kind") != "investor_relations" for s in sources)
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
            candidate = await session.get(InvestmentCandidateRecord, checkpoint.command.candidate_id)
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
                session.add(
                    CandidateSourceRecord(
                        candidate_id=candidate.id,
                        kind=str(src["kind"]),
                        url=str(src.get("url", "")),
                        normalized_url_hash=hashlib.sha256(str(src.get("url", "")).encode()).hexdigest(),
                        status=str(src.get("status", "discovered")),
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
        async with self._db.session() as session:
            source = await session.get(CandidateSourceRecord, command.source_id)
            if source is None:
                return CandidateSourceValidationResult(
                    candidate_id=command.candidate_id,
                    source_id=command.source_id,
                    status="rejected",
                    official=False,
                    reason="Source record not found.",
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

        content = response.content.decode("utf-8", errors="replace").lower()
        async with self._db.session() as session:
            candidate = await session.get(InvestmentCandidateRecord, command.candidate_id)

            identity_signals = []
            if candidate is not None:
                if candidate.legal_name and candidate.legal_name.lower() in content:
                    identity_signals.append("legal_name")
                if candidate.trading_name and candidate.trading_name.lower() in content:
                    identity_signals.append("trading_name")
                if candidate.cnpj and candidate.cnpj in content:
                    identity_signals.append("cnpj")
                if candidate.ticker and candidate.ticker.lower() in content:
                    identity_signals.append("ticker")

            if identity_signals:
                source.official = True
                source.status = "verified"
                source.verified_at = _now()
                source.last_checked_at = _now()
                source.evidence = {
                    "status_code": response.status_code,
                    "final_url": response.final_url,
                    "redirect_chain": list(response.redirect_chain),
                    "identity_signals": identity_signals,
                }
                await session.commit()
                return CandidateSourceValidationResult(
                    candidate_id=command.candidate_id,
                    source_id=command.source_id,
                    status="verified",
                    official=True,
                    reason=f"Verified: found identity signals {', '.join(identity_signals)}",
                    resolved_gap_codes=(f"source_{source.kind}_missing",),
                )

            source.status = "rejected"
            source.last_checked_at = _now()
            source.evidence = {
                "status_code": response.status_code,
                "final_url": response.final_url,
                "reason": "No identity signals found in page content",
            }
            await session.commit()

            return CandidateSourceValidationResult(
                candidate_id=command.candidate_id,
                source_id=command.source_id,
                status="rejected",
                official=False,
                reason="No matching identity signals found. The page may belong to a different entity.",
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

        if not sources:
            return _stage_blocked(
                command,
                "document_collection",
                "No verified sources available. Complete source validation first.",
                blocker_codes=("no_verified_sources",),
            )

        collected = 0
        failed = 0
        for source in sources:
            if not source.url:
                continue
            try:
                response = await self._http.get(source.url)
                content_hash = hashlib.sha256(response.content).hexdigest()
                async with self._db.session() as session:
                    session.add(
                        CandidateEventRecord(
                            candidate_id=command.candidate_id,
                            organization_id=command.organization_id,
                            event_type="document_collected",
                            actor_type="system",
                            actor_id="candidate_runtime",
                            occurred_at=_now(),
                            aggregate_version=1,
                            payload={
                                "source_id": str(source.id),
                                "kind": source.kind,
                                "url": source.url,
                                "content_hash": content_hash,
                                "content_length": len(response.content),
                                "status_code": response.status_code,
                            },
                        )
                    )
                    await session.commit()
                collected += 1
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

        return _stage_passed(
            command,
            "document_collection",
            reason=f"Downloaded {collected} document(s), {failed} failure(s).",
            payload={"collected": collected, "failed": failed},
        )

    # ------------------------------------------------------------------
    # Phase 5 — Readiness, Validation, Analysis
    # ------------------------------------------------------------------

    async def evaluate_candidate_readiness(self, command: CandidateWorkflowInput) -> CandidateCheckpoint:
        async with self._db.session() as session:
            candidate = await session.get(InvestmentCandidateRecord, command.candidate_id)
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
            candidate = await session.get(InvestmentCandidateRecord, command.candidate_id)
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
            candidate = await session.get(InvestmentCandidateRecord, command.candidate_id)
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
        runner = AgentRunner(FUNDAMENTALIST_ANALYST)
        result: AgentResult = await runner.run(input_data)
        if result.status != "completed":
            return _stage_blocked(
                command,
                "fundamental_analysis",
                f"Fundamental analysis agent failed: {result.error_message or 'unknown error'}",
                blocker_codes=("fundamental_analysis_failed",),
            )
        async with self._db.session() as session:
            c = await session.get(InvestmentCandidateRecord, command.candidate_id)
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
            candidate = await session.get(InvestmentCandidateRecord, command.candidate_id)
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
        runner = AgentRunner(RISK_DIRECTOR)
        result: AgentResult = await runner.run(input_data)
        if result.status != "completed":
            return _stage_blocked(
                command,
                "risk_analysis",
                f"Risk analysis agent failed: {result.error_message or 'unknown error'}",
                blocker_codes=("risk_analysis_failed",),
            )
        async with self._db.session() as session:
            c = await session.get(InvestmentCandidateRecord, command.candidate_id)
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
            candidate = await session.get(InvestmentCandidateRecord, command.candidate_id)
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
        runner = AgentRunner(INVESTMENT_COMMITTEE)
        result: AgentResult = await runner.run(input_data)
        if result.status != "completed":
            return _stage_passed(
                command,
                "committee_review",
                reason=(
                    f"Committee agent had no AI provider; pack created without machine decision. {result.error_message}"
                ),
                payload={"ai_unavailable": True},
            )
        async with self._db.session() as session:
            c = await session.get(InvestmentCandidateRecord, command.candidate_id)
            if c is not None:
                session.add(
                    CandidateEventRecord(
                        candidate_id=c.id,
                        organization_id=c.organization_id,
                        event_type="committee_pack_created",
                        actor_type="system",
                        actor_id="candidate_runtime",
                        occurred_at=_now(),
                        aggregate_version=c.lock_version,
                        payload={
                            "model_used": result.model_used,
                            "decision": result.output_data if isinstance(result.output_data, dict) else {},
                        },
                    )
                )
                c.lock_version += 1
                await session.commit()
        return _stage_passed(
            command,
            "committee_review",
            reason=f"Committee pack created via {result.model_used}",
            payload={"model_used": result.model_used},
        )

    # ------------------------------------------------------------------
    # Phase 6 — Final Completion
    # ------------------------------------------------------------------

    async def complete_candidate_analysis_run(
        self,
        command: CandidateWorkflowInput,
        checkpoint: CandidateCheckpoint,
    ) -> CandidateWorkflowResult:
        async with self._db.session() as session:
            run = await session.get(CandidateAnalysisRunRecord, command.analysis_run_id)
            if run is not None:
                run.completed_at = _now()
                run.status = "blocked" if checkpoint.blocked else "succeeded"
                run.decision = "pending"
                run.blocker_codes = list(checkpoint.blocker_codes)
                run.summary = checkpoint.reason
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
        async with self._db.session() as session:
            rows = (
                await session.execute(
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
                    .distinct()
                )
            ).all()

            securities = tuple(
                {
                    "instrument_id": str(row[0]),
                    "symbol": str(row[1]),
                    "exchange": str(row[2] or ""),
                    "issuer_id": str(row[3]),
                    "issuer_name": str(row[4]),
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
        runner = AgentRunner(RESEARCH_COORDINATOR)
        result: AgentResult = await runner.run(input_data)
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
            run = await session.get(ExplorationRunRecord, findings.shortlist.command.exploration_run_id)
            if run is None:
                return ExplorationWorkflowResult(
                    exploration_run_id=findings.shortlist.command.exploration_run_id,
                    status="failed",
                    universe_size=0,
                    eligible_size=0,
                    suggestion_count=0,
                )

            security_by_id = {s["instrument_id"]: s for s in findings.shortlist.securities}

            for suggestion in findings.suggestions:
                inst_id = suggestion.get("instrument_id", "")
                if not inst_id:
                    continue
                security = security_by_id.get(inst_id)
                if security is None:
                    continue

                inst_uuid = uuid.UUID(inst_id) if isinstance(inst_id, str) else inst_id
                issuer_uuid = (
                    uuid.UUID(security["issuer_id"])
                    if isinstance(security["issuer_id"], str)
                    else security["issuer_id"]
                )
                quantize_4 = Decimal("0.0001")
                record = ExplorationSuggestionRecord(
                    id=uuid.uuid4(),
                    exploration_run_id=run.id,
                    organization_id=run.organization_id,
                    instrument_id=inst_uuid,
                    issuer_id=issuer_uuid,
                    ticker=str(suggestion.get("symbol", security.get("symbol", ""))),
                    exchange=str(security.get("exchange", "")),
                    status="new",
                    quantitative_score=Decimal(str(suggestion.get("score", 0))).quantize(quantize_4),
                    data_coverage_score=Decimal(str(suggestion.get("data_coverage", 0))).quantize(quantize_4),
                    source_discovery_score=Decimal(str(suggestion.get("source_discovery", 0))).quantize(quantize_4),
                    rationale=str(suggestion.get("rationale", "")),
                    signals=suggestion.get("signals", []),
                    risks=suggestion.get("risks", []),
                    source_snapshot=suggestion.get("source_snapshot", []),
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


async def create_production_runtime(db: DatabaseRuntime) -> ProductionCandidateRuntime:
    from ia_investing.platform.http.safe_client import EgressPolicy

    http_client = SafeHttpClient(policy=EgressPolicy())
    return ProductionCandidateRuntime(db=db, http_client=http_client)
