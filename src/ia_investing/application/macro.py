from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.policy_intelligence import MacroObservationRevision, MacroSeriesDefinition
from ia_investing.domain.macro import (
    MacroValueRevision,
    macro_definition_hash,
    point_in_time_macro_values,
    resample_macro_values,
    transform_macro_values,
    validate_macro_definition,
    validate_macro_revision,
)


class MacroSeriesService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def register_definition(
        self,
        *,
        source_id: UUID,
        series_code: str,
        name: str,
        unit: str,
        frequency: str,
        revision_policy: str,
        transformation: dict[str, object],
        valid_from: datetime,
        permissions: frozenset[str],
    ) -> MacroSeriesDefinition:
        if "macro:write" not in permissions:
            raise PermissionError("permission required: macro:write")
        if valid_from.tzinfo is None:
            raise ValueError("definition valid_from must be timezone-aware")
        validate_macro_definition(unit=unit, frequency=frequency, transformation=transformation)
        payload = {
            "source_id": source_id,
            "series_code": series_code,
            "name": name,
            "unit": unit,
            "frequency": frequency,
            "revision_policy": revision_policy,
            "transformation": transformation,
        }
        digest = macro_definition_hash(payload)
        existing = await self.session.scalar(
            sa.select(MacroSeriesDefinition).where(MacroSeriesDefinition.content_sha256 == digest)
        )
        if existing is not None:
            return existing
        active = await self.session.scalar(
            sa.select(MacroSeriesDefinition)
            .where(
                MacroSeriesDefinition.source_id == source_id,
                MacroSeriesDefinition.series_code == series_code,
                MacroSeriesDefinition.valid_to.is_(None),
            )
            .with_for_update()
        )
        if active is not None:
            if valid_from <= active.valid_from:
                raise ValueError("new macro definition must start after the active version")
            active.valid_to = valid_from
        version = (
            await self.session.scalar(
                sa.select(sa.func.coalesce(sa.func.max(MacroSeriesDefinition.version), 0) + 1).where(
                    MacroSeriesDefinition.source_id == source_id,
                    MacroSeriesDefinition.series_code == series_code,
                )
            )
        ) or 1
        definition = MacroSeriesDefinition(
            source_id=source_id,
            series_code=series_code,
            version=version,
            name=name,
            unit=unit,
            frequency=frequency,
            revision_policy=revision_policy,
            transformation=transformation,
            content_sha256=digest,
            valid_from=valid_from,
        )
        self.session.add(definition)
        await self.session.flush()
        return definition

    async def ingest_observation(
        self,
        *,
        definition_id: UUID,
        effective_date: date,
        value: Decimal | None,
        value_status: str,
        published_at: datetime,
        knowledge_at: datetime,
        source_object_version_id: UUID,
        permissions: frozenset[str],
    ) -> MacroObservationRevision:
        if "macro:write" not in permissions:
            raise PermissionError("permission required: macro:write")
        definition = await self.session.get(MacroSeriesDefinition, definition_id)
        if definition is None:
            raise LookupError("macro series definition not found")
        previous = list(
            (
                await self.session.scalars(
                    sa.select(MacroObservationRevision)
                    .where(
                        MacroObservationRevision.series_definition_id == definition_id,
                        MacroObservationRevision.effective_date == effective_date,
                    )
                    .order_by(MacroObservationRevision.revision)
                    .with_for_update()
                )
            ).all()
        )
        for item in previous:
            if (
                item.value == value
                and item.value_status == value_status
                and item.published_at == published_at
                and item.knowledge_at == knowledge_at
                and item.source_object_version_id == source_object_version_id
            ):
                return item
        candidate = MacroValueRevision(
            effective_date,
            len(previous) + 1,
            value,
            value_status,
            published_at,
            knowledge_at,
        )
        validate_macro_revision(candidate)
        row = MacroObservationRevision(
            series_definition_id=definition_id,
            effective_date=effective_date,
            revision=candidate.revision,
            value=value,
            value_status=value_status,
            published_at=published_at,
            knowledge_at=knowledge_at,
            source_object_version_id=source_object_version_id,
        )
        self.session.add(row)
        await self.session.flush()
        return row

    async def values(self, definition_id: UUID, *, as_of: datetime) -> dict[str, object]:
        if as_of.tzinfo is None:
            raise ValueError("macro cutoff must be timezone-aware")
        definition = await self.session.get(MacroSeriesDefinition, definition_id)
        if (
            definition is None
            or definition.valid_from > as_of
            or (definition.valid_to is not None and definition.valid_to <= as_of)
        ):
            raise LookupError("macro series definition not found at cutoff")
        rows = tuple(
            MacroValueRevision(
                item.effective_date,
                item.revision,
                item.value,
                item.value_status,
                item.published_at,
                item.knowledge_at,
            )
            for item in (
                await self.session.scalars(
                    sa.select(MacroObservationRevision)
                    .where(MacroObservationRevision.series_definition_id == definition_id)
                    .order_by(MacroObservationRevision.effective_date, MacroObservationRevision.revision)
                )
            ).all()
        )
        selected = point_in_time_macro_values(rows, as_of)
        method = str(definition.transformation.get("method", "level"))
        values = transform_macro_values(selected, method)
        resample_frequency = definition.transformation.get("resample_frequency")
        if resample_frequency is not None:
            values = resample_macro_values(
                values,
                frequency=str(resample_frequency),
                aggregation=str(definition.transformation.get("aggregation", "last")),
            )
        return {
            "definition": definition,
            "as_of": as_of,
            "values": values,
        }
