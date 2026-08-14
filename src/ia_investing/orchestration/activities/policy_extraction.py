"""Policy extraction activities — fetch and process policy data from government APIs."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from temporalio import activity

from ia_investing.orchestration.activities._telemetry import activity_span

logger = logging.getLogger(__name__)

try:
    from ia_investing.connectors.policy._official import OfficialPolicyClient
except ImportError:
    OfficialPolicyClient = None  # type: ignore[assignment,misc]

try:
    from database.core import session_scope
    from ia_investing.application.policy_intelligence import PolicyIngestionService
except ImportError:
    session_scope = None  # type: ignore[assignment]
    PolicyIngestionService = None  # type: ignore[assignment]


@activity.defn(name="fetch_policy_objects")
async def fetch_policy_objects(params: dict[str, Any]) -> dict[str, Any]:
    """Fetch policy objects from government APIs based on authority."""
    with activity_span("fetch_policy_objects"):
        authority = params["authority"]
        since = params.get("since")

        if OfficialPolicyClient is None:
            raise RuntimeError("policy connector not available")

        client = OfficialPolicyClient()

        if authority == "camara":
            start = datetime.fromisoformat(since) if since else datetime.now(UTC) - timedelta(days=7)
            end = datetime.now(UTC)
            _payload, parsed, _next = await client.camara_proposals(start=start, end=end)
            records = [r.__dict__ for r in parsed]
        elif authority == "senado":
            since_date = datetime.fromisoformat(since).date() if since else None
            parsed = await client.senado_matters_batch(since=since_date)
            records = [
                p.model_dump() if hasattr(p, "model_dump") else (p.__dict__ if hasattr(p, "__dict__") else p)
                for p in parsed
            ]
        elif authority == "dou":
            payloads = await client.dou_acts_since(since=since)
            records = [{"type": "dou_act", "payload": p.model_dump()} for p in payloads]
        else:
            raise ValueError(f"unsupported authority: {authority}")

        return {"authority": authority, "count": len(records), "records": records}


@activity.defn(name="ingest_policy_objects")
async def ingest_policy_objects(params: dict[str, Any]) -> dict[str, Any]:
    """Ingest fetched policy objects into the database."""
    with activity_span("ingest_policy_objects"):
        if session_scope is None or PolicyIngestionService is None:
            raise RuntimeError("policy intelligence services not available")

        async with session_scope() as session:
            service = PolicyIngestionService(session)
            ingested = 0
            for record in params["records"]:
                try:
                    published_at = record.get("published_at")
                    if published_at is None:
                        published_at = datetime.now(UTC)
                    source_version_id = record.get("source_object_version_id")
                    if source_version_id is None:
                        source_version_id = uuid4()
                    await service.ingest(
                        authority=params["authority"],
                        object_type=record.get("object_type", "unknown"),
                        external_id=record.get("external_id", ""),
                        title=record.get("title", ""),
                        text_content=record.get("text_content", ""),
                        metadata_payload=record.get("metadata", {}),
                        published_at=published_at,
                        knowledge_at=datetime.now(UTC),
                        source_object_version_id=source_version_id,
                        permissions=frozenset({"policy:write", "data:write"}),
                    )
                    ingested += 1
                except Exception as exc:
                    logger.warning("Failed to ingest policy object: %s", exc)

        return {"authority": params["authority"], "ingested": ingested}


POLICY_EXTRACTION_ACTIVITIES = (
    fetch_policy_objects,
    ingest_policy_objects,
)
