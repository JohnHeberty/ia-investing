from __future__ import annotations

from fastapi import HTTPException


def parse_etag(value: str, *, entity: str = "resource") -> int:
    normalized = value.strip().removeprefix("W/").strip('"')
    try:
        return int(normalized)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"If-Match must contain a numeric {entity} version") from exc
