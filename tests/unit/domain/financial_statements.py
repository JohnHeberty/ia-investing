"""Unit tests for ia_investing.application.financial_statements."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from ia_investing.application.financial_statements import FinancialStatementService


@pytest.mark.unit
class TestFinancialStatementService:
    @pytest.mark.asyncio
    async def test_list_metrics_basic(self):
        mock_session = AsyncMock()
        issuer_id = uuid.uuid4()
        mock_metric = SimpleNamespace(
            id=uuid.uuid4(),
            issuer_id=issuer_id,
            metric_name="receita_liquida",
            category="revenue",
            value=Decimal("1000000"),
            unit="BRL",
            reporting_period_end=date(2026, 3, 31),
            previous_value=Decimal("900000"),
            change_percent=Decimal("11.11"),
        )
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_metric]
        mock_session.execute.return_value = mock_result

        svc = FinancialStatementService(mock_session)
        result = await svc.list_metrics(issuer_id)
        assert len(result) == 1
        assert result[0]["metric_name"] == "receita_liquida"
        assert result[0]["value"] == 1000000.0

    @pytest.mark.asyncio
    async def test_list_metrics_none_value(self):
        mock_session = AsyncMock()
        mock_metric = SimpleNamespace(
            id=uuid.uuid4(),
            issuer_id=uuid.uuid4(),
            metric_name="test",
            category="cat",
            value=None,
            unit="U",
            reporting_period_end=date(2026, 1, 1),
            previous_value=None,
            change_percent=None,
        )
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_metric]
        mock_session.execute.return_value = mock_result

        svc = FinancialStatementService(mock_session)
        result = await svc.list_metrics(uuid.uuid4())
        assert result[0]["value"] is None
        assert result[0]["previous_value"] is None

    @pytest.mark.asyncio
    async def test_list_statements_basic(self):
        mock_session = AsyncMock()
        mock_stmt = SimpleNamespace(
            id=uuid.uuid4(),
            issuer_id=uuid.uuid4(),
            statement_type="DRE",
            reporting_period_start=date(2026, 1, 1),
            reporting_period_end=date(2026, 3, 31),
            currency_code="BRL",
            scale_factor=1000,
            is_audited=True,
            line_items=[],
        )
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_stmt]
        mock_session.execute.return_value = mock_result

        svc = FinancialStatementService(mock_session)
        result = await svc.list_statements(uuid.uuid4())
        assert len(result) == 1
        assert result[0]["statement_type"] == "DRE"
        assert result[0]["is_audited"] is True

    @pytest.mark.asyncio
    async def test_list_statements_with_type_filter(self):
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        svc = FinancialStatementService(mock_session)
        result = await svc.list_statements(uuid.uuid4(), statement_type="BPP")
        assert result == []

    @pytest.mark.asyncio
    async def test_list_empty(self):
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        svc = FinancialStatementService(mock_session)
        result = await svc.list_metrics(uuid.uuid4(), metric_name="x", period="2026-01-01")
        assert result == []
