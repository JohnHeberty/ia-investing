"""CVM DFP (Demonstrativo Financeiro Padronizado) e ITR (Informações Trimestrais).

DFP: demonstrativos anuais consolidados/desconsolidados.
ITR: demonstrativos trimestrais."""

from __future__ import annotations

import logging
from dataclasses import dataclass, fields
from enum import StrEnum

from ..base import HttpClient

logger = logging.getLogger(__name__)


_DFP_URL_TEMPLATE = "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/DFP/DADOS/dfp_cia_aberta_{year}.zip"
_ITR_URL_TEMPLATE = "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/ITR/DADOS/itr_cia_aberta_{year}.zip"


class StatementType(StrEnum):
    """Tipos de demonstrativo financeiro."""

    BPA_CON = "BPA_con"       # Balanço Patrimonial Ativo - Consolidado
    BPA_IND = "BPA_ind"       # Balanço Patrimonial Ativo - Individual
    BPP_CON = "BPP_con"       # Balanço Patrimonial Passivo - Consolidado
    BPP_IND = "BPP_ind"       # Balanço Patrimonial Passivo - Individual
    DRE_CON = "DRE_con"       # Demonstração de Resultado do Exercício - Consolidado
    DRE_IND = "DRE_ind"       # Demonstração de Resultado do Exercício - Individual
    DMPL_CON = "DMPL_con"     # Mutação do Patrimônio Líquido - Consolidado
    DMPL_IND = "DMPL_ind"     # Mutação do Patrimônio Líquido - Individual


@dataclass(slots=True)
class FinancialEntry:
    """Linha de demonstrativo financeiro."""

    cnpj: str
    nome_empresa: str
    cod_cvm: str
    dt_referencia: str
    versao: int = 0
    cod_conta: str = ""
    desc_conta: str = ""
    valor: float = 0.0
    moeda: str = "REAL"
    escala: str = "MIL"

    def to_dict(self) -> dict[str, object]:
        return {f.name: getattr(self, f.name) for f in fields(self)}


def _parse_valor(raw: str) -> float:
    """Parse financial value handling Brazilian number format.

    CVM uses dot as thousands separator and comma as decimal separator.
    Example: 1.234.567,89 → 1234567.89
    Some fields use dot as decimal (e.g. scale=UN): 1234.56 → 1234.56
    """
    s = raw.strip()
    if not s:
        return 0.0

    # Remove thousands separators (dots before comma or at end)
    if "," in s:
        # Comma is decimal separator — remove dots (thousands)
        s = s.replace(".", "").replace(",", ".")
    else:
        # No comma — dots could be decimal or thousands
        # If multiple dots, they're thousands separators: 1.234.567
        if s.count(".") > 1:
            s = s.replace(".", "")
        # Single dot: treat as decimal separator (keep as-is)

    try:
        return float(s)
    except ValueError:
        return 0.0



def _parse(rows: list[dict[str, str]], cnpj_filter: str | None) -> list[FinancialEntry]:
    results: list[FinancialEntry] = []
    for r in rows:
        if cnpj_filter and (r.get("CNPJ_CIA") or "").strip() != cnpj_filter.strip():
            continue

        raw_valor = (r.get("VL_CONTA") or "0").strip()
        valor = _parse_valor(raw_valor)
        if valor == 0.0 and raw_valor and raw_valor != "0":
            logger.warning(
                "Could not parse VL_CONTA=%r for CNPJ=%s, cod_conta=%s — defaulting to 0.0",
                raw_valor,
                r.get("CNPJ_CIA"),
                r.get("CD_CONTA"),
            )

        raw_versao = (r.get("VERSAO") or "0").strip() or "0"
        try:
            versao = int(raw_versao)
        except (ValueError, TypeError):
            logger.warning("Could not parse VERSAO=%r for CNPJ=%s — defaulting to 0", raw_versao, r.get("CNPJ_CIA"))
            versao = 0

        results.append(FinancialEntry(
            cnpj=(r.get("CNPJ_CIA") or "").strip(),
            nome_empresa=(r.get("DENOM_CIA") or "").strip(),
            cod_cvm=(r.get("CD_CVM") or "").strip(),
            dt_referencia=(r.get("DT_REFER") or "").strip(),
            versao=versao,
            cod_conta=(r.get("CD_CONTA") or "").strip(),
            desc_conta=(r.get("DS_CONTA") or "").strip(),
            valor=valor,
            moeda=(r.get("MOEDA") or "REAL").strip(),
            escala=(r.get("ESCALA_MOEDA") or "MIL").strip(),
        ))

    return results


async def _get_statements(
    url_template: str,
    prefix_template: str,
    year: int,
    statement: StatementType,
    cnpj: str | None,
    client: HttpClient | None,
) -> list[FinancialEntry]:
    url = url_template.format(year=year)
    from ._parser import fetch_csv_from_zip

    prefix = prefix_template.format(statement=statement.value, year=year)
    rows = await fetch_csv_from_zip(url, prefix, client=client)
    return _parse(rows, cnpj)


async def get_dfp(
    year: int,
    statement: StatementType = StatementType.DRE_CON,
    cnpj: str | None = None,
    client: HttpClient | None = None,
) -> list[FinancialEntry]:
    """Buscar demonstrativo financeiro anual (DFP)."""
    return await _get_statements(_DFP_URL_TEMPLATE, "dfp_cia_aberta_{statement}_{year}", year, statement, cnpj, client)


async def get_itr(
    year: int,
    statement: StatementType = StatementType.DRE_CON,
    cnpj: str | None = None,
    client: HttpClient | None = None,
) -> list[FinancialEntry]:
    """Buscar demonstrativo financeiro trimestral (ITR)."""
    return await _get_statements(_ITR_URL_TEMPLATE, "itr_cia_aberta_{statement}_{year}", year, statement, cnpj, client)


async def get_dfp_all(
    year: int,
    cnpj: str | None = None,
    client: HttpClient | None = None,
) -> dict[StatementType, list[FinancialEntry]]:
    """Buscar todos os demonstrativos do DFP de um ano."""
    results: dict[StatementType, list[FinancialEntry]] = {}
    for stmt in StatementType:
        logger.info("Fetching %s for year %d", stmt.value, year)
        entries = await get_dfp(year, statement=stmt, cnpj=cnpj, client=client)
        if entries:
            results[stmt] = entries

    return results
