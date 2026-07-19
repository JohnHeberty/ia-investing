"""COTAHIST data models."""

from __future__ import annotations

from dataclasses import dataclass, fields
from datetime import date


@dataclass(slots=True)
class CotahistTrade:
    """Um registro de cotacao diaria (uma acao x um dia util)."""

    trade_date: date
    ticker: str
    cod_bdi: str = ""
    nome_resumido: str = ""
    especificacao: str = ""
    moeda: str = "R$"
    preco_abertura: float = 0.0
    preco_maximo: float = 0.0
    preco_minimo: float = 0.0
    preco_medio: float = 0.0
    preco_ultimo: float = 0.0
    num_negocios: int = 0
    qtd_titulos_negociados: int = 0
    volume_financeiro: float = 0.0
    isin: str = ""

    def to_dict(self) -> dict[str, object]:
        return {f.name: getattr(self, f.name) for f in fields(self)}
