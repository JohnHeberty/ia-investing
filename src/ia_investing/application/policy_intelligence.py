from __future__ import annotations

import hashlib
import json
from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.policy_intelligence import (
    PolicyGraphEdge,
    PolicyGraphNode,
    PolicyObject,
    PolicyObjectVersion,
    PolicyProbabilityForecast,
    PolicyStageEvent,
)
from ia_investing.domain.policy import canonical_policy_key, text_diff


class PolicyIngestionService:
    """Append normalized official records while retaining raw-source lineage."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def ingest(
        self,
        *,
        authority: str,
        object_type: str,
        external_id: str,
        title: str,
        text_content: str,
        metadata_payload: dict[str, object],
        published_at: datetime,
        knowledge_at: datetime,
        source_object_version_id: UUID,
        permissions: frozenset[str],
    ) -> tuple[PolicyObject, PolicyObjectVersion, bool]:
        if "policy:write" not in permissions and "data:write" not in permissions:
            raise PermissionError("permission required: policy:write")
        if published_at.tzinfo is None or knowledge_at.tzinfo is None:
            raise ValueError("policy timestamps must include timezone information")
        if knowledge_at < published_at:
            raise ValueError("knowledge_at cannot precede published_at")
        key = canonical_policy_key(authority, object_type, external_id)
        obj = await self.session.scalar(sa.select(PolicyObject).where(PolicyObject.canonical_key == key))
        if obj is None:
            if not title.strip():
                raise ValueError("policy title is required")
            obj = PolicyObject(
                authority=authority.strip(),
                object_type=object_type.strip(),
                external_id=external_id.strip(),
                canonical_key=key,
                title=title.strip(),
            )
            self.session.add(obj)
            await self.session.flush()
        metadata_sha256 = hashlib.sha256(
            json.dumps(metadata_payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
        ).hexdigest()
        text_sha256 = hashlib.sha256(text_content.encode()).hexdigest()
        existing = await self.session.scalar(
            sa.select(PolicyObjectVersion).where(
                PolicyObjectVersion.policy_object_id == obj.id,
                PolicyObjectVersion.text_sha256 == text_sha256,
                PolicyObjectVersion.metadata_sha256 == metadata_sha256,
            )
        )
        if existing is not None:
            return obj, existing, False
        previous = await self.session.scalar(
            sa.select(PolicyObjectVersion)
            .where(PolicyObjectVersion.policy_object_id == obj.id)
            .order_by(PolicyObjectVersion.version.desc())
            .limit(1)
        )
        version = PolicyObjectVersion(
            policy_object_id=obj.id,
            version=1 if previous is None else previous.version + 1,
            text_sha256=text_sha256,
            metadata_sha256=metadata_sha256,
            text_content=text_content,
            metadata_payload=metadata_payload,
            diff_from_previous=None if previous is None else text_diff(previous.text_content, text_content),
            published_at=published_at,
            knowledge_at=knowledge_at,
            source_object_version_id=source_object_version_id,
        )
        self.session.add(version)
        await self.session.flush()
        return obj, version, True


class PolicyIntelligenceQueryService:
    """Point-in-time policy queries; raw and historical records remain immutable."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def events(
        self,
        *,
        as_of: datetime,
        authority: str | None = None,
        stage: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, object]]:
        if as_of.tzinfo is None:
            raise ValueError("as_of must include timezone information")
        latest_version = (
            sa.select(
                PolicyObjectVersion.policy_object_id,
                sa.func.max(PolicyObjectVersion.version).label("version"),
            )
            .where(PolicyObjectVersion.knowledge_at <= as_of)
            .group_by(PolicyObjectVersion.policy_object_id)
            .subquery()
        )
        latest_stage_time = (
            sa.select(
                PolicyStageEvent.policy_object_id,
                sa.func.max(PolicyStageEvent.knowledge_at).label("knowledge_at"),
            )
            .where(PolicyStageEvent.knowledge_at <= as_of)
            .group_by(PolicyStageEvent.policy_object_id)
            .subquery()
        )
        query = (
            sa.select(PolicyObject, PolicyObjectVersion, PolicyStageEvent)
            .join(latest_version, latest_version.c.policy_object_id == PolicyObject.id)
            .join(
                PolicyObjectVersion,
                sa.and_(
                    PolicyObjectVersion.policy_object_id == PolicyObject.id,
                    PolicyObjectVersion.version == latest_version.c.version,
                ),
            )
            .outerjoin(latest_stage_time, latest_stage_time.c.policy_object_id == PolicyObject.id)
            .outerjoin(
                PolicyStageEvent,
                sa.and_(
                    PolicyStageEvent.policy_object_id == PolicyObject.id,
                    PolicyStageEvent.knowledge_at == latest_stage_time.c.knowledge_at,
                ),
            )
            .order_by(PolicyObjectVersion.knowledge_at.desc(), PolicyObject.id)
            .limit(min(max(limit, 1), 500))
        )
        if authority:
            query = query.where(PolicyObject.authority == authority)
        if stage:
            query = query.where(PolicyStageEvent.stage == stage)
        rows = (await self.session.execute(query)).all()
        return [
            {
                "id": obj.id,
                "authority": obj.authority,
                "object_type": obj.object_type,
                "external_id": obj.external_id,
                "title": obj.title,
                "version": version.version,
                "text_sha256": version.text_sha256,
                "published_at": version.published_at,
                "knowledge_at": version.knowledge_at,
                "stage": stage_event.stage if stage_event else None,
                "as_of": as_of,
            }
            for obj, version, stage_event in rows
        ]

    async def detail(self, policy_object_id: UUID, *, as_of: datetime) -> dict[str, object]:
        events = await self.events(as_of=as_of, limit=500)
        summary = next((item for item in events if item["id"] == policy_object_id), None)
        if summary is None:
            raise LookupError("policy object not found at cutoff")
        versions = (
            await self.session.scalars(
                sa.select(PolicyObjectVersion)
                .where(
                    PolicyObjectVersion.policy_object_id == policy_object_id,
                    PolicyObjectVersion.knowledge_at <= as_of,
                )
                .order_by(PolicyObjectVersion.version)
            )
        ).all()
        forecasts = (
            await self.session.scalars(
                sa.select(PolicyProbabilityForecast)
                .where(
                    PolicyProbabilityForecast.policy_object_id == policy_object_id,
                    PolicyProbabilityForecast.predicted_at <= as_of,
                    PolicyProbabilityForecast.knowledge_cutoff <= as_of,
                )
                .order_by(PolicyProbabilityForecast.predicted_at.desc())
            )
        ).all()
        return {
            **summary,
            "versions": versions,
            "forecasts": forecasts,
        }

    async def graph(self, *, organization_id: UUID, as_of: datetime) -> dict[str, object]:
        nodes = (
            await self.session.scalars(
                sa.select(PolicyGraphNode).where(
                    sa.or_(
                        PolicyGraphNode.organization_id == organization_id,
                        PolicyGraphNode.organization_id.is_(None),
                    )
                )
            )
        ).all()
        node_ids = [node.id for node in nodes]
        edges = []
        if node_ids:
            edges = list(
                (
                    await self.session.scalars(
                        sa.select(PolicyGraphEdge).where(
                            PolicyGraphEdge.from_node_id.in_(node_ids),
                            PolicyGraphEdge.to_node_id.in_(node_ids),
                            PolicyGraphEdge.valid_from <= as_of,
                            sa.or_(PolicyGraphEdge.valid_to.is_(None), PolicyGraphEdge.valid_to > as_of),
                        )
                    )
                ).all()
            )
        return {"nodes": nodes, "edges": edges, "as_of": as_of}
