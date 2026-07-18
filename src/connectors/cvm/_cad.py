"""CVM CAD — Cadastro de Companhias Abertas.

Arquivo CSV simples com dados cadastrais atualizados."""

from __future__ import annotations

from ..base import HttpClient

CAD_URL = "https://dados.cvm.gov.br/dados/CIA_ABERTA/CAD/DADOS/cad_cia_aberta.csv"


async def get_companies(
    cnpj: str | None = None, client: HttpClient | None = None,
) -> list[dict[str, str]]:
    """Listar todas as companhias abertas cadastradas na CVM.

    Args:
        cnpj: filtro opcional por CNPJ específico.
        client: HttpClient opcional.

    Returns: lista de dicts com colunas do CSV original.
    """
    from ._parser import fetch_csv

    rows = await fetch_csv(CAD_URL, client=client)

    if cnpj:
        target = cnpj.strip()
        rows = [r for r in rows if (r.get("CNPJ") or "").strip() == target]

    return rows


async def get_company_by_cnpj(
    cnpj: str, client: HttpClient | None = None,
) -> dict[str, str] | None:
    """Buscar companhia aberta por CNPJ.

    Args:
        cnpj: CNPJ da empresa (com ou sem pontuação).
        client: HttpClient opcional.

    Returns: dict com dados da empresa ou None se não encontrada.
    """
    rows = await get_companies(cnpj=cnpj, client=client)

    if not rows:
        return None

    sorted_rows = sorted(rows, key=lambda r: r.get("Data_Referencia", ""), reverse=True)
    return sorted_rows[0]
