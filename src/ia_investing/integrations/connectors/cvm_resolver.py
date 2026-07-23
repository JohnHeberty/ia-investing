from __future__ import annotations

import csv
import io
import logging

from ia_investing.integrations.connectors.models import CVMCompanyProfile, CVMSecurityProfile
from ia_investing.platform.http.safe_client import SafeHttpClient, ValidatedHttpResponse

logger = logging.getLogger(__name__)

_CAD_CSV_URL = "https://dados.cvm.gov.br/dados/CIA_ABERTA/CAD/DADOS/cad_cia_aberta.csv"


class CVMResolver:
    def __init__(self, http_client: SafeHttpClient) -> None:
        self._http = http_client

    async def lookup_by_cnpj(self, cnpj: str) -> CVMCompanyProfile | None:
        raw = await self._fetch_cad()
        if raw is None:
            return None
        target = cnpj.strip()
        for row in raw:
            if (row.get("CNPJ") or "").strip() == target:
                return CVMCompanyProfile(
                    cnpj=row.get("CNPJ", "").strip(),
                    legal_name=row.get("Denominacao_Social", "").strip(),
                    cvm_code=row.get("Codigo_CVM", "").strip(),
                    reference_date=row.get("Data_Referencia", "").strip(),
                    sector=row.get("Setor_Atividade", "").strip() or None,
                    website=row.get("Pagina_Web", "").strip() or None,
                    issuer_status=row.get("Situacao_Emissor", "").strip() or None,
                    registration_status=row.get("Situacao_Registro_CVM", "").strip() or None,
                    registration_category=row.get("Categoria_Registro_CVM", "").strip() or None,
                )
        return None

    async def lookup_by_cvm_code(self, code: str) -> CVMCompanyProfile | None:
        raw = await self._fetch_cad()
        if raw is None:
            return None
        target = code.strip()
        for row in raw:
            if (row.get("Codigo_CVM") or "").strip() == target:
                return CVMCompanyProfile(
                    cnpj=row.get("CNPJ", "").strip(),
                    legal_name=row.get("Denominacao_Social", "").strip(),
                    cvm_code=row.get("Codigo_CVM", "").strip(),
                    reference_date=row.get("Data_Referencia", "").strip(),
                    sector=row.get("Setor_Atividade", "").strip() or None,
                    website=row.get("Pagina_Web", "").strip() or None,
                    issuer_status=row.get("Situacao_Emissor", "").strip() or None,
                    registration_status=row.get("Situacao_Registro_CVM", "").strip() or None,
                    registration_category=row.get("Categoria_Registro_CVM", "").strip() or None,
                )
        return None

    async def lookup_securities_by_cnpj(self, cnpj: str) -> list[CVMSecurityProfile]:
        return []

    async def _fetch_cad(self) -> list[dict[str, str]] | None:
        try:
            response: ValidatedHttpResponse = await self._http.get(_CAD_CSV_URL)
        except Exception as exc:
            logger.warning("CVM CAD fetch failed: %s", exc)
            return None
        if response.status_code >= 400:
            logger.warning("CVM CAD returned HTTP %s", response.status_code)
            return None
        try:
            text = response.content.decode("iso-8859-1")
        except UnicodeDecodeError:
            text = response.content.decode("utf-8", errors="replace")
        reader = csv.DictReader(io.StringIO(text), delimiter=";")
        return list(reader)
