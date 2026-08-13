"""Unit tests for ia_investing.application.candidate_repository."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from ia_investing.application.candidate_repository import CandidateRepository


@pytest.mark.unit
class TestCandidateRepository:
    @pytest.mark.asyncio
    async def test_get_candidate(self):
        mock_session = AsyncMock()
        org_id = uuid.uuid4()
        cand_id = uuid.uuid4()
        mock_obj = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_obj
        mock_session.execute.return_value = mock_result

        repo = CandidateRepository(mock_session, org_id)
        result = await repo.get_candidate(cand_id)
        assert result is mock_obj

    @pytest.mark.asyncio
    async def test_get_candidate_not_found(self):
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        repo = CandidateRepository(mock_session, uuid.uuid4())
        result = await repo.get_candidate(uuid.uuid4())
        assert result is None

    @pytest.mark.asyncio
    async def test_get_source(self):
        mock_session = AsyncMock()
        mock_obj = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_obj
        mock_session.execute.return_value = mock_result

        repo = CandidateRepository(mock_session, uuid.uuid4())
        result = await repo.get_source(uuid.uuid4(), uuid.uuid4())
        assert result is mock_obj

    @pytest.mark.asyncio
    async def test_get_analysis_run(self):
        mock_session = AsyncMock()
        mock_obj = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_obj
        mock_session.execute.return_value = mock_result

        repo = CandidateRepository(mock_session, uuid.uuid4())
        result = await repo.get_analysis_run(uuid.uuid4(), uuid.uuid4())
        assert result is mock_obj

    @pytest.mark.asyncio
    async def test_get_exploration_run(self):
        mock_session = AsyncMock()
        mock_obj = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_obj
        mock_session.execute.return_value = mock_result

        repo = CandidateRepository(mock_session, uuid.uuid4())
        result = await repo.get_exploration_run(uuid.uuid4())
        assert result is mock_obj

    @pytest.mark.asyncio
    async def test_get_exploration_run_not_found(self):
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        repo = CandidateRepository(mock_session, uuid.uuid4())
        result = await repo.get_exploration_run(uuid.uuid4())
        assert result is None
