"""Shared types for document parsing."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class ParsedDocument:
    text: str
    tables: list[list[list[str]]]
    metadata: dict[str, Any]
    source_path: str
