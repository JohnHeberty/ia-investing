"""Conector CVM — acesso unificado a dados da Comissão de Valores Mobiliários.

Endpoints disponíveis: https://dados.cvm.gov.br/dados/"""

from __future__ import annotations

from ._cad import get_companies, get_company_by_cnpj
from ._directory import latest_period, list_files, list_periods
from ._financials import FinancialEntry, StatementType, get_dfp, get_dfp_all, get_itr
from .fca import (
    FCAGeneral,
    FCAInvestorRelations,
    FCASecurity,
    get_fca_dri,
    get_fca_geral,
    get_fca_valores_mobiliarios,
)

__all__ = [
    "FCAGeneral",
    "FCAInvestorRelations",
    "FCASecurity",
    "FinancialEntry",
    "StatementType",
    "get_companies",
    "get_company_by_cnpj",
    "get_dfp",
    "get_dfp_all",
    "get_fca_dri",
    "get_fca_geral",
    "get_fca_valores_mobiliarios",
    "get_itr",
    "latest_period",
    "list_files",
    "list_periods",
]
