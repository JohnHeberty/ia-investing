"""CVM DFP (Demonstrativo Financeiro Padronizado) e ITR (Informações Trimestrais).

DFP: demonstrativos anuais consolidados/desconsolidados.
ITR: demonstrativos trimestrais."""

from __future__ import annotations

import logging
from dataclasses import dataclass, fields
from decimal import Decimal, InvalidOperation
from enum import StrEnum

from ..base import HttpClient

logger = logging.getLogger(__name__)


_DFP_URL_TEMPLATE = "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/DFP/DADOS/dfp_cia_aberta_{year}.zip"
_ITR_URL_TEMPLATE = "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/ITR/DADOS/itr_cia_aberta_{year}.zip"


class StatementType(StrEnum):
    """Tipos de demonstrativo financeiro."""

    BPA_CON = "BPA_con"  # Balanço Patrimonial Ativo - Consolidado
    BPA_IND = "BPA_ind"  # Balanço Patrimonial Ativo - Individual
    BPP_CON = "BPP_con"  # Balanço Patrimonial Passivo - Consolidado
    BPP_IND = "BPP_ind"  # Balanço Patrimonial Passivo - Individual
    DRE_CON = "DRE_con"  # Demonstração de Resultado do Exercício - Consolidado
    DRE_IND = "DRE_ind"  # Demonstração de Resultado do Exercício - Individual
    DFC_MD_CON = "DFC_MD_con"  # Fluxo de Caixa - Método Direto - Consolidado
    DFC_MD_IND = "DFC_MD_ind"  # Fluxo de Caixa - Método Direto - Individual
    DFC_MI_CON = "DFC_MI_con"  # Fluxo de Caixa - Método Indireto - Consolidado
    DFC_MI_IND = "DFC_MI_ind"  # Fluxo de Caixa - Método Indireto - Individual
    DMPL_CON = "DMPL_con"  # Mutação do Patrimônio Líquido - Consolidado
    DMPL_IND = "DMPL_ind"  # Mutação do Patrimônio Líquido - Individual
    DVA_CON = "DVA_con"  # Demonstração do Valor Adicionado - Consolidado
    DVA_IND = "DVA_ind"  # Demonstração do Valor Adicionado - Individual


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
    dt_inicio_exercicio: str = ""
    ordem_exercicio: str = ""
    grupo_demonstracao: str = ""
    coluna_demonstracao: str = ""

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
        raise ValueError("VL_CONTA is empty")

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
    except ValueError as exc:
        raise ValueError(f"invalid VL_CONTA: {raw!r}") from exc


def parse_value_status(raw: str) -> tuple[Decimal | None, str]:
    """Parse a CVM value without converting absence or parser failure into zero."""
    normalized = raw.strip()
    if not normalized:
        return None, "missing"
    if normalized.casefold() in {"n/a", "na", "não aplicável", "nao aplicavel"}:
        return None, "not_applicable"
    if normalized in {"-", "--"}:
        return None, "suppressed"
    if "," in normalized:
        normalized = normalized.replace(".", "").replace(",", ".")
    elif normalized.count(".") > 1:
        normalized = normalized.replace(".", "")
    try:
        return Decimal(normalized), "reported"
    except InvalidOperation:
        return None, "parse_error"


def _parse(rows: list[dict[str, str]], cnpj_filter: str | None) -> list[FinancialEntry]:
    results: list[FinancialEntry] = []
    for r in rows:
        if cnpj_filter and (r.get("CNPJ_CIA") or "").strip() != cnpj_filter.strip():
            continue

        raw_valor = (r.get("VL_CONTA") or "").strip()
        valor = _parse_valor(raw_valor)

        raw_versao = (r.get("VERSAO") or "").strip()
        try:
            versao = int(raw_versao)
        except (ValueError, TypeError) as exc:
            raise ValueError(f"invalid VERSAO for CNPJ={r.get('CNPJ_CIA')}: {raw_versao!r}") from exc

        results.append(
            FinancialEntry(
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
                dt_inicio_exercicio=(r.get("DT_INI_EXERC") or "").strip(),
                ordem_exercicio=(r.get("ORDEM_EXERC") or "").strip(),
                grupo_demonstracao=(r.get("GRUPO_DFP") or r.get("GRUPO_ITR") or "").strip(),
                coluna_demonstracao=(r.get("COLUNA_DF") or "").strip(),
            )
        )

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
