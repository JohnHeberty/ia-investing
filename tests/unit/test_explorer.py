from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from ia_investing.candidate_intelligence.contracts import (
    AutonomousExplorerOutput,
    ExplorerCandidateFinding,
)
from ia_investing.candidate_intelligence.enums import ExplorationRunStatus
from ia_investing.candidate_intelligence.explorer import (
    AutonomousExplorationOrchestrator,
    ScreenedSecurity,
    UniverseSecurity,
)
from ia_investing.candidate_intelligence.models import ExplorationRun, utcnow
from ia_investing.candidate_intelligence.repositories import (
    InMemoryCandidateRepository,
    InMemoryExplorationRepository,
)


class Universe:
    def __init__(self, securities):
        self.securities = securities

    async def snapshot(self, **_kwargs):
        return self.securities


class Screener:
    async def screen(self, universe, **_kwargs):
        return tuple(
            ScreenedSecurity(
                security=item,
                quantitative_score=Decimal("0.85"),
                signals=("quality",),
                risk_flags=(),
            )
            for item in universe
        )


class Agent:
    async def investigate(self, securities, **_kwargs):
        valid = securities[0].security
        return AutonomousExplorerOutput(
            universe_size=2,
            eligible_size=1,
            methodology_summary="Teste",
            candidates=(
                ExplorerCandidateFinding(
                    ticker=valid.ticker,
                    exchange=valid.exchange,
                    legal_name=valid.legal_name,
                    quantitative_score=Decimal("0.99"),
                    data_coverage_score=Decimal("0.90"),
                    source_discovery_score=Decimal("0.80"),
                    rationale="Candidato permitido",
                ),
                ExplorerCandidateFinding(
                    ticker="FAKE3",
                    exchange="B3",
                    legal_name="Fora da shortlist",
                    quantitative_score=Decimal("0.99"),
                    data_coverage_score=Decimal("0.90"),
                    source_discovery_score=Decimal("0.80"),
                    rationale="O agente tentou introduzir um ativo novo",
                ),
            ),
        )


@pytest.mark.asyncio
async def test_explorer_cannot_introduce_security_outside_shortlist() -> None:
    organization_id = uuid4()
    security = UniverseSecurity(
        instrument_id=uuid4(),
        issuer_id=uuid4(),
        ticker="ABCD3",
        exchange="B3",
        legal_name="Companhia ABCD",
        cnpj="00.000.000/0001-00",
        cvm_code="12345",
        average_daily_liquidity=Decimal("10000000"),
        active=True,
        restricted=False,
        data_coverage_score=Decimal("0.90"),
    )
    repository = InMemoryExplorationRepository()
    run = ExplorationRun(
        id=uuid4(),
        organization_id=organization_id,
        status=ExplorationRunStatus.QUEUED,
        strategy_codes=("quality",),
        requested_by="john",
        created_at=utcnow(),
        data_as_of=datetime.now(UTC),
        minimum_liquidity=Decimal("5000000"),
        maximum_suggestions=10,
    )
    await repository.add_run(run)
    orchestrator = AutonomousExplorationOrchestrator(
        exploration_repository=repository,
        candidate_repository=InMemoryCandidateRepository(),
        universe_provider=Universe((security,)),
        screener=Screener(),
        explorer_agent=Agent(),
    )
    result = await orchestrator.run(run.id)
    saved = await repository.get_run(run.id)
    assert result.suggestion_count == 1
    assert saved.suggestions[0].identity.ticker == "ABCD3"
