from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest

from connectors.policy._official import (
    OfficialPolicyClient,
    parse_camara_proposal,
    parse_dou_act,
    parse_senado_proposal,
    require_official_egress,
)
from database.models.policy_intelligence import PolicyObject, PolicyObjectVersion
from ia_investing.application.policy_intelligence import PolicyIngestionService
from ia_investing.domain.policy import (
    HistoricalOutcome,
    ImpactEdge,
    base_rate,
    brier_score,
    canonical_policy_key,
    material_review_required,
    propagate_impact,
    text_diff,
    validate_policy_stage_transition,
)

FIXTURES = Path(__file__).parents[1] / "fixtures" / "policy"


class FixtureHttpClient:
    def __init__(self, responses: dict[str, bytes]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def get_bytes(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        follow_redirects: bool = True,
    ) -> bytes:
        self.calls.append((url, {"params": params, "headers": headers, "follow_redirects": follow_redirects}))
        return self.responses[url]

    async def get_text(
        self,
        url: str,
        *,
        encoding: str = "utf-8",
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> str:
        return (await self.get_bytes(url, params=params, headers=headers)).decode(encoding)


def test_official_policy_identity_keeps_legislative_houses_separate() -> None:
    assert canonical_policy_key("camara", "PL", "123") != canonical_policy_key("senado", "PL", "123")
    validate_policy_stage_transition("introduced", "committee")
    with pytest.raises(ValueError, match="invalid"):
        validate_policy_stage_transition("introduced", "published")


def test_policy_diff_and_official_contract_parsers() -> None:
    diff = text_diff("Art. 1 texto", "Art. 1 novo texto")
    assert diff["changed"] and diff["additions"] == 1 and diff["removals"] == 1
    camara = parse_camara_proposal({"id": 123, "ementa": "Altera regra", "dataApresentacao": "2026-01-01T12:00:00Z"})
    senado = parse_senado_proposal({"codigo": 123, "ementa": "Altera regra", "data": "2026-01-02"})
    dou = parse_dou_act(
        {"id": "abc", "titulo": "Resolução", "dataPublicacao": "2026-01-03", "orgao": "CVM", "tipo": "resolucao"}
    )
    assert (camara.authority, senado.authority, dou.authority) == ("camara", "senado", "CVM")
    require_official_egress("https://dadosabertos.camara.leg.br/api/v2/proposicoes")
    with pytest.raises(PermissionError, match="allowlisted"):
        require_official_egress("https://example.com/policy")


def test_base_rate_hides_future_outcomes_and_returns_interval() -> None:
    cutoff = datetime(2026, 1, 1, tzinfo=UTC)
    outcomes = (
        HistoricalOutcome("bill", "committee", cutoff - timedelta(days=20), cutoff - timedelta(days=10), True),
        HistoricalOutcome("bill", "committee", cutoff - timedelta(days=5), cutoff + timedelta(days=1), False),
    )
    estimate = base_rate(outcomes, policy_type="bill", stage="committee", knowledge_cutoff=cutoff)
    assert estimate.sample_size == 1
    assert estimate.probability == Decimal("0.6666666666666666666666666667")
    assert estimate.interval_low <= estimate.probability <= estimate.interval_high
    assert brier_score(((Decimal("0.8"), True), (Decimal("0.3"), False))) == Decimal("0.065")


def test_policy_graph_propagates_lineage_and_rejects_cycles() -> None:
    edges = (
        ImpactEdge("event", "sector", "affects", Decimal("0.8"), Decimal("0.9")),
        ImpactEdge("sector", "issuer", "exposes", Decimal("0.5"), Decimal("0.8")),
        ImpactEdge("issuer", "portfolio", "held_by", Decimal("0.1"), Decimal("1")),
    )
    results = propagate_impact("event", Decimal(1), edges)
    assert results[-1].path == ("event", "sector", "issuer", "portfolio")
    assert results[-1].impact == Decimal("0.02880")
    with pytest.raises(ValueError, match="cycle"):
        propagate_impact(
            "event",
            Decimal(1),
            (*edges, ImpactEdge("portfolio", "event", "invalid", Decimal(1), Decimal(1))),
        )


def test_material_alert_combines_exposure_freshness_and_corroboration() -> None:
    assert material_review_required(
        materiality=Decimal("0.9"),
        exposure=Decimal("0.8"),
        corroboration=Decimal("0.9"),
        freshness=Decimal("1"),
    )
    assert not material_review_required(
        materiality=Decimal("0.9"),
        exposure=Decimal("0.8"),
        corroboration=Decimal("0.1"),
        freshness=Decimal("1"),
    )


@pytest.mark.asyncio
async def test_camara_client_preserves_raw_hash_pagination_and_contract() -> None:
    url = "https://dadosabertos.camara.leg.br/api/v2/proposicoes"
    body = (FIXTURES / "camara_proposicoes_synthetic.json").read_bytes()
    transport = FixtureHttpClient({url: body})
    raw, records, next_link = await OfficialPolicyClient(transport).camara_proposals(
        start=datetime(2026, 1, 1, tzinfo=UTC), end=datetime(2026, 1, 2, tzinfo=UTC)
    )
    assert raw.body == body and len(raw.content_sha256) == 64
    assert records[0].authority == "camara" and records[0].external_id == "123"
    assert next_link == "https://dadosabertos.camara.leg.br/api/v2/proposicoes?pagina=2"
    assert transport.calls[0][1]["params"]["itens"] == 100


@pytest.mark.asyncio
async def test_senado_client_preserves_raw_and_contract() -> None:
    url = "https://legis.senado.leg.br/dadosabertos/materia/456"
    body = (FIXTURES / "senado_materia_synthetic.json").read_bytes()
    raw, record = await OfficialPolicyClient(FixtureHttpClient({url: body})).senado_matter("456")
    assert raw.body == body and record.authority == "senado" and record.external_id == "456"


@pytest.mark.asyncio
async def test_camara_bundle_preserves_version_stage_actor_vote_and_all_raw_payloads() -> None:
    root = "https://dadosabertos.camara.leg.br/api/v2/proposicoes/123"
    responses = {
        root: (FIXTURES / "camara_proposicao_detalhe_synthetic.json").read_bytes(),
        f"{root}/tramitacoes": (FIXTURES / "camara_tramitacoes_synthetic.json").read_bytes(),
        f"{root}/autores": (FIXTURES / "camara_autores_synthetic.json").read_bytes(),
        f"{root}/votacoes": (FIXTURES / "camara_votacoes_synthetic.json").read_bytes(),
    }
    bundle = await OfficialPolicyClient(FixtureHttpClient(responses)).camara_proposal_bundle("123")
    assert bundle.proposal.external_id == "123" and len(bundle.version_key.split(":")[-1]) == 64
    assert [item.external_id for item in bundle.stages] == ["1", "2"]
    assert bundle.actors[0].display_name == "Pessoa Autora Sintética"
    assert bundle.votes[0].external_id == "vote-123"
    assert len(bundle.raw_payloads) == 4 and all(len(item.content_sha256) == 64 for item in bundle.raw_payloads)


def test_dou_contract_fixture() -> None:
    import json

    payload = json.loads((FIXTURES / "dou_ato_synthetic.json").read_text(encoding="utf-8"))
    record = parse_dou_act(payload)
    assert record.authority == "CVM" and record.external_id == "fixture-789"


class PolicySessionStub:
    def __init__(self, scalars: list[object | None]) -> None:
        self.scalars = iter(scalars)
        self.added: list[object] = []

    async def scalar(self, _statement: object) -> object | None:
        return next(self.scalars)

    def add(self, value: object) -> None:
        if getattr(value, "id", None) is None:
            value.id = uuid4()  # type: ignore[attr-defined]
        self.added.append(value)

    async def flush(self) -> None:
        return None


@pytest.mark.asyncio
async def test_policy_ingestion_is_append_only_and_calculates_version_diff() -> None:
    now = datetime(2026, 1, 3, tzinfo=UTC)
    obj = PolicyObject(
        id=uuid4(),
        authority="camara",
        object_type="proposal",
        external_id="123",
        canonical_key="camara:proposal:123",
        title="Proposal",
    )
    previous = PolicyObjectVersion(
        id=uuid4(),
        policy_object_id=obj.id,
        version=1,
        text_sha256="a" * 64,
        metadata_sha256="b" * 64,
        text_content="Art. 1 texto anterior",
        metadata_payload={},
        published_at=now,
        knowledge_at=now,
        source_object_version_id=uuid4(),
    )
    session = PolicySessionStub([obj, None, previous])
    returned_obj, version, created = await PolicyIngestionService(session).ingest(  # type: ignore[arg-type]
        authority="camara",
        object_type="proposal",
        external_id="123",
        title="Proposal",
        text_content="Art. 1 texto novo",
        metadata_payload={"stage": "committee"},
        published_at=now,
        knowledge_at=now,
        source_object_version_id=uuid4(),
        permissions=frozenset({"policy:write"}),
    )
    assert returned_obj is obj and created and version.version == 2
    assert version.diff_from_previous is not None and version.diff_from_previous["changed"]
    assert session.added == [version]


@pytest.mark.asyncio
async def test_policy_ingestion_replay_returns_existing_content() -> None:
    now = datetime(2026, 1, 3, tzinfo=UTC)
    obj = PolicyObject(
        id=uuid4(),
        authority="senado",
        object_type="proposal",
        external_id="456",
        canonical_key="senado:proposal:456",
        title="Proposal",
    )
    existing = PolicyObjectVersion(
        id=uuid4(),
        policy_object_id=obj.id,
        version=1,
        text_sha256="a" * 64,
        metadata_sha256="b" * 64,
        text_content="text",
        metadata_payload={},
        published_at=now,
        knowledge_at=now,
        source_object_version_id=uuid4(),
    )
    session = PolicySessionStub([obj, existing])
    _, returned, created = await PolicyIngestionService(session).ingest(  # type: ignore[arg-type]
        authority="senado",
        object_type="proposal",
        external_id="456",
        title="Proposal",
        text_content="text",
        metadata_payload={},
        published_at=now,
        knowledge_at=now,
        source_object_version_id=uuid4(),
        permissions=frozenset({"data:write"}),
    )
    assert returned is existing and not created and session.added == []
