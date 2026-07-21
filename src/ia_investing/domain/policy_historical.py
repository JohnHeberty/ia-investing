"""Historical outcome dataset for Brazilian political probability calibration.

This module provides synthetic historical outcomes for calibrating
political probability forecasts. Each outcome represents a real-world
pattern of legislative progression.

The data is structured to avoid temporal leakage: outcomes are filtered
by outcome_at <= knowledge_cutoff in the base_rate() function.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass(frozen=True, slots=True)
class HistoricalPoliticalOutcome:
    policy_type: str
    legal_type: str
    stage: str
    predicted_at: datetime
    outcome_at: datetime
    outcome: bool
    source: str
    description: str


HISTORICAL_OUTCOMES: tuple[HistoricalPoliticalOutcome, ...] = (
    # Projetos de lei - Câmara → Senado → Sanção
    HistoricalPoliticalOutcome(
        policy_type="tributaria",
        legal_type="projeto_lei",
        stage="committee",
        predicted_at=datetime(2020, 1, 1, tzinfo=UTC),
        outcome_at=datetime(2020, 12, 31, tzinfo=UTC),
        outcome=True,
        source="camara_historical",
        description="PL tributário aprovado em comissão e seguiu para votação em plenário",
    ),
    HistoricalPoliticalOutcome(
        policy_type="tributaria",
        legal_type="projeto_lei",
        stage="floor",
        predicted_at=datetime(2020, 6, 1, tzinfo=UTC),
        outcome_at=datetime(2020, 12, 31, tzinfo=UTC),
        outcome=True,
        source="camara_historical",
        description="PL tributário aprovado na Câmara e seguiu ao Senado",
    ),
    HistoricalPoliticalOutcome(
        policy_type="tributaria",
        legal_type="projeto_lei",
        stage="other_house",
        predicted_at=datetime(2021, 1, 1, tzinfo=UTC),
        outcome_at=datetime(2021, 12, 31, tzinfo=UTC),
        outcome=True,
        source="senado_historical",
        description="PL tributário aprovado no Senado e seguiu para sanção",
    ),
    # Decretos
    HistoricalPoliticalOutcome(
        policy_type="regulatoria",
        legal_type="decreto",
        stage="published",
        predicted_at=datetime(2022, 1, 1, tzinfo=UTC),
        outcome_at=datetime(2022, 6, 30, tzinfo=UTC),
        outcome=True,
        source="dou_historical",
        description="Decreto regulatório publicado e mantido",
    ),
    HistoricalPoliticalOutcome(
        policy_type="regulatoria",
        legal_type="decreto",
        stage="published",
        predicted_at=datetime(2022, 1, 1, tzinfo=UTC),
        outcome_at=datetime(2022, 12, 31, tzinfo=UTC),
        outcome=False,
        source="dou_historical",
        description="Decreto regulatório publicado mas revogado posteriormente",
    ),
    # Normativos BCB
    HistoricalPoliticalOutcome(
        policy_type="financeira",
        legal_type="normativo",
        stage="published",
        predicted_at=datetime(2023, 1, 1, tzinfo=UTC),
        outcome_at=datetime(2023, 6, 30, tzinfo=UTC),
        outcome=True,
        source="bcb_historical",
        description="Normativo BCB publicado e em vigor",
    ),
    # Ato oficial - DOU
    HistoricalPoliticalOutcome(
        policy_type="setorial",
        legal_type="ato_oficial",
        stage="published",
        predicted_at=datetime(2023, 6, 1, tzinfo=UTC),
        outcome_at=datetime(2023, 12, 31, tzinfo=UTC),
        outcome=True,
        source="dou_historical",
        description="Ato setorial publicado no DOU com efeitos permanentes",
    ),
    # Rejeição em comissão
    HistoricalPoliticalOutcome(
        policy_type="social",
        legal_type="projeto_lei",
        stage="committee",
        predicted_at=datetime(2021, 3, 1, tzinfo=UTC),
        outcome_at=datetime(2021, 9, 30, tzinfo=UTC),
        outcome=False,
        source="camara_historical",
        description="PL social rejeitado na comissão especial",
    ),
    # Veto presidencial
    HistoricalPoliticalOutcome(
        policy_type="tributaria",
        legal_type="projeto_lei",
        stage="approved",
        predicted_at=datetime(2022, 6, 1, tzinfo=UTC),
        outcome_at=datetime(2022, 12, 31, tzinfo=UTC),
        outcome=False,
        source="senado_historical",
        description="PL aprovado no Congresso mas veto presidencial mantido",
    ),
    # Regulamentação parcial
    HistoricalPoliticalOutcome(
        policy_type="regulatoria",
        legal_type="decreto",
        stage="regulated",
        predicted_at=datetime(2023, 1, 1, tzinfo=UTC),
        outcome_at=datetime(2023, 12, 31, tzinfo=UTC),
        outcome=True,
        source="dou_historical",
        description="Decreto regulamentado com normas complementares",
    ),
    # Projeto arquivado
    HistoricalPoliticalOutcome(
        policy_type="ambiental",
        legal_type="projeto_lei",
        stage="introduced",
        predicted_at=datetime(2020, 1, 1, tzinfo=UTC),
        outcome_at=datetime(2020, 12, 31, tzinfo=UTC),
        outcome=False,
        source="camara_historical",
        description="PL ambiental arquivado por fim de mandato legislativo",
    ),
    # Normativo suspenso
    HistoricalPoliticalOutcome(
        policy_type="financeira",
        legal_type="normativo",
        stage="published",
        predicted_at=datetime(2022, 6, 1, tzinfo=UTC),
        outcome_at=datetime(2022, 12, 31, tzinfo=UTC),
        outcome=False,
        source="bcb_historical",
        description="Normativo BCB publicado mas suspenso judicialmente",
    ),
)


def get_historical_outcomes() -> tuple[HistoricalPoliticalOutcome, ...]:
    return HISTORICAL_OUTCOMES
