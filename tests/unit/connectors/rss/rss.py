"""Unit tests for connectors.news._rss — RSS feed parsing and fetching."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest

from connectors.news._rss import (
    NewsArticle,
    _extract_text,
    _parse_pub_date,
    fetch_google_news_rss,
    fetch_reuters_rss,
    parse_rss_feed,
)


@pytest.mark.unit
class TestParsePubDate:
    def test_rfc2822(self):
        dt = _parse_pub_date("Mon, 01 Jan 2026 12:00:00 +0000")
        assert dt.year == 2026
        assert dt.month == 1
        assert dt.hour == 12

    def test_iso_with_tz(self):
        dt = _parse_pub_date("2026-06-15T10:30:00+00:00")
        assert dt.year == 2026
        assert dt.tzinfo is not None

    def test_iso_without_tz(self):
        dt = _parse_pub_date("2026-06-15T10:30:00Z")
        assert dt.year == 2026

    def test_date_only(self):
        dt = _parse_pub_date("2026-03-20")
        assert dt.year == 2026
        assert dt.month == 3
        assert dt.tzinfo is not None

    def test_unparseable_returns_now(self):
        dt = _parse_pub_date("not-a-date")
        assert isinstance(dt, datetime)
        assert dt.tzinfo is UTC

    def test_none_returns_now(self):
        dt = _parse_pub_date("")
        assert isinstance(dt, datetime)


@pytest.mark.unit
class TestExtractText:
    def test_none_returns_empty(self):
        assert _extract_text(None) == ""

    def test_element_with_text(self):
        import defusedxml.ElementTree as ET

        el = ET.fromstring("<item><title>Test</title></item>")
        assert _extract_text(el.find("title")) == "Test"

    def test_element_without_text(self):
        import defusedxml.ElementTree as ET

        el = ET.fromstring("<item><title/></item>")
        assert _extract_text(el.find("title")) == ""

    def test_strips_whitespace(self):
        import defusedxml.ElementTree as ET

        el = ET.fromstring("<item><title>  Hello  </title></item>")
        assert _extract_text(el.find("title")) == "Hello"


@pytest.mark.unit
class TestParseRssFeed:
    SAMPLE_RSS = """<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0">
    <channel>
        <item>
            <title>Petrobras sobe 3%</title>
            <link>https://example.com/1</link>
            <description>Noticia sobre petroleo</description>
            <pubDate>Mon, 01 Jan 2026 12:00:00 +0000</pubDate>
            <source>Reuters</source>
        </item>
        <item>
            <title>Vale cai 2%</title>
            <link>https://example.com/2</link>
            <description>Mineracao em alta</description>
            <pubDate>Tue, 02 Jan 2026 10:00:00 +0000</pubDate>
        </item>
    </channel>
    </rss>"""

    def test_parse_two_items(self):
        articles = parse_rss_feed(self.SAMPLE_RSS, source="test")
        assert len(articles) == 2
        assert articles[0].title == "Petrobras sobe 3%"
        assert articles[0].source == "Reuters"
        assert articles[1].source == "test"

    def test_empty_feed(self):
        articles = parse_rss_feed(
            '<?xml version="1.0"?><rss version="2.0"><channel></channel></rss>',
            source="empty",
        )
        assert articles == []

    def test_atom_format(self):
        atom = """<?xml version="1.0" encoding="UTF-8"?>
        <feed xmlns="http://www.w3.org/2005/Atom">
            <entry>
                <title>Atom Title</title>
                <link href="https://example.com/atom"/>
                <summary>Atom summary</summary>
                <published>2026-01-01T12:00:00Z</published>
            </entry>
        </feed>"""
        articles = parse_rss_feed(atom, source="atom-test")
        assert len(articles) == 1
        assert articles[0].title == "Atom Title"

    def test_no_title_no_link_skipped(self):
        rss = """<?xml version="1.0"?>
        <rss version="2.0"><channel>
            <item><description>Only description</description></item>
        </channel></rss>"""
        articles = parse_rss_feed(rss, source="skip-test")
        assert len(articles) == 0

    def test_language_is_pt_br(self):
        articles = parse_rss_feed(self.SAMPLE_RSS, source="test")
        assert all(a.language == "pt-BR" for a in articles)


@pytest.mark.unit
class TestFetchGoogleNewsRss:
    @pytest.mark.asyncio
    async def test_calls_correct_url(self):
        mock_client = AsyncMock()
        mock_client.get_text = AsyncMock(return_value='<?xml version="1.0"?><rss version="2.0"><channel></channel></rss>')
        result = await fetch_google_news_rss("petroleo", client=mock_client)
        assert result == []
        mock_client.get_text.assert_called_once()
        call_args = mock_client.get_text.call_args
        assert "news.google.com" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_max_results_limits_output(self):
        rss = """<?xml version="1.0"?>
        <rss version="2.0"><channel>
            <item><title>A</title><link>https://a.com</link></item>
            <item><title>B</title><link>https://b.com</link></item>
            <item><title>C</title><link>https://c.com</link></item>
        </channel></rss>"""
        mock_client = AsyncMock()
        mock_client.get_text = AsyncMock(return_value=rss)
        result = await fetch_google_news_rss("test", max_results=2, client=mock_client)
        assert len(result) == 2


@pytest.mark.unit
class TestFetchReutersRss:
    @pytest.mark.asyncio
    async def test_calls_correct_url(self):
        mock_client = AsyncMock()
        mock_client.get_text = AsyncMock(return_value='<?xml version="1.0"?><rss version="2.0"><channel></channel></rss>')
        result = await fetch_reuters_rss("economia", client=mock_client)
        assert result == []
        call_args = mock_client.get_text.call_args
        assert "reuters.com" in call_args[0][0]
