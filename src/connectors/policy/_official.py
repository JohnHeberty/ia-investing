from __future__ import annotations

import asyncio
import hashlib
import json
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

from ..base import HttpClient, HttpClientProtocol

OFFICIAL_POLICY_HOSTS = frozenset(
    {
        "dadosabertos.camara.leg.br",
        "legis.senado.leg.br",
        "www.in.gov.br",
        "inlabs.in.gov.br",
        "www.gov.br",
        "www.bcb.gov.br",
        "dadosabertos.bcb.gov.br",
        "api.bcb.gov.br",
        "apisidra.ibge.gov.br",
    }
)


@dataclass(frozen=True, slots=True)
class OfficialPolicyRecord:
    authority: str
    object_type: str
    external_id: str
    title: str
    published_at: datetime
    metadata: dict[str, object]


@dataclass(frozen=True, slots=True)
class OfficialPolicyStageRecord:
    external_id: str
    stage: str
    occurred_at: datetime
    metadata: dict[str, object]


@dataclass(frozen=True, slots=True)
class OfficialPolicyActorRecord:
    external_id: str
    display_name: str
    actor_type: str
    metadata: dict[str, object]


@dataclass(frozen=True, slots=True)
class OfficialPolicyVoteRecord:
    external_id: str
    result: str
    voted_at: datetime
    metadata: dict[str, object]


@dataclass(frozen=True, slots=True)
class OfficialLegislativeBundle:
    proposal: OfficialPolicyRecord
    version_key: str
    stages: tuple[OfficialPolicyStageRecord, ...]
    actors: tuple[OfficialPolicyActorRecord, ...]
    votes: tuple[OfficialPolicyVoteRecord, ...]
    raw_payloads: tuple[FetchedOfficialPayload, ...]


@dataclass(frozen=True, slots=True)
class FetchedOfficialPayload:
    url: str
    body: bytes
    content_sha256: str
    media_type: str
    discovered_at: datetime

    def json(self) -> dict[str, Any]:
        payload = json.loads(self.body)
        if not isinstance(payload, dict):
            raise ValueError("official API payload must be a JSON object")
        return payload


class OfficialPolicyClient:
    """Raw-first clients for allowlisted official sources."""

    def __init__(self, client: HttpClientProtocol | None = None) -> None:
        self.client = client or HttpClient(timeout=30, max_retries=3)

    async def camara_proposals(
        self, *, start: datetime, end: datetime, page: int = 1, items: int = 100
    ) -> tuple[FetchedOfficialPayload, tuple[OfficialPolicyRecord, ...], str | None]:
        url = "https://dadosabertos.camara.leg.br/api/v2/proposicoes"
        payload = await self._get(
            url,
            params={
                "dataInicio": start.date().isoformat(),
                "dataFim": end.date().isoformat(),
                "pagina": page,
                "itens": min(max(items, 1), 100),
                "ordem": "ASC",
                "ordenarPor": "id",
            },
            headers={"Accept": "application/json"},
        )
        document = payload.json()
        records = document.get("dados")
        if not isinstance(records, list):
            raise ValueError("Câmara response lacks the dados list")
        parsed = tuple(parse_camara_proposal(item) for item in records if isinstance(item, dict))
        return payload, parsed, _next_link(document)

    async def senado_matter(self, code: str) -> tuple[FetchedOfficialPayload, OfficialPolicyRecord]:
        if not code.strip():
            raise ValueError("Senado matter code is required")
        url = f"https://legis.senado.leg.br/dadosabertos/materia/{code.strip()}"
        payload = await self._get(url, headers={"Accept": "application/json"})
        document = payload.json()
        record = document.get("materia", document)
        if not isinstance(record, dict):
            raise ValueError("Senado response lacks a matter object")
        return payload, parse_senado_proposal(record)

    async def camara_proposal_bundle(self, proposal_id: str) -> OfficialLegislativeBundle:
        if not proposal_id.strip():
            raise ValueError("Câmara proposal ID is required")
        root = f"https://dadosabertos.camara.leg.br/api/v2/proposicoes/{proposal_id.strip()}"
        detail, stages, actors, votes = await asyncio.gather(
            self._get(root, headers={"Accept": "application/json"}),
            self._get(f"{root}/tramitacoes", headers={"Accept": "application/json"}),
            self._get(f"{root}/autores", headers={"Accept": "application/json"}),
            self._get(f"{root}/votacoes", headers={"Accept": "application/json"}),
        )
        proposal_payload = _object_data(detail.json(), "Câmara proposal detail")
        proposal = parse_camara_proposal(proposal_payload)
        return OfficialLegislativeBundle(
            proposal=proposal,
            version_key=f"{proposal.external_id}:{detail.content_sha256}",
            stages=tuple(parse_camara_stage(item) for item in _list_data(stages.json(), "tramitacoes")),
            actors=tuple(parse_camara_actor(item) for item in _list_data(actors.json(), "autores")),
            votes=tuple(parse_camara_vote(item) for item in _list_data(votes.json(), "votacoes")),
            raw_payloads=(detail, stages, actors, votes),
        )

    async def dou_xml(self, url: str) -> FetchedOfficialPayload:
        return await self._get(url, headers={"Accept": "application/xml"}, media_type="application/xml")

    async def _get(
        self,
        url: str,
        *,
        params: dict[str, object] | None = None,
        headers: dict[str, str] | None = None,
        media_type: str = "application/json",
    ) -> FetchedOfficialPayload:
        require_official_egress(url)
        body = await self.client.get_bytes(url, params=params, headers=headers, follow_redirects=True)
        return FetchedOfficialPayload(
            url=url,
            body=body,
            content_sha256=hashlib.sha256(body).hexdigest(),
            media_type=media_type,
            discovered_at=datetime.now(UTC),
        )


