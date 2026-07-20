"""PETR4 E2E acceptance test — exercises the full research domain lifecycle.

Validates the F3 exit criterion:
  "A pergunta de aceite sobre PETR4 é respondida por API/teste E2E."

Flow: create case → transition → add evidence + claim → verify claim →
create thesis → approve (activate) → query active_as_of.

Requires real PostgreSQL:
    docker compose --profile test up -d --wait
    pytest tests/integration/test_petr4_e2e.py -x -v
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.research import (
    ClaimEvidenceLink,
    ResearchCase,
    ResearchClaim,
    ResearchEvidence,
)
from database.models.thesis_domain import (
    ResearchThesis,
    ResearchThesisVersion,
    ThesisVersionClaim,
    ThesisVersionEvidence,
)
from ia_investing.application.research import ClaimService, CreateResearchCase, ResearchCaseService
from ia_investing.application.reviews import ResearchReviewService
from ia_investing.application.theses import ThesisService, ThesisSnapshot

_TZ = UTC
_ACTOR = "analyst-petr4"
_ALL_PERMS = frozenset({
    "research_cases:create",
    "research_cases:submit",
    "research_cases:assign",
    "research_cases:review",
    "research_cases:close",
    "research_cases:reopen",
    "research_cases:read",
    "research_assessments:create",
    "research_reviews:request",
    "research_reviews:decide",
    "research_claims:verify",
    "research_theses:create",
    "research_theses:revise",
    "research_theses:approve",
})


def _dt(y: int, m: int, d: int, h: int = 0, mi: int = 0) -> datetime:
    return datetime(y, m, d, h, mi, tzinfo=_TZ)


async def _find_issuer_id(session: AsyncSession):
    """Return an existing issuer_id from the catalog, or skip."""
    result = await session.execute(
        sa.text("SELECT id FROM issuers LIMIT 1")
    )
    row = result.first()
    if row is None:
        pytest.skip("No issuers in database — run seed/migrations")
    return row[0]


# ---------------------------------------------------------------------------
# Main E2E test
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_petr4_full_research_lifecycle(session: AsyncSession) -> None:
    """PETR4: case → transition → evidence → claim → verify → thesis → approve → query."""
    issuer_id = await _find_issuer_id(session)
    now = _dt(2026, 7, 20, 12, 0)
    correlation = uuid4()

    # ── 1. Create research case ──────────────────────────────────────────
    case_svc = ResearchCaseService(session)
    case_cmd = CreateResearchCase(
        case_type="fundamental",
        title="PETR4 — Análise Fundamentalista Q2 2026",
        priority="high",
        issuer_id=issuer_id,
        instrument_id=None,
        data_as_of=now,
        due_at=now + timedelta(days=30),
        questions=(
            "Qual é a tendência de receita líquida?",
            "A dívida líquida está em trajetória sustentável?",
        ),
    )
    case, created = await case_svc.create(
        case_cmd, _ACTOR, _ALL_PERMS, f"petr4-e2e-{uuid4()}", correlation
    )
    assert created is True
    assert case.state == "draft"
    case_id = case.id

    # ── 2. Transition: draft → triage → in_research → review ─────────────
    case = await case_svc.transition(
        case_id, "triage", 1, _ACTOR, _ALL_PERMS, correlation, "Entered triage"
    )
    assert case.state == "triage"

    case = await case_svc.transition(
        case_id, "in_research", 2, _ACTOR, _ALL_PERMS, correlation, "Research started"
    )
    assert case.state == "in_research"

    case = await case_svc.transition(
        case_id, "review", 3, _ACTOR, _ALL_PERMS, correlation, "Ready for review"
    )
    assert case.state == "review"

    # ── 3. Create evidence ───────────────────────────────────────────────
    evidence = ResearchEvidence(
        research_case_id=case_id,
        document_chunk_id=uuid4(),
        source_object_version_id=uuid4(),
        license_id=uuid4(),
        excerpt="Receita líquida do Q2 2026 foi R$ 120 bilhões, acima das expectativas de mercado.",
        excerpt_sha256="a" * 64,
        page_start=1,
        page_end=1,
        section_path=["DFP", "Demonstração do Resultado"],
        quality_score=Decimal("0.8500"),
        knowledge_at=now,
    )
    session.add(evidence)
    await session.flush()

    # ── 4. Create claim ──────────────────────────────────────────────────
    claim = ResearchClaim(
        research_case_id=case_id,
        claim_type="fact",
        text="Receita líquida Q2 2026 superou expectativa de mercado",
        text_sha256="b" * 64,
        is_material=True,
        status="draft",
        confidence=Decimal("0.8000"),
        valid_from=now,
        created_by_type="agent",
        created_by_id="filing-analyst",
    )
    session.add(claim)
    await session.flush()

    # ── 5. Link evidence → claim (supporting) ────────────────────────────
    link = ClaimEvidenceLink(
        claim_id=claim.id,
        evidence_id=evidence.id,
        stance="supporting",
    )
    session.add(link)
    await session.flush()

    # ── 6. Verify claim ──────────────────────────────────────────────────
    claim_svc = ClaimService(session)
    verified = await claim_svc.verify(
        claim.id, now, _ACTOR, _ALL_PERMS, correlation
    )
    assert verified.status == "verified"

    # ── 7. Create assessment → request review → approve review ────────────
    review_svc = ResearchReviewService(session)
    assessment = await review_svc.create_assessment(
        research_case_id=case_id,
        assessment_type="filing_analysis",
        author_type="agent",
        author_id="filing-analyst",
        schema_name="filing-review-v1",
        schema_version="1.0",
        result={"verdict": "positive", "confidence": 0.85},
        data_as_of=now,
        expires_at=now + timedelta(days=90),
        permissions=_ALL_PERMS,
    )

    review_request = await review_svc.request_review(
        assessment.id,
        reviewer_role="senior_analyst",
        requested_by=_ACTOR,
        due_at=now + timedelta(days=7),
        permissions=_ALL_PERMS,
    )

    decision = await review_svc.decide(
        review_request.id,
        decision="approved",
        reviewer_id="senior-analyst",
        reviewer_roles=frozenset({"senior_analyst"}),
        permissions=_ALL_PERMS,
        comment="Analysis is solid and well-supported.",
        reason="Evidence corroborates the claim",
        correlation_id=correlation,
    )
    assert decision.decision == "approved"

    # ── 8. Transition: review → approved ──────────────────────────────────
    case = await case_svc.transition(
        case_id, "approved", 4, _ACTOR, _ALL_PERMS, correlation, "Review approved"
    )
    assert case.state == "approved"

    # ── 9. Create thesis for PETR4 ───────────────────────────────────────
    thesis_svc = ThesisService(session)
    snapshot = ThesisSnapshot(
        summary="PETR4 está posicionada para crescimento de receita com preços de petróleo estáveis.",
        assumptions=[
            {"name": "brent_price", "value": "80 USD/bbl"},
            {"name": "production_volume", "value": "2.8 Mbpd"},
        ],
        catalysts=[
            {"text": "Dividend yield atrativo"},
            {"text": "Investimentos em pré-sal"},
        ],
        risks=[
            {"text": "Volatilidade do câmbio"},
            {"text": "Regulação ambiental"},
        ],
        invalidation_criteria=[
            {"metric": "net_debt_ebitda", "op": ">", "value": "3.0"},
            {"metric": "payout_ratio", "op": ">", "value": "1.0"},
        ],
        recommendation="buy",
        recommendation_confidence=Decimal("0.7500"),
        data_as_of=now,
        expires_at=now + timedelta(days=180),
    )

    thesis, version = await thesis_svc.create_draft(
        issuer_id=issuer_id,
        instrument_id=None,
        snapshot=snapshot,
        actor_subject=_ACTOR,
        permissions=_ALL_PERMS,
        evidence_ids=[evidence.id],
        claim_ids=[claim.id],
    )
    assert thesis.status == "draft"
    assert version.version_number == 1
    assert version.status == "draft"
    thesis_id = thesis.id
    version_id = version.id

    # ── 10. Activate thesis (requires approved review decision) ───────────
    active_version = await thesis_svc.activate(
        version_id=version_id,
        review_decision_id=decision.id,
        actor_subject="senior-analyst",  # must match the reviewer
        permissions=_ALL_PERMS,
        correlation_id=correlation,
    )
    assert active_version.status == "active"
    assert active_version.approved_by == "senior-analyst"

    # Verify thesis status updated
    await session.refresh(thesis)
    assert thesis.status == "active"

    # ── 11. Query active_as_of ───────────────────────────────────────────
    queried = await thesis_svc.active_as_of(thesis_id, now + timedelta(days=1))
    assert queried is not None
    assert queried.id == version_id
    assert queried.recommendation == "buy"
    assert queried.recommendation_confidence == Decimal("0.7500")

    # ── 12. Verify DB state ──────────────────────────────────────────────
    db_case = await session.get(ResearchCase, case_id)
    assert db_case is not None
    assert db_case.state == "approved"
    assert db_case.lock_version == 4

    evidence_count = await session.scalar(
        sa.select(sa.func.count(ResearchEvidence.id)).where(
            ResearchEvidence.research_case_id == case_id
        )
    )
    assert evidence_count == 1

    claim_count = await session.scalar(
        sa.select(sa.func.count(ResearchClaim.id)).where(
            ResearchClaim.research_case_id == case_id
        )
    )
    assert claim_count == 1

    db_claim = await session.get(ResearchClaim, claim.id)
    assert db_claim is not None
    assert db_claim.status == "verified"

    db_thesis = await session.get(ResearchThesis, thesis_id)
    assert db_thesis is not None
    assert db_thesis.status == "active"

    version_count = await session.scalar(
        sa.select(sa.func.count(ResearchThesisVersion.id)).where(
            ResearchThesisVersion.thesis_id == thesis_id
        )
    )
    assert version_count == 1

    # ThesisVersionClaim link exists
    thesis_claim_link = await session.scalar(
        sa.select(sa.func.count(ThesisVersionClaim.claim_id)).where(
            ThesisVersionClaim.thesis_version_id == version_id
        )
    )
    assert thesis_claim_link == 1

    # ThesisVersionEvidence link exists
    thesis_evidence_link = await session.scalar(
        sa.select(sa.func.count(ThesisVersionEvidence.evidence_id)).where(
            ThesisVersionEvidence.thesis_version_id == version_id
        )
    )
    assert thesis_evidence_link == 1

    await session.commit()


# ---------------------------------------------------------------------------
# Rejection path test
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_petr4_case_rejection_and_reopen(session: AsyncSession) -> None:
    """PETR4: case rejected → closed → reopened to triage."""
    issuer_id = await _find_issuer_id(session)
    now = _dt(2026, 7, 20, 14, 0)
    correlation = uuid4()

    case_svc = ResearchCaseService(session)
    case, _ = await case_svc.create(
        CreateResearchCase(
            case_type="technical",
            title="PETR4 — Análise Técnica",
            priority="normal",
            issuer_id=issuer_id,
            instrument_id=None,
            data_as_of=now,
            due_at=None,
            questions=("Tendência de curto prazo?",),
        ),
        _ACTOR,
        _ALL_PERMS,
        f"petr4-reject-{uuid4()}",
        correlation,
    )

    # draft → triage → in_research → review
    await case_svc.transition(case.id, "triage", 1, _ACTOR, _ALL_PERMS, correlation, "")
    await case_svc.transition(case.id, "in_research", 2, _ACTOR, _ALL_PERMS, correlation, "")
    await case_svc.transition(case.id, "review", 3, _ACTOR, _ALL_PERMS, correlation, "")

    # review → rejected
    case = await case_svc.transition(
        case.id, "rejected", 4, _ACTOR, _ALL_PERMS, correlation, "Insufficient data"
    )
    assert case.state == "rejected"

    # rejected → closed
    case = await case_svc.transition(
        case.id, "closed", 5, _ACTOR, _ALL_PERMS, correlation, "Closing rejected case"
    )
    assert case.state == "closed"

    # closed → triage (reopen)
    case = await case_svc.transition(
        case.id, "triage", 6, _ACTOR, _ALL_PERMS, correlation, "New data available"
    )
    assert case.state == "triage"

    await session.commit()
