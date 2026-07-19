"""CVM `dados.cvm.gov.br` directory listing helper.

A CVM publica tudo em paths previsíveis como:
  `/dados/FI/DOC/<PRODUTO>/DADOS/<arquivo>.zip`

Mas os períodos disponíveis (anos ou carimbos YYYYMM) mudam com o tempo.
Hard-coding ranges fica desatualizado; HTTP-HEAD para cada arquivo é desperdício.
Então raspamos o HTML index do diretório pai uma vez por chamada e deixamos a listagem nos dizer o que existe."""

from __future__ import annotations

import asyncio
import re
import time

from ..base import DEFAULT_TIMEOUT, HttpClient

_CACHE: dict[str, tuple[float, list[str]]] = {}
_CACHE_TTL = 3600.0  # 1 hour
_CACHE_MAX_SIZE = 256
_cache_lock = asyncio.Lock()

_LISTING_PATTERN = re.compile(r'<a\s+href="([^"]+\.(?:zip|csv|txt))"', re.IGNORECASE)
_PERIOD_RE = re.compile(r"(\d{4}\d{2}|\d{4})(?:\D|$)")


async def _cache_get(key: str) -> list[str] | None:
    async with _cache_lock:
        entry = _CACHE.get(key)
        if entry and (time.monotonic() - entry[0]) < _CACHE_TTL:
            return entry[1]
        return None


async def _cache_set(key: str, value: list[str]) -> None:
    async with _cache_lock:
        if len(_CACHE) >= _CACHE_MAX_SIZE:
            # Evict oldest entries
            now = time.monotonic()
            expired = [k for k, (ts, _) in _CACHE.items() if (now - ts) >= _CACHE_TTL]
            for k in expired:
                del _CACHE[k]
            # If still over limit, remove oldest remaining
            if len(_CACHE) >= _CACHE_MAX_SIZE:
                oldest_key = min(_CACHE, key=lambda k: _CACHE[k][0])
                del _CACHE[oldest_key]
        _CACHE[key] = (time.monotonic(), value)


async def list_files(
    category: str,
    product: str,
    sub: str = "DADOS",
    client: HttpClient | None = None,
) -> list[str]:
    """Listar todos os arquivos de dados em um diretório da CVM.

    Args:
        category: top-level (ex: ``"FI"``, ``"CIA_ABERTA"``).
        product: sub-category (ex: ``"DOC/CDA"``, ``"CAD"``).
        sub: subdir sob o produto (padrão ``"DADOS"``).
        client: HttpClient opcional.

    Returns: lista de nomes de arquivos ordenados.
    """
    key = f"{category}/{product}/{sub}"
    cached = await _cache_get(key)
    if cached is not None:
        return cached

    if client is None:
        client = HttpClient(timeout=DEFAULT_TIMEOUT)

    url = f"https://dados.cvm.gov.br/dados/{category}/{product}/{sub}/"
    raw = await client.get_bytes(url)
    html = raw.decode("utf-8", errors="replace")

    files = sorted(set(_LISTING_PATTERN.findall(html)))
    await _cache_set(key, files)
    return files


async def list_periods(
    category: str,
    product: str,
    client: HttpClient | None = None,
) -> list[str]:
    """Extrair carimbos de período (YYYYMM ou YYYY) da listagem."""
    files = await list_files(category, product, client=client)
    periods: set[str] = set()
    for name in files:
        match = _PERIOD_RE.search(name)
        if match:
            periods.add(match.group(1))
    return sorted(periods)


async def latest_period(
    category: str,
    product: str,
    client: HttpClient | None = None,
) -> str | None:
    """Período mais recente disponível para um produto da CVM."""
    periods = await list_periods(category, product, client=client)
    return periods[-1] if periods else None
