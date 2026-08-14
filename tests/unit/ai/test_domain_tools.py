"""Unit tests for ia_investing.ai.domain_tools."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from ia_investing.ai.domain_tools import _safe_decimal, build_read_only_tool_registry
from ia_investing.ai.tools import (
    EvidenceSearchInput,
    FinancialMetricsInput,
    ToolRegistry,
    ValuationInput,
)


class TestSafeDecimal:
    def test_int_to_decimal(self) -> None:
        assert _safe_decimal(42) == Decimal("42")

    def test_float_to_decimal(self) -> None:
        assert _safe_decimal(3.14) == Decimal("3.14")

    def test_decimal_passthrough(self) -> None:
        d = Decimal("1.23")
        assert _safe_decimal(d) is d

    def test_string_number(self) -> None:
        assert _safe_decimal("99.9") == Decimal("99.9")

    def test_string_negative(self) -> None:
        assert _safe_decimal("-5") == Decimal("-5")

    def test_empty_string_raises(self) -> None:
        with pytest.raises(ValueError, match="non-numeric"):
            _safe_decimal("")

    def test_na_string_raises(self) -> None:
        with pytest.raises(ValueError, match="non-numeric"):
            _safe_decimal("N/A")

    def test_na_uppercase_raises(self) -> None:
        with pytest.raises(ValueError, match="non-numeric"):
            _safe_decimal("NA")

    def test_dash_string_raises(self) -> None:
        with pytest.raises(ValueError, match="non-numeric"):
            _safe_decimal("-")

    def test_none_string_raises(self) -> None:
        with pytest.raises(ValueError, match="non-numeric"):
            _safe_decimal("None")

    def test_none_type_raises(self) -> None:
        with pytest.raises((ValueError, TypeError)):
            _safe_decimal(None)

    def test_whitespace_stripped(self) -> None:
        assert _safe_decimal("  10  ") == Decimal("10")


class TestBuildReadOnlyToolRegistry:
    def test_returns_tool_registry(self) -> None:
        session = AsyncMock()
        registry = build_read_only_tool_registry(session)
        assert isinstance(registry, ToolRegistry)

    def test_registers_three_tools(self) -> None:
        session = AsyncMock()
        registry = build_read_only_tool_registry(session)
        allowed = registry.allowed({"get_financial_metrics", "search_evidence", "calculate_valuation"})
        assert len(allowed) == 3


class TestGetFinancialMetricsHandler:
    @pytest.mark.asyncio
    async def test_returns_observations(self) -> None:
        session = AsyncMock()
        registry = build_read_only_tool_registry(session)

        row = {
            "id": uuid4(),
            "metric_name": "revenue",
            "reporting_period_id": uuid4(),
            "value": Decimal("1000"),
            "value_status": "actual",
            "data_as_of": MagicMock(isoformat=MagicMock(return_value="2026-01-01T00:00:00")),
            "quality_score": Decimal("0.95"),
        }
        mock_result = MagicMock()
        mock_result.mappings.return_value = [row]
        session.execute = AsyncMock(return_value=mock_result)

        tool = registry.allowed({"get_financial_metrics"})["get_financial_metrics"]
        request = FinancialMetricsInput(
            issuer_id=uuid4(),
            metric_names=["revenue"],
            knowledge_cutoff=datetime(2026, 1, 1),
        )
        result = await tool.handler(request)
        assert len(result.observations) == 1

    @pytest.mark.asyncio
    async def test_with_reporting_period(self) -> None:
        session = AsyncMock()
        registry = build_read_only_tool_registry(session)

        mock_result = MagicMock()
        mock_result.mappings.return_value = []
        session.execute = AsyncMock(return_value=mock_result)

        tool = registry.allowed({"get_financial_metrics"})["get_financial_metrics"]
        request = FinancialMetricsInput(
            issuer_id=uuid4(),
            reporting_period_id=uuid4(),
            metric_names=["revenue"],
            knowledge_cutoff=datetime(2026, 1, 1),
        )
        result = await tool.handler(request)
        assert result.observations == []


class TestSearchEvidenceHandler:
    @pytest.mark.asyncio
    async def test_empty_query_raises(self) -> None:
        session = AsyncMock()
        registry = build_read_only_tool_registry(session)
        tool = registry.allowed({"search_evidence"})["search_evidence"]

        request = EvidenceSearchInput(
            case_id=uuid4(),
            query="  ",
            knowledge_cutoff=datetime(2026, 1, 1),
        )
        with pytest.raises(ValueError, match="empty"):
            await tool.handler(request)

    @pytest.mark.asyncio
    async def test_returns_evidence(self) -> None:
        session = AsyncMock()
        registry = build_read_only_tool_registry(session)

        evidence = MagicMock()
        evidence.id = uuid4()
        evidence.excerpt = "quote"
        evidence.page_start = 1
        evidence.page_end = 2
        evidence.excerpt_sha256 = "abc"
        evidence.knowledge_at = MagicMock(isoformat=MagicMock(return_value="2026-01-01T00:00:00"))
        evidence.quality_score = Decimal("0.9")

        chunk = MagicMock()
        chunk.id = uuid4()
        chunk.ordinal = 1

        mock_result = MagicMock()
        mock_result.all.return_value = [(evidence, chunk)]
        session.execute = AsyncMock(return_value=mock_result)

        tool = registry.allowed({"search_evidence"})["search_evidence"]
        request = EvidenceSearchInput(
            case_id=uuid4(),
            query="test query",
            knowledge_cutoff=datetime(2026, 1, 1),
        )
        result = await tool.handler(request)
        assert len(result.evidence) == 1
        assert result.evidence[0]["quote"] == "quote"


class TestCalculateValuationHandler:
    @pytest.mark.asyncio
    async def test_missing_assumptions_raises(self) -> None:
        session = AsyncMock()
        registry = build_read_only_tool_registry(session)
        tool = registry.allowed({"calculate_valuation"})["calculate_valuation"]

        request = ValuationInput(model_type="dcf", assumptions={"free_cash_flows": [100]})
        with pytest.raises(ValueError, match="missing"):
            await tool.handler(request)

    @pytest.mark.asyncio
    async def test_non_list_cash_flows_raises(self) -> None:
        session = AsyncMock()
        registry = build_read_only_tool_registry(session)
        tool = registry.allowed({"calculate_valuation"})["calculate_valuation"]

        request = ValuationInput(
            model_type="dcf",
            assumptions={
                "free_cash_flows": "not_a_list",
                "discount_rate": 0.1,
                "terminal_growth": 0.02,
                "net_debt": 100,
                "shares_outstanding": 50,
            },
        )
        with pytest.raises(ValueError, match="list"):
            await tool.handler(request)

    @pytest.mark.asyncio
    async def test_valid_valuation(self) -> None:
        session = AsyncMock()
        registry = build_read_only_tool_registry(session)
        tool = registry.allowed({"calculate_valuation"})["calculate_valuation"]

        request = ValuationInput(
            model_type="dcf",
            assumptions={
                "free_cash_flows": [100, 110, 120],
                "discount_rate": 0.1,
                "terminal_growth": 0.02,
                "net_debt": 50,
                "shares_outstanding": 10,
            },
        )
        result = await tool.handler(request)
        assert len(result.results) == 1
        assert result.results[0]["model_type"] == "dcf"
        assert "enterprise_value" in result.results[0]
        assert "equity_value" in result.results[0]
        assert "value_per_share" in result.results[0]
