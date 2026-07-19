from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.financial_facts import FinancialFact
from database.models.research import ResearchEvidence
from ia_investing.application.valuations import AssumptionInput, ValuationService, canonical_payload


def assumption(source_type: str = "evidence") -> AssumptionInput:
    return AssumptionInput(
        name="wacc",
        value=Decimal("0.10"),
        unit="ratio",
        horizon="5y",
        source_type=source_type,
        source_id=uuid4(),
        source_version="v1",
        approved_by="reviewer-1",
        sensitivity_low=Decimal("0.08"),
        sensitivity_high=Decimal("0.12"),
    )


def test_canonical_valuation_payload_is_stable_and_json_safe() -> None:
    cutoff = datetime(2026, 7, 18, tzinfo=UTC)
    first, first_hash = canonical_payload({"cutoff": cutoff, "value": Decimal("1.20")})
    second, second_hash = canonical_payload({"value": Decimal("1.20"), "cutoff": cutoff})

    assert first == second == {"cutoff": str(cutoff), "value": "1.20"}
    assert first_hash == second_hash


async def test_revoked_evidence_cannot_source_valuation_assumption() -> None:
    cutoff = datetime(2026, 7, 18, tzinfo=UTC)
    item = assumption()
    evidence = ResearchEvidence(
        knowledge_at=cutoff - timedelta(days=1),
        valid_until=None,
        revoked_at=cutoff - timedelta(hours=1),
    )
    session = AsyncMock(spec=AsyncSession)
    session.get.return_value = evidence

    with pytest.raises(ValueError, match="not valid at cutoff"):
        await ValuationService(session)._validate_assumption_source(item, cutoff)


async def test_quarantined_financial_fact_cannot_source_valuation_assumption() -> None:
    cutoff = datetime(2026, 7, 18, tzinfo=UTC)
    item = assumption("financial_fact")
    fact = FinancialFact(
        knowledge_at=cutoff - timedelta(days=1),
        valid_from=cutoff - timedelta(days=2),
        valid_to=None,
        value_status="reported",
        source_object_version_id=uuid4(),
    )
    session = AsyncMock(spec=AsyncSession)
    session.get.return_value = fact
    session.scalar.return_value = 1

    with pytest.raises(ValueError, match="quarantined"):
        await ValuationService(session)._validate_assumption_source(item, cutoff)


async def test_assumption_rejects_inverted_sensitivity_range() -> None:
    cutoff = datetime(2026, 7, 18, tzinfo=UTC)
    original = assumption()
    item = AssumptionInput(
        name=original.name,
        value=original.value,
        unit=original.unit,
        horizon=original.horizon,
        source_type=original.source_type,
        source_id=original.source_id,
        source_version=original.source_version,
        approved_by=original.approved_by,
        sensitivity_low=Decimal("0.12"),
        sensitivity_high=Decimal("0.08"),
    )
    session = AsyncMock(spec=AsyncSession)

    with pytest.raises(ValueError, match="invalid sensitivity"):
        await ValuationService(session)._validate_assumption_source(item, cutoff)
