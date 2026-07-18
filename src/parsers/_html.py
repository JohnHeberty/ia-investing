"""HTML document parsing and text extraction."""

from __future__ import annotations

import re
from html.parser import HTMLParser

from ._pdf import ParsedDocument


def parse_html(html: str) -> ParsedDocument:

    class _TextExtractor(HTMLParser):
        def __init__(self) -> None:
            super().__init__()
            self._parts: list[str] = []
            self._skip = False

        def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
            if tag in ("script", "style", "noscript"):
                self._skip = True

        def handle_endtag(self, tag: str) -> None:
            if tag in ("script", "style", "noscript"):
                self._skip = False
            elif tag in ("p", "br", "div", "h1", "h2", "h3", "h4", "h5", "h6", "li", "tr"):
                self._parts.append("\n")

        def handle_data(self, data: str) -> None:
            if not self._skip:
                self._parts.append(data)

        def get_text(self) -> str:
            raw = "".join(self._parts)
            raw = re.sub(r"[ \t]+", " ", raw)
            raw = re.sub(r"\n\s*\n+", "\n", raw)
            return raw.strip()

    extractor = _TextExtractor()
    extractor.feed(html)

    return ParsedDocument(
        text=extractor.get_text(),
        tables=[],
        metadata={"source": "html"},
        source_path="<html>",
    )


def extract_text_from_tag(html: str, tag: str, attrs: dict[str, str] | None = None) -> str:

    class _TagExtractor(HTMLParser):
        def __init__(self, target_tag: str, target_attrs: dict[str, str] | None) -> None:
            super().__init__()
            self._parts: list[str] = []
            self._depth = 0
            self._target = False
            self._target_tag = target_tag
            self._target_attrs = target_attrs

        def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
            if tag != self._target_tag:
                return
            if self._target_attrs:
                attr_dict = dict(attrs)
                if not all(attr_dict.get(k) == v for k, v in self._target_attrs.items()):
                    return
            self._target = True
            self._depth += 1

        def handle_endtag(self, tag: str) -> None:
            if tag == self._target_tag and self._target:
                self._depth -= 1
                if self._depth <= 0:
                    self._target = False

        def handle_data(self, data: str) -> None:
            if self._target:
                self._parts.append(data)

        def get_text(self) -> str:
            return re.sub(r"\s+", " ", "".join(self._parts)).strip()

    extractor = _TagExtractor(tag, attrs)
    extractor.feed(html)
    return extractor.get_text()
