"""COTAHIST line and CSV parsing functions."""

from __future__ import annotations

from datetime import date, datetime

from ._models import CotahistTrade

_LINE_WIDTH = 245
_RECORD_TIPREG = "01"


def _parse_price(slc: str) -> float:
    """Parsear campo de preço em centavos (13 bytes)."""
    s = slc.strip()
    if not s:
        return 0.0
    try:
        return int(s) / 100.0
    except ValueError:
        return 0.0


def _parse_int(slc: str) -> int:
    """Parsear campo inteiro."""
    s = slc.strip()
    if not s:
        return 0
    try:
        return int(s)
    except ValueError:
        return 0


def _format_date(slc: str) -> date | None:
    """``20240326`` → ``date(2024, 3, 26)``."""
    s = slc.strip()
    if len(s) != 8:
        return None
    try:
        return date(int(s[:4]), int(s[4:6]), int(s[6:8]))
    except (ValueError, TypeError):
        return None


def _parse_line(line: str) -> CotahistTrade | None:
    """Parsear uma linha de formato fixo. Retorna None para cabeçalho/rodapé."""
    if len(line) < _LINE_WIDTH:
        return None
    if line[0:2] != _RECORD_TIPREG:
        return None

    trade_date = _format_date(line[2:10])
    ticker = line[12:24].strip()

    if not ticker or not trade_date:
        return None

    return CotahistTrade(
        trade_date=trade_date,
        ticker=ticker.upper(),
        cod_bdi=line[10:12].strip(),
        nome_resumido=line[24:38].strip() if len(line) > 38 else "",
        especificacao=line[38:44].strip() if len(line) > 44 else "",
        moeda="R$",
        preco_abertura=_parse_price(line[58:71]),
        preco_maximo=_parse_price(line[71:84]),
        preco_minimo=_parse_price(line[84:97]),
        preco_medio=_parse_price(line[97:110]),
        preco_ultimo=_parse_price(line[110:123]),
        num_negocios=_parse_int(line[156:164]) if len(line) > 164 else 0,
        qtd_titulos_negociados=_parse_int(line[164:180]) if len(line) > 180 else 0,
        volume_financeiro=_parse_price(line[180:200]) if len(line) > 200 else 0.0,
        isin=line[236:248].strip() if len(line) > 248 else "",
    )


def _parse_date_str(s: str) -> date | None:
    """Parse date strings in common B3 CSV formats (DD/MM/YYYY, YYYY-MM-DD, YYYYMMDD)."""
    s = s.strip()
    if not s:
        return None
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%Y%m%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def _parse_csv_price(val: str | None) -> float:
    """Parse price from CSV (handles comma decimal, dot thousands separator)."""
    if not val:
        return 0.0
    s = val.strip()
    if not s:
        return 0.0
    try:
        s = s.replace(".", "").replace(",", ".")
        return float(s)
    except ValueError:
        return 0.0


def _parse_csv_int(val: str | None) -> int:
    """Parse integer from CSV (handles dot thousands separator)."""
    if not val:
        return 0
    s = val.strip()
    if not s:
        return 0
    try:
        return int(s.replace(".", ""))
    except ValueError:
        return 0
