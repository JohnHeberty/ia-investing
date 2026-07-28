from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from ia_investing.integrations.production_runtime import ProductionCandidateRuntime


@pytest.fixture
def runtime():
    return ProductionCandidateRuntime.__new__(ProductionCandidateRuntime)


@pytest.fixture
def command():
    return MagicMock(
        candidate_id=uuid4(),
        organization_id=uuid4(),
        data_as_of=date(2025, 12, 31),
        correlation_id="test-correlation",
    )


def _mock_db_session(session: AsyncMock | None = None):
    """Create a mock _db with session() async context manager."""
    if session is None:
        session = AsyncMock()
    db = MagicMock()
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=session)
    ctx.__aexit__ = AsyncMock(return_value=False)
    db.session.return_value = ctx
    return db


class TestIngestFinancialData:
    @pytest.mark.asyncio
    async def test_returns_blocked_when_candidate_not_found(self, runtime, command):
        runtime._db = _mock_db_session()
        mock_repo = MagicMock()
        mock_repo.get_candidate = AsyncMock(return_value=None)

        with patch(
            "ia_investing.integrations.production_runtime.CandidateRepository",
            return_value=mock_repo,
        ):
            result = await runtime.ingest_candidate_financial_data(command)

        assert result.blocked is True
        assert "issuer_not_resolved" in result.blocker_codes

    @pytest.mark.asyncio
    async def test_returns_blocked_when_no_cnpj(self, runtime, command):
        runtime._db = _mock_db_session()
        candidate = MagicMock()
        candidate.issuer_id = uuid4()
        candidate.cnpj = None

        mock_repo = MagicMock()
        mock_repo.get_candidate = AsyncMock(return_value=candidate)

        with patch(
            "ia_investing.integrations.production_runtime.CandidateRepository",
            return_value=mock_repo,
        ):
            result = await runtime.ingest_candidate_financial_data(command)

        assert result.blocked is True
        assert "cnpj_missing" in result.blocker_codes

    @pytest.mark.asyncio
    async def test_returns_blocked_when_no_dfp_data_found(self, runtime, command):
        runtime._db = _mock_db_session()
        candidate = MagicMock()
        candidate.issuer_id = uuid4()
        candidate.cnpj = "12.345.678/0001-90"

        mock_repo = MagicMock()
        mock_repo.get_candidate = AsyncMock(return_value=candidate)

        runtime._client = AsyncMock()

        with (
            patch(
                "ia_investing.integrations.production_runtime.CandidateRepository",
                return_value=mock_repo,
            ),
            patch(
                "connectors.cvm._financials.get_dfp",
                new_callable=AsyncMock,
                return_value=[],
            ),
        ):
            result = await runtime.ingest_candidate_financial_data(command)

            assert result.blocked is True
            assert "financial_facts_missing" in result.blocker_codes
