"""Activities for collecting policy data from DB-driven sources."""

from __future__ import annotations

import dataclasses
import logging
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
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


SYNTHETIC_SHA256 = "a" * 64


async def _ensure_pipeline_source_version(session: AsyncSession) -> UUID:
    """Ensure a 'pipeline' source object and version exist for automated collection.

    Returns the source_object_version_id to use for ingested records.
    """
    from database.models.data_foundation import DataSource, SourceLicense, SourceObject, SourceObjectVersion

    # Find or create the pipeline internal license
    pipeline_license = await session.scalar(select(SourceLicense).where(SourceLicense.code == "pipeline-internal"))
    if pipeline_license is None:
        pipeline_license = SourceLicense(
            code="pipeline-internal",
            name="Pipeline Internal",
            terms_url=None,
            permits_redistribution=False,
            retention_days=None,
        )
        session.add(pipeline_license)
        await session.flush()

    # Find or create the pipeline data source
    pipeline_source = await session.scalar(select(DataSource).where(DataSource.code == "policy-pipeline"))
    if pipeline_source is None:
        pipeline_source = DataSource(
            code="policy-pipeline",
            name="Policy Collection Pipeline",
            base_url="internal://policy-pipeline",
            owner_role="system",
            schema_version="1.0",
            license_id=pipeline_license.id,
            is_active=True,
        )
        session.add(pipeline_source)
        await session.flush()

    # Find or create the pipeline source object
    pipeline_object = await session.scalar(
        select(SourceObject).where(
            SourceObject.source_id == pipeline_source.id,
            SourceObject.logical_uri == "policy-pipeline://collection",
        )
    )
    if pipeline_object is None:
        pipeline_object = SourceObject(
            source_id=pipeline_source.id,
            logical_uri="policy-pipeline://collection",
            object_type="pipeline",
        )
        session.add(pipeline_object)
        await session.flush()

    # Find or create the pipeline source object version (version 1)
    pipeline_version = await session.scalar(
        select(SourceObjectVersion).where(
            SourceObjectVersion.source_object_id == pipeline_object.id,
            SourceObjectVersion.version_number == 1,
        )
    )
    if pipeline_version is None:
        pipeline_version = SourceObjectVersion(
            source_object_id=pipeline_object.id,
            version_number=1,
            content_sha256=SYNTHETIC_SHA256,
            storage_key="policy-pipeline://v1",
            size_bytes=0,
            media_type="application/json",
            published_at=datetime.now(UTC),
            discovered_at=datetime.now(UTC),
        )
        session.add(pipeline_version)
        await session.flush()

    return pipeline_version.id


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


def _build_record(d: dict[str, Any], authority: str, text_keys: tuple[str, ...] = ()) -> dict[str, Any]:
    """Build a standardized record dict from a parsed policy record."""
    metadata = d.get("metadata", {}) if isinstance(d.get("metadata"), dict) else {}
    text_content = ""
    for key in text_keys:
        if metadata.get(key):
            text_content = metadata[key]
            break
    return {
        "object_type": d.get("object_type", "unknown"),
        "external_id": d.get("external_id", ""),
        "title": d.get("title", ""),
        "text_content": text_content,
        "published_at": d.get("published_at") or None,
        "authority": authority,
        "metadata": d,
    }


def _to_dict(item: Any) -> dict[str, Any]:
    """Convert a connector model or plain object to a dict."""
    if hasattr(item, "model_dump"):
        return item.model_dump()
    if hasattr(item, "__dict__"):
        return item.__dict__
    if isinstance(item, dict):
        return item
    return {}


