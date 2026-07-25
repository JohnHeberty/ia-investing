from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from ia_investing.integrations.connectors.cvm_resolver import CVMResolver
from ia_investing.integrations.connectors.models import CVMSecurityProfile
from ia_investing.platform.http.safe_client import EgressPolicy, SafeHttpClient


@pytest.fixture()
def http_client() -> SafeHttpClient:
    return SafeHttpClient(policy=EgressPolicy())


@pytest.fixture()
def resolver(http_client: SafeHttpClient) -> CVMResolver:
    return CVMResolver(http_client=http_client)


class TestLookupByCnpj:
    async def test_returns_profile_when_found(self, resolver: CVMResolver) -> None:
        mock_rows = [
            {
                "CNPJ": "12.345.678/0001-90",
                "Denominacao_Social": "Empresa Teste",
                "Codigo_CVM": "12345",
                "Data_Referencia": "2025-01-01",
                "Setor_Atividade": "Financeiro",
                "Pagina_Web": "https://teste.com",
                "Situacao_Emissor": "Normal",
                "Situacao_Registro_CVM": "Regular",
                "Categoria_Registro_CVM": "Integral",
            }
        ]
        with patch.object(resolver, "_fetch_cad", new_callable=AsyncMock, return_value=mock_rows):
            result = await resolver.lookup_by_cnpj("12.345.678/0001-90")

        assert result is not None
        assert result.cnpj == "12.345.678/0001-90"
        assert result.legal_name == "Empresa Teste"
        assert result.cvm_code == "12345"
        assert result.sector == "Financeiro"
        assert result.website == "https://teste.com"

    async def test_returns_none_when_not_found(self, resolver: CVMResolver) -> None:
        mock_rows = [
            {
                "CNPJ": "99.999.999/0001-99",
                "Denominacao_Social": "Outra",
                "Codigo_CVM": "99999",
                "Data_Referencia": "2025-01-01",
            }
        ]
        with patch.object(resolver, "_fetch_cad", new_callable=AsyncMock, return_value=mock_rows):
            result = await resolver.lookup_by_cnpj("00.000.000/0000-00")

        assert result is None

    async def test_returns_none_on_fetch_error(self, resolver: CVMResolver) -> None:
        with patch.object(resolver, "_fetch_cad", new_callable=AsyncMock, return_value=None):
            result = await resolver.lookup_by_cnpj("12.345.678/0001-90")
        assert result is None


class TestLookupSecuritiesByCnpj:
    async def test_returns_securities_from_fca(self, resolver: CVMResolver) -> None:
        mock_securities = [
            type(
                "FCA Security",
                (),
                {
                    "cnpj": "12.345.678/0001-90",
                    "codigo_negociacao": "TEST4",
                    "mercado": "Bolsa",
                    "segmento": "Novo Mercado",
                    "dt_inicio_negociacao": "2020-01-01",
                    "valor_mobiliario": "Ação ON",
                },
            )()
        ]
        with patch(
            "ia_investing.integrations.connectors.cvm_resolver.get_fca_valores_mobiliarios",
            new_callable=AsyncMock,
            return_value=mock_securities,
        ):
            result = await resolver.lookup_securities_by_cnpj("12.345.678/0001-90")

        assert len(result) == 1
        assert isinstance(result[0], CVMSecurityProfile)
        assert result[0].trading_code == "TEST4"
        assert result[0].market == "Bolsa"
        assert result[0].segment == "Novo Mercado"
        assert result[0].security_type == "Ação ON"

    async def test_returns_empty_on_fca_error(self, resolver: CVMResolver) -> None:
        with patch(
            "ia_investing.integrations.connectors.cvm_resolver.get_fca_valores_mobiliarios",
            new_callable=AsyncMock,
            side_effect=Exception("network error"),
        ):
            result = await resolver.lookup_securities_by_cnpj("12.345.678/0001-90")

        assert result == []

    async def test_returns_empty_when_no_securities(self, resolver: CVMResolver) -> None:
        with patch(
            "ia_investing.integrations.connectors.cvm_resolver.get_fca_valores_mobiliarios",
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = await resolver.lookup_securities_by_cnpj("12.345.678/0001-90")

        assert result == []


class TestFetchCad:
    async def test_caches_cad_response(self, resolver: CVMResolver) -> None:
        mock_response = type(
            "Response",
            (),
            {
                "status_code": 200,
                "content": "CNPJ;Denominacao_Social\n12.345.678/0001-90;Empresa\n".encode("iso-8859-1"),
            },
        )()
        mock_http = AsyncMock(get=AsyncMock(return_value=mock_response))
        resolver._http = mock_http

        result1 = await resolver._fetch_cad()
        result2 = await resolver._fetch_cad()

        assert result1 is result2
        assert mock_http.get.call_count == 1

    async def test_returns_none_on_http_error(self, resolver: CVMResolver) -> None:
        mock_http = AsyncMock(get=AsyncMock(side_effect=Exception("timeout")))
        resolver._http = mock_http
        result = await resolver._fetch_cad()
        assert result is None
