"""Unit tests for parsers._types — ParsedDocument dataclass."""

from __future__ import annotations

import pytest

from parsers._types import ParsedDocument


class TestParsedDocument:
    def test_construction_with_all_fields(self):
        doc = ParsedDocument(
            text="hello",
            tables=[[["a", "b"], ["c", "d"]]],
            metadata={"page_count": 1},
            source_path="/tmp/test.pdf",
        )
        assert doc.text == "hello"
        assert doc.tables == [[["a", "b"], ["c", "d"]]]
        assert doc.metadata == {"page_count": 1}
        assert doc.source_path == "/tmp/test.pdf"

    def test_empty_document(self):
        doc = ParsedDocument(text="", tables=[], metadata={}, source_path="")
        assert doc.text == ""
        assert doc.tables == []
        assert doc.metadata == {}
        assert doc.source_path == ""

    def test_equality(self):
        a = ParsedDocument(text="x", tables=[], metadata={}, source_path="a")
        b = ParsedDocument(text="x", tables=[], metadata={}, source_path="a")
        assert a == b

    def test_inequality(self):
        a = ParsedDocument(text="x", tables=[], metadata={}, source_path="a")
        b = ParsedDocument(text="y", tables=[], metadata={}, source_path="a")
        assert a != b

    def test_slots_prevents_attribute_creation(self):
        doc = ParsedDocument(text="", tables=[], metadata={}, source_path="")
        with pytest.raises(AttributeError):
            doc.new_attr = "oops"  # type: ignore[attr-defined]

    def test_metadata_is_mutable(self):
        doc = ParsedDocument(text="", tables=[], metadata={}, source_path="")
        doc.metadata["key"] = "value"
        assert doc.metadata["key"] == "value"

    def test_tables_nested_structure(self):
        tables = [
            [["h1", "h2"], ["v1", "v2"]],
            [["x", "y", "z"]],
        ]
        doc = ParsedDocument(text="", tables=tables, metadata={}, source_path="")
        assert len(doc.tables) == 2
        assert doc.tables[0][0] == ["h1", "h2"]

    def test_hashable_metadata_keys(self):
        doc = ParsedDocument(text="", tables=[], metadata={"a": 1, "b": [2, 3]}, source_path="")
        assert doc.metadata["a"] == 1
        assert doc.metadata["b"] == [2, 3]

    def test_large_text(self):
        big_text = "x" * 100_000
        doc = ParsedDocument(text=big_text, tables=[], metadata={}, source_path="")
        assert len(doc.text) == 100_000
