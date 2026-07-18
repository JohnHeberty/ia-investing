"""COTAHIST ZIP download and fixed-width parsing."""

from __future__ import annotations

import io
import logging
import zipfile
from datetime import date

from ..base import HttpClient
from ._models import CotahistTrade
from ._parser import _parse_line

logger = logging.getLogger(__name__)

RECORD_TIPREG = "01"


async def _fetch(
    url: str, *, ticker: str | None = None, market_codes: list[str] | None = None,
    client: HttpClient | None = None,
) -> list[CotahistTrade]:
    """Download e parse do ZIP da B3 com filtros inline."""

    target_ticker = ticker.upper() if ticker else None
    code_set = {c.strip().upper() for c in market_codes} if market_codes else None

    if client is None:
        client = HttpClient(timeout=60.0)

    raw = await client.get_bytes(url)

    results: list[CotahistTrade] = []

    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        for name in sorted(zf.namelist()):
            if not name.upper().endswith(".TXT"):
                continue

            logger.info("Parsing B3 file: %s", name)

            text_wrapper = io.TextIOWrapper(
                io.BytesIO(zf.read(name)), encoding="iso-8859-1"
            )

            for line in text_wrapper:
                stripped_line = line.rstrip("\r\n")

                if len(stripped_line) < 2 or stripped_line[:2] != RECORD_TIPREG:
                    continue

                if target_ticker and len(stripped_line) > 24:
                    line_ticker = stripped_line[12:24].strip().upper()
                    if line_ticker != target_ticker:
                        continue

                row = _parse_line(stripped_line)

                if row and code_set and row.cod_bdi.upper() not in {c.upper() for c in code_set}:
                    continue

                if row:
                    results.append(row)

    return sorted(results, key=lambda x: (x.trade_date or date.min, x.ticker))
