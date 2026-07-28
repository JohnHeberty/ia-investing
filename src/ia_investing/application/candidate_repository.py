from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.investment_candidates import (
    CandidateAnalysisRunRecord,
    CandidateSourceRecord,
    ExplorationRunRecord,
    InvestmentCandidateRecord,
)


class CandidateRepository:
    """Tenant-scoped repository for candidate-owned entities."""

    def __init__(self, session: AsyncSession, organization_id: UUID) -> None:
        self.session = session
        self.organization_id = organization_id

    async def get_candidate(self, candidate_id: UUID) -> InvestmentCandidateRecord | None:
        """Fetch candidate only if it belongs to this organization."""
        stmt = (
            select(InvestmentCandidateRecord)
            .where(InvestmentCandidateRecord.id == candidate_id)
            .where(InvestmentCandidateRecord.organization_id == self.organization_id)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_source(self, candidate_id: UUID, source_id: UUID) -> CandidateSourceRecord | None:
        """Fetch source only if it belongs to a candidate in this organization."""
        stmt = (
            select(CandidateSourceRecord)
            .join(InvestmentCandidateRecord, CandidateSourceRecord.candidate_id == InvestmentCandidateRecord.id)
            .where(InvestmentCandidateRecord.id == candidate_id)
            .where(CandidateSourceRecord.id == source_id)
            .where(InvestmentCandidateRecord.organization_id == self.organization_id)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_analysis_run(
        self, candidate_id: UUID, analysis_run_id: UUID
    ) -> CandidateAnalysisRunRecord | None:
        """Fetch analysis run only if it belongs to a candidate in this organization."""
        stmt = (
            select(CandidateAnalysisRunRecord)
            .join(InvestmentCandidateRecord, CandidateAnalysisRunRecord.candidate_id == InvestmentCandidateRecord.id)
            .where(InvestmentCandidateRecord.id == candidate_id)
            .where(CandidateAnalysisRunRecord.id == analysis_run_id)
            .where(InvestmentCandidateRecord.organization_id == self.organization_id)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_exploration_run(self, exploration_run_id: UUID) -> ExplorationRunRecord | None:
        """Fetch exploration run only if it belongs to this organization."""
        stmt = (
            select(ExplorationRunRecord)
            .where(ExplorationRunRecord.id == exploration_run_id)
            .where(ExplorationRunRecord.organization_id == self.organization_id)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()