async def _fetch_records(client: Any, authority: str, since: str | None) -> list[dict[str, Any]]:
    """Fetch raw records from the appropriate government API."""
    if authority == "camara":
        start = datetime.fromisoformat(since) if since else datetime.now(UTC) - timedelta(days=7)
        end = datetime.now(UTC)
        _payload, parsed, _next = await client.camara_proposals(start=start, end=end)
        return [_build_record(_to_dict(p), authority, ("ementa", "indexacao")) for p in parsed]
    if authority == "senado":
        since_date = datetime.fromisoformat(since).date() if since else None
        parsed = await client.senado_matters_batch(since=since_date)
        return [_build_record(_to_dict(p), authority, ("ementaMateria", "ementa")) for p in parsed]
    if authority == "dou":
        from connectors.policy._official import parse_dou_xml

        since_date = datetime.fromisoformat(since).date() if since else datetime.now(UTC).date() - timedelta(days=7)
        payloads = await client.dou_acts_since(since=since_date)
        records: list[dict[str, Any]] = []
        for payload in payloads:
            try:
                parsed_records = parse_dou_xml(payload)
                for r in parsed_records:
                    d = dataclasses.asdict(r)
                    records.append(
                        {
                            **_build_record(d, authority, ()),
                            "external_id": r.external_id,
                        }
                    )
            except Exception:
                logger.debug("Failed to parse DOU XML payload from %s", payload.url)
        return records
    return []


async def _ingest_records(
    ingester: Any,
    authority: str,
    records: list[dict[str, Any]],
    pipeline_version_id: UUID,
) -> dict[str, int]:
    """Ingest fetched records into the database. Returns count ingested."""
    ingested = 0
    for record in records:
        try:
            published_at = record.get("published_at")
            if isinstance(published_at, datetime):
                pass  # already a datetime, keep as-is
            elif isinstance(published_at, str) and published_at:
                try:
                    published_at = datetime.fromisoformat(published_at)
                except (ValueError, TypeError):
                    published_at = datetime.now(UTC)
            else:
                published_at = datetime.now(UTC)
            # Ensure timezone is present
            if published_at.tzinfo is None:
                published_at = published_at.replace(tzinfo=UTC)
            await ingester.ingest(
                authority=authority,
                object_type=record.get("object_type", "unknown"),
                external_id=record.get("external_id", ""),
                title=record.get("title", ""),
                text_content=record.get("text_content", ""),
                metadata_payload=record.get("metadata", {}),
                published_at=published_at,
                knowledge_at=datetime.now(UTC),
                source_object_version_id=pipeline_version_id,
                permissions=frozenset({"policy:write", "data:write"}),
            )
            ingested += 1
        except Exception as e:
            logger.warning("Failed to ingest record from %s: %s", authority, e, exc_info=True)
    return {"ingested": ingested}


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

            pipeline_version_id = await _ensure_pipeline_source_version(session)
            ingested_result = await _ingest_records(ingester, authority, records, pipeline_version_id)

            # Track partial failure: fetched records but none ingested
            if ingested_result["ingested"] == 0 and len(records) > 0:
                source.last_fetch_error = f"Fetched {len(records)} records but 0 ingested"
                source.last_fetch_error_at = datetime.now(UTC)
                await session.commit()
                return {"status": "partial", "authority": authority, "fetched": len(records), "ingested": 0}

            # Update success tracking
            source.last_fetched_at = datetime.now(UTC)
            source.last_fetch_error = None
            source.last_fetch_error_at = None

            return {
                "status": "completed",
                "authority": authority,
                "fetched": len(records),
                "ingested": ingested_result["ingested"],
            }

        except Exception as e:
            # Sanitize error for storage
            error_type = type(e).__name__
            error_msg = f"{error_type}: {str(e)[:200]}"

            # Only update source if session is still usable
            try:
                if session.is_active:
                    source.last_fetch_error = error_msg
                    source.last_fetch_error_at = datetime.now(UTC)
                else:
                    logger.error("Session inactive, cannot update source error tracking: %s", e)
            except Exception:
                logger.error("Failed to update source error tracking", exc_info=True)

            logger.error("Collection failed for source %s (%s)", source.id, authority, exc_info=True)
            return {"status": "failed", "authority": authority, "error": error_msg}


POLICY_SOURCE_COLLECTION_ACTIVITIES = (list_active_policy_sources, collect_from_policy_source)