def require_official_egress(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in OFFICIAL_POLICY_HOSTS:
        raise PermissionError(f"policy connector egress is not allowlisted: {parsed.hostname}")


def parse_camara_proposal(payload: dict[str, object]) -> OfficialPolicyRecord:
    return _parse_proposal(payload, authority="camara", identifier="id", title="ementa")


def parse_senado_proposal(payload: dict[str, object]) -> OfficialPolicyRecord:
    return _parse_proposal(payload, authority="senado", identifier="codigo", title="ementa")


def _next_link(document: dict[str, Any]) -> str | None:
    links = document.get("links", [])
    if not isinstance(links, list):
        return None
    for item in links:
        if isinstance(item, dict) and item.get("rel") == "next":
            href = item.get("href")
            if isinstance(href, str):
                require_official_egress(href)
                return href
    return None


def _parse_proposal(payload: dict[str, object], *, authority: str, identifier: str, title: str) -> OfficialPolicyRecord:
    external_id = str(payload.get(identifier, "")).strip()
    title_value = str(payload.get(title, "")).strip()
    published = payload.get("dataApresentacao") or payload.get("data")
    if not external_id or not title_value or not isinstance(published, str):
        raise ValueError(f"{authority} proposal lacks required fields")
    return OfficialPolicyRecord(
        authority=authority,
        object_type="proposal",
        external_id=external_id,
        title=title_value,
        published_at=_parse_timestamp(published),
        metadata=payload,
    )


def parse_dou_act(payload: dict[str, object]) -> OfficialPolicyRecord:
    required = ("id", "titulo", "dataPublicacao", "orgao", "tipo")
    if any(not payload.get(field) for field in required):
        raise ValueError("DOU act lacks required fields")
    return OfficialPolicyRecord(
        authority=str(payload["orgao"]),
        object_type=str(payload["tipo"]),
        external_id=str(payload["id"]),
        title=str(payload["titulo"]),
        published_at=_parse_timestamp(str(payload["dataPublicacao"])),
        metadata=payload,
    )


def parse_camara_stage(payload: dict[str, object]) -> OfficialPolicyStageRecord:
    external_id = str(payload.get("sequencia", "")).strip()
    stage = str(payload.get("descricaoTramitacao", "")).strip()
    occurred_at = payload.get("dataHora")
    if not external_id or not stage or not isinstance(occurred_at, str):
        raise ValueError("Câmara stage lacks required fields")
    return OfficialPolicyStageRecord(external_id, stage, _parse_timestamp(occurred_at), payload)


def parse_camara_actor(payload: dict[str, object]) -> OfficialPolicyActorRecord:
    external_id = str(payload.get("id", "")).strip()
    name = str(payload.get("nome", "")).strip()
    actor_type = str(payload.get("tipo", "")).strip()
    if not external_id or not name or not actor_type:
        raise ValueError("Câmara actor lacks required fields")
    return OfficialPolicyActorRecord(external_id, name, actor_type, payload)


def parse_camara_vote(payload: dict[str, object]) -> OfficialPolicyVoteRecord:
    external_id = str(payload.get("id", "")).strip()
    result = str(payload.get("aprovacao", "")).strip()
    voted_at = payload.get("dataHoraRegistro")
    if not external_id or not result or not isinstance(voted_at, str):
        raise ValueError("Câmara vote lacks required fields")
    return OfficialPolicyVoteRecord(external_id, result, _parse_timestamp(voted_at), payload)


def _list_data(document: dict[str, Any], name: str) -> list[dict[str, object]]:
    rows = document.get("dados")
    if not isinstance(rows, list) or any(not isinstance(item, dict) for item in rows):
        raise ValueError(f"Câmara response lacks the {name} list")
    return rows


def _object_data(document: dict[str, Any], name: str) -> dict[str, object]:
    value = document.get("dados")
    if not isinstance(value, dict):
        raise ValueError(f"{name} lacks the dados object")
    return value


def _parse_timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed


def parse_dou_xml(payload: FetchedOfficialPayload) -> tuple[OfficialPolicyRecord, ...]:
    """Parse DOU XML payload into structured policy records."""
    try:
        root = ET.fromstring(payload.body)
    except ET.ParseError as exc:
        raise ValueError(f"DOU XML parse error: {exc}") from exc

    records: list[OfficialPolicyRecord] = []

    for item in root.iter():
        if item.tag.endswith("item") or item.tag == "doc":
            title = ""
            orgao = ""
            tipo = ""
            data_pub = ""
            external_id = ""

            for child in item:
                tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
                text = (child.text or "").strip()
                if tag in ("titulo", "title"):
                    title = text
                elif tag in ("orgao", "organ"):
                    orgao = text
                elif tag in ("tipo", "type"):
                    tipo = text
                elif tag in ("dataPublicacao", "pubDate", "data"):
                    data_pub = text
                elif tag in ("id", "num"):
                    external_id = text

            if not external_id:
                external_id = hashlib.sha256(f"{orgao}:{tipo}:{title}:{data_pub}".encode()).hexdigest()[:16]

            if title and orgao and data_pub:
                records.append(
                    OfficialPolicyRecord(
                        authority=orgao,
                        object_type=tipo or "ato_oficial",
                        external_id=external_id,
                        title=title,
                        published_at=_parse_timestamp(data_pub),
                        metadata={"raw_xml_tag": item.tag, "source_sha256": payload.content_sha256},
                    )
                )

    return tuple(records)
