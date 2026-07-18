from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime

from ..base import HttpClient

CVM_FNET_URL = "https://fnet.bmfbovespa.com.br/dotnet"
CVM_DOCUMENTS_URL = f"{CVM_FNET_URL}/formulario/DadosDocumento.aspx"
CVM_CALENDAR_URL = f"{CVM_FNET_URL}/formulario/CalEventos.aspx"
B3_RI_URL = "https://www.b3.com.br/pt_br/solucoes/plataformas/puma/trader-system/cotacoes-b3"


@dataclass(slots=True)
class IRDocument:
    ticker: str
    title: str
    doc_type: str
    published_at: datetime
    url: str
    content_hash: str


def _compute_hash(content: str) -> str:
    return hashlib.sha256(content.encode()).hexdigest()[:16]


def _parse_date(raw: str) -> datetime:
    for fmt in ("%d/%m/%Y %H:%M:%S", "%d/%m/%Y", "%Y-%m-%dT%H:%M:%S"):
        try:
            dt = datetime.strptime(raw.strip(), fmt)
            return dt.replace(tzinfo=UTC)
        except ValueError:
            continue
    return datetime.now(UTC)


async def fetch_ri_documents(
    ticker: str,
    client: HttpClient | None = None,
) -> list[IRDocument]:
    if client is None:
        client = HttpClient(timeout=30.0)

    params = {"noi_frame": "1", "idioma": "I", "ticker": ticker.upper()}
    raw = await client.get_text(CVM_DOCUMENTS_URL, params=params)

    documents: list[IRDocument] = []
    try:
        data = json.loads(raw) if raw.strip().startswith(("{", "[")) else []
        if isinstance(data, dict):
            data = data.get("data", [])
    except json.JSONDecodeError:
        data = []

    for item in data:
        title = item.get("nomeDocumento") or item.get("title") or ""
        link = item.get("linkDocumento") or item.get("url") or ""
        date_str = item.get("data") or item.get("publicacao") or ""
        doc_type = item.get("tipoDocumento") or item.get("tipo") or "RI"

        if not title and not link:
            continue

        published_at = _parse_date(date_str) if date_str else datetime.now(UTC)
        content_hash = _compute_hash(f"{ticker}:{title}:{link}")

        documents.append(
            IRDocument(
                ticker=ticker.upper(),
                title=title,
                doc_type=doc_type,
                published_at=published_at,
                url=link,
                content_hash=content_hash,
            )
        )

    return documents


async def fetch_ri_calendar(
    ticker: str,
    client: HttpClient | None = None,
) -> list[dict[str, str]]:
    if client is None:
        client = HttpClient(timeout=30.0)

    params = {"noi_frame": "1", "idioma": "I", "ticker": ticker.upper()}
    raw = await client.get_text(CVM_CALENDAR_URL, params=params)

    try:
        data = json.loads(raw) if raw.strip().startswith(("{", "[")) else []
        if isinstance(data, dict):
            data = data.get("data", [])
    except json.JSONDecodeError:
        data = []

    events: list[dict[str, str]] = []
    for item in data:
        event = {
            "ticker": ticker.upper(),
            "event": item.get("evento") or item.get("title") or "",
            "date": item.get("data") or item.get("dtEvento") or "",
            "description": item.get("descricao") or item.get("obs") or "",
        }
        if event["event"] or event["date"]:
            events.append(event)

    return events
