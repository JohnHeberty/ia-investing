"""Document parsing — extract text, tables, and metadata from PDF and HTML."""

from ._html import extract_text_from_tag, parse_html
from ._pdf import ParsedDocument, extract_tables, parse_pdf

__all__ = [
    "ParsedDocument",
    "extract_tables",
    "extract_text_from_tag",
    "parse_html",
    "parse_pdf",
]
