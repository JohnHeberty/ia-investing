"""COTAHIST data models."""

from __future__ import annotations

from datetime import date


class CotahistTrade:
    """Um registro de cotacao diaria (uma acao x um dia util)."""

    __slots__ = (
        "cod_bdi",
        "especificacao",
        "isin",
        "moeda",
        "nome_resumido",
        "num_negocios",
        "preco_abertura",
        "preco_maximo",
        "preco_medio",
        "preco_minimo",
        "preco_ultimo",
        "qtd_titulos_negociados",
        "ticker",
        "trade_date",
        "volume_financeiro",
    )

    def __init__(
        self, trade_date: date, ticker: str, cod_bdi: str = "", nome_resumido: str = "",
        especificacao: str = "", moeda: str = "R$", preco_abertura: float = 0.0,
        preco_maximo: float = 0.0, preco_minimo: float = 0.0, preco_medio: float = 0.0,
        preco_ultimo: float = 0.0, num_negocios: int = 0, qtd_titulos_negociados: int = 0,
        volume_financeiro: float = 0.0, isin: str = "",
    ):
        self.trade_date = trade_date
        self.ticker = ticker
        self.cod_bdi = cod_bdi
        self.nome_resumido = nome_resumido
        self.especificacao = especificacao
        self.moeda = moeda
        self.preco_abertura = preco_abertura
        self.preco_maximo = preco_maximo
        self.preco_minimo = preco_minimo
        self.preco_medio = preco_medio
        self.preco_ultimo = preco_ultimo
        self.num_negocios = num_negocios
        self.qtd_titulos_negociados = qtd_titulos_negociados
        self.volume_financeiro = volume_financeiro
        self.isin = isin

    def to_dict(self) -> dict[str, object]:
        return {s: getattr(self, s) for s in self.__slots__}
