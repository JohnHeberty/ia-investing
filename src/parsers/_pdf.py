"""PDF document parsing using pdfplumber."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class ParsedDocument:
    text: str
    tables: list[list[list[str]]]
    metadata: dict[str, Any]
    source_path: str


def _sanitize_cell(cell: str | None) -> str:
    return cell if cell is not None else ""


def _sanitize_tables(raw: list[list[list[str | None]]]) -> list[list[list[str]]]:
    return [[[_sanitize_cell(cell) for cell in row] for row in table] for table in raw]


def parse_pdf(file_path: str | Path) -> ParsedDocument:
    import pdfplumber

    path = Path(file_path)
    all_text_parts: list[str] = []
    all_tables: list[list[list[str]]] = []

    with pdfplumber.open(path) as pdf:
        metadata: dict[str, Any] = dict(pdf.metadata) if pdf.metadata else {}
        metadata["page_count"] = len(pdf.pages)

        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                all_text_parts.append(page_text)

            raw_tables = page.extract_tables()
            if raw_tables:
                all_tables.extend(_sanitize_tables(raw_tables))

    return ParsedDocument(
        text="\n".join(all_text_parts),
        tables=all_tables,
        metadata=metadata,
        source_path=str(path),
    )


def extract_tables(file_path: str | Path) -> list[list[list[str]]]:
    import pdfplumber

    path = Path(file_path)
    all_tables: list[list[list[str]]] = []

    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            raw_tables = page.extract_tables()
            if raw_tables:
                all_tables.extend(_sanitize_tables(raw_tables))

    return all_tables
