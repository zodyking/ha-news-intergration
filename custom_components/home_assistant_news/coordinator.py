"""DataUpdateCoordinator for fetching Google News RSS feeds."""
from __future__ import annotations

import asyncio
import html
import logging
import re
import xml.etree.ElementTree as ET
from datetime import timedelta
from urllib.parse import quote

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import CATEGORY_MAP, DEFAULTS, DOMAIN, GOOGLE_RSS_BASE, GOOGLE_RSS_SEARCH_BASE

_LOGGER = logging.getLogger(__name__)


class NewsCoordinator(DataUpdateCoordinator[dict[str, list[dict[str, str]]]]):
    """Coordinator to fetch and parse Google News RSS feeds."""

    def __init__(
        self,
        hass: HomeAssistant,
        scan_interval: int,
        max_per_category: int,
        local_geo: str,
        enabled_categories: dict[str, bool],
        custom_sources: list[dict[str, str]] | None = None,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
        )
        self._max_per_category = max_per_category
        self._local_geo = local_geo
        self._enabled_categories = enabled_categories
        self._custom_sources = custom_sources or []
        self._session = None

    async def _async_update_data(
        self,
    ) -> dict[str, list[dict[str, str]]]:
        """Fetch data from Google News RSS feeds."""
        if self._session is None:
            from homeassistant.helpers import aiohttp_client
            self._session = aiohttp_client.async_get_clientsession(self.hass)

        results: dict[str, list[dict[str, str]]] = {}
        used_article_ids: set[str] = set()  # Track articles to prevent duplicates

        # Fetch all enabled categories in parallel
        tasks = []
        category_list = []
        for category, enabled in self._enabled_categories.items():
            if not enabled:
                results[category] = []
                continue

            category_list.append(category)
            if category == "Local":
                tasks.append(self._fetch_local_feed(category))
            else:
                tasks.append(self._fetch_topic_feed(category))

        # Fetch custom sources in parallel
        for source in self._custom_sources:
            category_list.append(source.get("name", ""))
            tasks.append(self._fetch_query_feed(source.get("name", ""), source.get("query", "")))

        fetched_data = await asyncio.gather(*tasks, return_exceptions=True)

        for category, data in zip(category_list, fetched_data):
            if isinstance(data, Exception):
                _LOGGER.warning(
                    "Error fetching %s: %s", category, data, exc_info=data
                )
                results[category] = []
            else:
                # Filter out duplicates and limit to max_per_category
                unique_articles = []
                for article in data:
                    article_id = article.get("link", article.get("title", ""))
                    if article_id and article_id not in used_article_ids:
                        used_article_ids.add(article_id)
                        unique_articles.append(article)
                        if len(unique_articles) >= self._max_per_category:
                            break
                results[category] = unique_articles

        # Scrape article content for all articles in parallel
        scrape_tasks = []
        article_list = []
        for category, articles in results.items():
            for article in articles:
                article_list.append((category, article))
                scrape_tasks.append(self._scrape_article(article.get("link", "")))
        
        scraped_contents = await asyncio.gather(*scrape_tasks, return_exceptions=True)
        
        # Update articles with scraped content
        for (category, article), content in zip(article_list, scraped_contents):
            if isinstance(content, Exception):
                _LOGGER.warning("Error scraping article: %s", content)
                article["summary"] = ""
            else:
                article["summary"] = content if content else ""

        return results

    async def _fetch_topic_feed(
        self, category: str
    ) -> list[dict[str, str]]:
        """Fetch a topic-based RSS feed."""
        topic = CATEGORY_MAP[category]
        url = (
            f"{GOOGLE_RSS_BASE}/topic/{topic}"
            "?hl=en-US&gl=US&ceid=US:en"
        )

        try:
            async with self._session.get(url, timeout=10) as response:
                response.raise_for_status()
                text = await response.text()
                return self._parse_rss(text)
        except Exception as err:
            _LOGGER.warning("Failed to fetch %s: %s", category, err)
            return []

    async def _fetch_local_feed(
        self, category: str
    ) -> list[dict[str, str]]:
        """Fetch a local/geo-based RSS feed."""
        # URL encode the geo location
        geo_encoded = quote(self._local_geo)
        url = (
            f"{GOOGLE_RSS_BASE}/geo/{geo_encoded}"
            "?hl=en-US&gl=US&ceid=US:en"
        )

        try:
            async with self._session.get(url, timeout=10) as response:
                response.raise_for_status()
                text = await response.text()
                return self._parse_rss(text)
        except Exception as err:
            _LOGGER.warning("Failed to fetch %s: %s", category, err)
            return []

    async def _fetch_query_feed(
        self, name: str, query: str
    ) -> list[dict[str, str]]:
        """Fetch a query-based RSS feed."""
        # URL encode the query
        query_encoded = quote(query)
        url = (
            f"{GOOGLE_RSS_SEARCH_BASE}?q={query_encoded}"
            "&hl=en-US&gl=US&ceid=US:en"
        )

        try:
            async with self._session.get(url, timeout=10) as response:
                response.raise_for_status()
                text = await response.text()
                return self._parse_rss(text)
        except Exception as err:
            _LOGGER.warning("Failed to fetch query feed %s (%s): %s", name, query, err)
            return []

    def _parse_rss(self, xml_text: str) -> list[dict[str, str]]:
        """Parse RSS XML and extract articles."""
        articles = []
        try:
            root = ET.fromstring(xml_text)
            # Find all items
            for item in root.findall(".//item"):
                title_elem = item.find("title")
                link_elem = item.find("link")

                title = ""
                if title_elem is not None and title_elem.text:
                    title = html.unescape(title_elem.text.strip())

                link = ""
                if link_elem is not None and link_elem.text:
                    link = html.unescape(link_elem.text.strip())

                if title:
                    articles.append({"title": title, "link": link, "summary": ""})

        except ET.ParseError as err:
            _LOGGER.warning("Failed to parse RSS XML: %s", err)
        except Exception as err:
            _LOGGER.warning("Unexpected error parsing RSS: %s", err)

        return articles

    async def _scrape_article(self, url: str) -> str:
        """Scrape full article content from URL."""
        if not url:
            return ""
        
        try:
            # Follow redirects to get actual article URL
            async with self._session.get(url, timeout=15, allow_redirects=True) as response:
                if response.status != 200:
                    return ""
                
                text = await response.text()
                
                # Extract article content using basic HTML parsing
                # Try to find main content areas
                import re
                
                # Remove script and style tags
                text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL | re.IGNORECASE)
                text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
                
                # Try to extract from common article tags
                article_patterns = [
                    r'<article[^>]*>(.*?)</article>',
                    r'<div[^>]*class="[^"]*article[^"]*"[^>]*>(.*?)</div>',
                    r'<div[^>]*class="[^"]*content[^"]*"[^>]*>(.*?)</div>',
                    r'<main[^>]*>(.*?)</main>',
                ]
                
                content = ""
                for pattern in article_patterns:
                    matches = re.findall(pattern, text, re.DOTALL | re.IGNORECASE)
                    if matches:
                        content = matches[0]
                        break
                
                if not content:
                    # Fallback: extract from body
                    body_match = re.search(r'<body[^>]*>(.*?)</body>', text, re.DOTALL | re.IGNORECASE)
                    if body_match:
                        content = body_match.group(1)
                
                # Strip HTML tags
                content = re.sub(r'<[^>]+>', ' ', content)
                # Decode HTML entities
                content = html.unescape(content)
                # Collapse whitespace
                content = re.sub(r'\s+', ' ', content)
                content = content.strip()
                
                # Limit to reasonable length (2000 chars)
                if len(content) > 2000:
                    content = content[:2000] + "..."
                
                return content
                
        except Exception as err:
            _LOGGER.warning("Failed to scrape article from %s: %s", url, err)
            return ""

