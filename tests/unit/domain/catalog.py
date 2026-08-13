"""Unit tests for ia_investing.application.catalog — IssuerCatalogService."""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from ia_investing.application.catalog import IssuerCatalogService


@pytest.mark.unit
class TestIssuerCatalogService:
    @pytest.mark.asyncio
    async def test_get_by_cnpj_found(self):
        mock_session = AsyncMock()
        mock_issuer = SimpleNamespace(
            id=uuid.uuid4(),
            name_pt="Petrobras",
            cnpj="12345678000190",
            cvm_code="1234",
            industry_id=uuid.uuid4(),
            website_ri_url="https://ri.petrobras.com.br",
            is_active=True,
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_issuer
        mock_session.execute.return_value = mock_result

        svc = IssuerCatalogService(mock_session)
        result = await svc.get_by_cnpj("12345678000190")
        assert result is not None
        assert result["name_pt"] == "Petrobras"
        assert result["cnpj"] == "12345678000190"

    @pytest.mark.asyncio
    async def test_get_by_cnpj_not_found(self):
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        svc = IssuerCatalogService(mock_session)
        result = await svc.get_by_cnpj("00000000000000")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_by_id_found(self):
        mock_session = AsyncMock()
        issuer_id = uuid.uuid4()
        mock_issuer = SimpleNamespace(
            id=issuer_id,
            name_pt="Vale",
            cnpj="98765432000190",
            cvm_code="5678",
            industry_id=None,
            website_ri_url=None,
            is_active=True,
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_issuer
        mock_session.execute.return_value = mock_result

        svc = IssuerCatalogService(mock_session)
        result = await svc.get_by_id(issuer_id)
        assert result is not None
        assert result["name_pt"] == "Vale"
        assert result["industry_id"] is None

    @pytest.mark.asyncio
    async def test_list_active(self):
        mock_session = AsyncMock()
        mock_issuers = [
            SimpleNamespace(
                id=uuid.uuid4(), name_pt="A", cnpj="111", cvm_code="1",
                website_ri_url=None, is_active=True,
            ),
            SimpleNamespace(
                id=uuid.uuid4(), name_pt="B", cnpj="222", cvm_code="2",
                website_ri_url="https://b.com", is_active=True,
            ),
        ]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_issuers
        mock_session.execute.return_value = mock_result

        svc = IssuerCatalogService(mock_session)
        result = await svc.list_active()
        assert len(result) == 2
        assert result[0]["name_pt"] == "A"

    @pytest.mark.asyncio
    async def test_list_active_with_sector(self):
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        svc = IssuerCatalogService(mock_session)
        result = await svc.list_active(sector="Energia")
        assert result == []

    @pytest.mark.asyncio
    async def test_to_dict_none_industry(self):
        mock_issuer = SimpleNamespace(
            id=uuid.uuid4(), name_pt="X", cnpj="111", cvm_code="1",
            industry_id=None, website_ri_url=None, is_active=False,
        )
        result = IssuerCatalogService._to_dict(mock_issuer)
        assert result["industry_id"] is None
        assert result["is_active"] is False
