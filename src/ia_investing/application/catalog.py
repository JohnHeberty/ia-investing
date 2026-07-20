from __future__ import annotations

import uuid
from typing import Any

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.catalog import Issuer, Sector


class IssuerCatalogService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_cnpj(self, cnpj: str) -> dict[str, Any] | None:
        stmt = sa.select(Issuer).where(Issuer.cnpj == cnpj)
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return self._to_dict(row)

    async def get_by_id(self, issuer_id: uuid.UUID) -> dict[str, Any] | None:
        stmt = sa.select(Issuer).where(Issuer.id == issuer_id)
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return self._to_dict(row)

    async def list_active(
        self,
        sector: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        stmt = sa.select(Issuer).where(Issuer.is_active.is_(True))
        if sector:
            stmt = stmt.join(Issuer.industry).join(Sector).where(
                Sector.name_pt.ilike(f"%{sector}%")
            )
        stmt = stmt.order_by(Issuer.name_pt).offset(offset).limit(limit)
        result = await self._session.execute(stmt)
        rows = result.scalars().all()
        return [
            {
                "id": str(r.id),
                "name_pt": r.name_pt,
                "cnpj": r.cnpj,
                "cvm_code": r.cvm_code,
                "website_ri_url": r.website_ri_url,
            }
            for r in rows
        ]

    @staticmethod
    def _to_dict(row: Issuer) -> dict[str, Any]:
        return {
            "id": str(row.id),
            "name_pt": row.name_pt,
            "cnpj": row.cnpj,
            "cvm_code": row.cvm_code,
            "industry_id": str(row.industry_id) if row.industry_id is not None else None,
            "website_ri_url": row.website_ri_url,
            "is_active": row.is_active,
        }
