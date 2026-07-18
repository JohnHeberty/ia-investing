"""CSV/ZIP parsing para dados da CVM. Semicolon-delimited, ISO-8859-1."""

from __future__ import annotations

import csv
import io
import zipfile

from ..base import DEFAULT_TIMEOUT, HttpClient


async def fetch_csv(url: str, client: HttpClient | None = None) -> list[dict[str, str]]:
    """Baixar e parsear um arquivo CSV da CVM.

    Args:
        url: URL completa do arquivo .csv ou .zip.
        client: HttpClient opcional para fazer o download.

    Returns: lista de dicts com colunas como chaves.
    """
    if client is None:
        client = HttpClient(timeout=DEFAULT_TIMEOUT)

    raw = await client.get_bytes(url)
    return list(csv.DictReader(io.StringIO(raw.decode("iso-8859-1")), delimiter=";"))


async def fetch_csv_from_zip(
    url: str,
    filename_contains: str | None = None,
    client: HttpClient | None = None,
) -> list[dict[str, str]]:
    """Baixar um ZIP da CVM e parsear os CSVs dentro dele.

    Args:
        url: URL do arquivo .zip.
        filename_contains: filtro opcional para nome do arquivo interno.
        client: HttpClient opcional.

    Returns: lista de dicts concatenados de todos os CSVs que batem o filtro.
    """
    if client is None:
        client = HttpClient(timeout=DEFAULT_TIMEOUT)

    raw = await client.get_bytes(url)

    results: list[dict[str, str]] = []
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        for name in sorted(zf.namelist()):
            if not name.endswith(".csv"):
                continue
            if filename_contains and filename_contains not in name:
                continue
            with zf.open(name) as f:
                reader = csv.DictReader(
                    io.StringIO(f.read().decode("iso-8859-1")),
                    delimiter=";",
                )
                results.extend(reader)
    return results
