from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from urllib.parse import quote_plus

from ..base import DEFAULT_TIMEOUT, HttpClient

GOOGLE_NEWS_RSS = "https://news.google.com/rss/search"
REUTERS_RSS = "https://www.reuters.com/rssFeed"

_NS = {"atom": "http://www.w3.org/2005/Atom", "media": "http://search.yahoo.com/mrss/"}


@dataclass(slots=True)
class NewsArticle:
    title: str
    body: str
    url: str
    source: str
    published_at: datetime
    retrieved_at: datetime
    language: str


def _parse_pub_date(raw: str) -> datetime:
    try:
        return parsedate_to_datetime(raw)
    except (ValueError, TypeError):
        pass

    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(raw, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=UTC)
            return dt
        except ValueError:
            continue

    return datetime.now(UTC)


def _extract_text(element: ET.Element | None) -> str:
    if element is None:
        return ""
    text = element.text or ""
    return text.strip()


def parse_rss_feed(xml_content: str, source: str) -> list[NewsArticle]:
    root = ET.fromstring(xml_content)
    articles: list[NewsArticle] = []
    now = datetime.now(UTC)

    items = root.findall(".//item")
    if not items:
        items = root.findall(".//atom:entry", _NS)

    for item in items:
        title = _extract_text(item.find("title")) or _extract_text(item.find("atom:title", _NS))
        link = _extract_text(item.find("link")) or _extract_text(item.find("atom:link", _NS))
        if not link:
            link_el = item.find("atom:link", _NS)
            if link_el is not None:
                link = link_el.get("href", "")

        description = (
            _extract_text(item.find("description"))
            or _extract_text(item.find("atom:summary", _NS))
            or _extract_text(item.find("media:group/media:description", _NS))
        )

        pub_date_raw = (
            _extract_text(item.find("pubDate"))
            or _extract_text(item.find("atom:published", _NS))
            or _extract_text(item.find("atom:updated", _NS))
        )
        published_at = _parse_pub_date(pub_date_raw) if pub_date_raw else now

        source_el = item.find("source")
        source_name = source_el.text if source_el is not None else source

        if title or link:
            articles.append(
                NewsArticle(
                    title=title,
                    body=description,
                    url=link,
                    source=source_name or source,
                    published_at=published_at,
                    retrieved_at=now,
                    language="pt-BR",
                )
            )

    return articles


async def fetch_google_news_rss(
    query: str,
    language: str = "pt-BR",
    max_results: int = 20,
    client: HttpClient | None = None,
) -> list[NewsArticle]:
    if client is None:
        client = HttpClient(timeout=DEFAULT_TIMEOUT)

    params = {"q": query, "hl": language, "gl": "BR", "ceid": "BR:pt-419"}
    raw = await client.get_text(GOOGLE_NEWS_RSS, params=params)
    articles = parse_rss_feed(raw, source="Google News")
    return articles[:max_results]


async def fetch_reuters_rss(
    query: str,
    language: str = "pt-BR",
    max_results: int = 20,
    client: HttpClient | None = None,
) -> list[NewsArticle]:
    if client is None:
        client = HttpClient(timeout=DEFAULT_TIMEOUT)

    url = f"{REUTERS_RSS}/{quote_plus(query)}"
    raw = await client.get_text(url)
    articles = parse_rss_feed(raw, source="Reuters")
    return articles[:max_results]
