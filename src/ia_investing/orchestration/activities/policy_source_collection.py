"""Activities for collecting policy data from DB-driven sources."""
from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from temporalio import activity

from database.core import session_scope
from database.models.policy_intelligence import PolicySource

logger = logging.getLogger(__name__)

try:
    from ia_investing.connectors.policy._official import OfficialPolicyClient
except ImportError:
    OfficialPolicyClient = None  # type: ignore[assignment,misc]

try:
    from ia_investing.application.policy_intelligence import PolicyIngestionService
except ImportError:
    PolicyIngestionService = None  # type: ignore[assignment]


@activity.defn(name="list_active_policy_sources")
async def list_active_policy_sources(params: dict[str, Any]) -> dict[str, Any]:
    """Return all active policy sources from the database."""
    async with session_scope() as session:
        stmt = select(PolicySource).where(PolicySource.is_active == True).order_by(PolicySource.authority)  # noqa: E712
        result = await session.execute(stmt)
        sources = result.scalars().all()
        return {
            "sources": [
                {
                    "id": str(s.id),
                    "authority": s.authority,
                    "name": s.name,
                    "last_fetched_at": s.last_fetched_at.isoformat() if s.last_fetched_at else None,
                }
                for s in sources
            ]
        }


async def _fetch_records(
    client: Any, authority: str, since: str | None
) -> list[dict[str, Any]]:
    """Fetch raw records from the appropriate government API."""
    if authority == "camara":
        start = datetime.fromisoformat(since) if since else datetime.now(UTC) - timedelta(days=7)
        end = datetime.now(UTC)
        _payload, parsed, _next = await client.camara_proposals(start=start, end=end)
        return [r.__dict__ for r in parsed]
    if authority == "senado":
        parsed = await client.senado_matters_batch(
            since=datetime.fromisoformat(since).date() if since else None,
        )
        return [r.__dict__ for r in parsed]
    if authority == "dou":
        since_date = (
            datetime.fromisoformat(since).date()
            if since
            else datetime.now(UTC).date() - timedelta(days=7)
        )
        _payloads = await client.dou_acts_since(since=since_date)
        return [{"type": "dou_act", "payload": p.model_dump()} for p in _payloads]
    return []


async def _ingest_records(
    ingester: Any, authority: str, records: list[dict[str, Any]]
) -> int:
    """Ingest fetched records into the database. Returns count ingested."""
    ingested = 0
    for record in records:
        try:
            published_at = record.get("published_at")
            if published_at is None:
                published_at = datetime.now(UTC)
            await ingester.ingest(
                authority=authority,
                object_type=record.get("object_type", "unknown"),
                external_id=record.get("external_id", ""),
                title=record.get("title", ""),
                text_content=record.get("text_content", ""),
                metadata_payload=record.get("metadata", {}),
                published_at=published_at,
                knowledge_at=datetime.now(UTC),
                source_object_version_id=record.get("source_object_version_id") or uuid4(),
                permissions=frozenset({"policy:write", "data:write"}),
            )
            ingested += 1
        except Exception as e:
            logger.warning("Failed to ingest record from %s: %s", authority, e)
    return ingested


@activity.defn(name="collect_from_policy_source")
async def collect_from_policy_source(params: dict[str, Any]) -> dict[str, Any]:
    """Collect data from a single policy source.

    Updates last_fetched_at on success, last_fetch_error on failure.
    """
    source_id = params["source_id"]
    since = params.get("since")

    async with session_scope() as session:
        source = await session.get(PolicySource, source_id)
        if source is None:
            return {"status": "skipped", "reason": "source not found"}
        if not source.is_active:
            return {"status": "skipped", "reason": "source inactive"}

        authority = source.authority

        if OfficialPolicyClient is None:
            return {"status": "skipped", "reason": "policy connector not available"}
        if PolicyIngestionService is None:
            return {"status": "skipped", "reason": "policy intelligence services not available"}

        client = OfficialPolicyClient()
        ingester = PolicyIngestionService(session)

        try:
            records = await _fetch_records(client, authority, since)
            if not records and authority not in ("camara", "senado", "dou"):
                return {"status": "skipped", "reason": f"unknown authority: {authority}"}

            ingested = await _ingest_records(ingester, authority, records)

            # Update success tracking
            source.last_fetched_at = datetime.now(UTC)
            source.last_fetch_error = None
            source.last_fetch_error_at = None

            return {"status": "completed", "authority": authority, "fetched": len(records), "ingested": ingested}

        except Exception as e:
            # Update error tracking
            source.last_fetch_error = str(e)[:500]
            source.last_fetch_error_at = datetime.now(UTC)
            logger.error("Collection failed for source %s (%s): %s", source.id, authority, e)
            return {"status": "failed", "authority": authority, "error": str(e)[:200]}


POLICY_SOURCE_COLLECTION_ACTIVITIES = (list_active_policy_sources, collect_from_policy_source)
