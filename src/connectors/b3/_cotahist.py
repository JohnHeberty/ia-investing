"""B3 COTAHIST — séries históricas de cotações (1986+).

Formato fixo da B3, herdado desde a era mainframe IBM. Cada ZIP anual contem
um ``COTAHIST_A{YYYY}.TXT`` com um registro por acao x dia util, 245 bytes/linha,
ISO-8859-1, preços em centavos (dividir por 100).

Layout de campos:

| Pos   | Largura | Campo     | Notas                                    |
|-------|---------|-----------|------------------------------------------|
| 1-2   | 2       | TIPREG    | 00=cabeçalho, 01=registro, 99=rodapé     |
| 3-10  | 8       | DATA      | YYYYMMDD                                 |
| 11-12 | 2       | CODBDI    | código de mercado (02=lote padrão)        |
| 13-24 | 12      | CODNEG    | ticker, left-aligned                     |
| 56-58 | 3       | MODREF    | moeda referência                         |
| 59-71 | 13      | PREABE    | abertura (centavos)                      |
| 72-84 | 13      | PREMAX    | máxima                                   |
| 85-97 | 13      | PREMIN    | mínima                                   |
| 98-110| 13      | PREMED    | média                                    |
| 111-123| 13     | PREULT    | fechamento                               |
| 157-164| 8      | TOTNEG    | número de negócios                       |
| 165-180| 16     | QUATOT    | quantidade total negociada               |
| 181-200| 20     | VOLTOT    | volume financeiro (centavos)             |
| 237-248| 12     | CODISI    | ISIN                                     |

URL: ``https://bvmf.bmfbovespa.com.br/InstDados/SerHist/COTAHIST_A{year}.ZIP``"""

from __future__ import annotations

import logging
from datetime import date

from ._downloader import _fetch
from ._models import CotahistTrade
from ._parser import (  # noqa: F401
    _parse_csv_int,
    _parse_csv_price,
    _parse_date_str,
    _parse_int,
    _parse_line,
    _parse_price,
)

logger = logging.getLogger(__name__)

COTAHIST_BASE_URL = "https://bvmf.bmfbovespa.com.br/InstDados/SerHist"


async def get_cotahist_year(
    year: int, ticker: str | None = None, market_codes: list[str] | None = None,
) -> list[CotahistTrade]:
    """Ler todos os registros de um ano.

    Args:
        year: 1986+ (B3 publica desde 1986-01-02).
        ticker: filtro por CODNEG (case-insensitive). Obrigatório para chamadas
            anuais, pois o arquivo não filtrado tem ~2.6M registros.
        market_codes: whitelist de CODBDI (ex: ``["02"]`` lote padrão, ``["96"]`` fracionário).

    Returns: lista de CotahistTrade ordenada por data e ticker.
    """
    url = f"{COTAHIST_BASE_URL}/COTAHIST_A{year}.ZIP"

    if not ticker and not market_codes:
        logger.warning(
            "get_cotahist_year sem filtros retornaria ~2.6M registros. Use 'ticker' ou 'market_codes'.",
        )

    return await _fetch(url, ticker=ticker, market_codes=market_codes)


async def get_cotahist_month(
    year: int, month: int, ticker: str | None = None, market_codes: list[str] | None = None,
) -> list[CotahistTrade]:
    """Ler um mês de COTAHIST (menor e mais rápido que anual)."""
    url = f"{COTAHIST_BASE_URL}/COTAHIST_M{month:02d}{year}.ZIP"
    return await _fetch(url, ticker=ticker, market_codes=market_codes)


async def get_cotahist_day(
    year: int, month: int, day: int, ticker: str | None = None, market_codes: list[str] | None = None,
) -> list[CotahistTrade]:
    """Ler um dia útil de COTAHIST."""
    url = f"{COTAHIST_BASE_URL}/COTAHIST_D{day:02d}{month:02d}{year}.ZIP"
    return await _fetch(url, ticker=ticker, market_codes=market_codes)


async def get_cotahist_csv(
    year: int, month: int, ticker: str | None = None,
) -> list[CotahistTrade]:
    """Ler via CSV simplificado da B3 (formato mais leve).

    A B3 também publica versões em CSV para alguns períodos. Este endpoint
    tenta o formato CSV antes de cair no ZIP fix-width."""

    import csv as _csv

    from ..base import DEFAULT_TIMEOUT, HttpClient

    url = f"https://api.b3.com.br/api/MarketData/Cotahist/{ticker}/{year:04d}{month:02d}"

    try:
        client = HttpClient(timeout=DEFAULT_TIMEOUT)
        text = await client.get_text(url)
        lines = text.strip().split("\n")
        if len(lines) < 2:
            return []

        reader = _csv.DictReader(lines)
        results: list[CotahistTrade] = []
        for row in reader:
            trade_date_str = (row.get("Data") or row.get("DATE") or "").strip()
            trade_date_obj = _parse_date_str(trade_date_str)
            if not trade_date_obj:
                continue

            symbol = (row.get("Codigo") or row.get("CODNEG") or "").strip().upper()
            if ticker and symbol != ticker.upper():
                continue

            results.append(CotahistTrade(
                trade_date=trade_date_obj,
                ticker=symbol,
                cod_bdi=row.get("CODBDI", "").strip(),
                nome_resumido=row.get("Nome", "").strip(),
                especificacao=row.get("Especificacao", "").strip(),
                moeda="R$",
                preco_abertura=_parse_csv_price(row.get("Abertura") or row.get("PREABE")),
                preco_maximo=_parse_csv_price(row.get("Maxima") or row.get("PREMAX")),
                preco_minimo=_parse_csv_price(row.get("Minima") or row.get("PREMIN")),
                preco_medio=_parse_csv_price(row.get("Media") or row.get("PREMED")),
                preco_ultimo=_parse_csv_price(row.get("Fechamento") or row.get("PREULT")),
                num_negocios=_parse_csv_int(row.get("Negocios") or row.get("TOTNEG")),
                qtd_titulos_negociados=_parse_csv_int(row.get("Quantidade") or row.get("QUATOT")),
                volume_financeiro=_parse_csv_price(row.get("Volume") or row.get("VOLTOT")),
                isin=row.get("ISIN", "").strip(),
            ))

        return sorted(results, key=lambda x: (x.trade_date or date.min, x.ticker))

    except Exception as e:
        logger.warning("CSV endpoint failed for %s/%d-%d: %s", ticker, year, month, e)
        return await get_cotahist_month(year, month, ticker=ticker)


__all__ = [
    "CotahistTrade",
    "get_cotahist_csv",
    "get_cotahist_day",
    "get_cotahist_month",
    "get_cotahist_year",
]
