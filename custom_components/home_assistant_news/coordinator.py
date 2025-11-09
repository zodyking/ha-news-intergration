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
        """Scrape full article content from URL using readability-lxml."""
        if not url:
            return ""
        
        try:
            # Follow redirects to get actual article URL
            async with self._session.get(
                url, 
                timeout=20, 
                allow_redirects=True,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
                }
            ) as response:
                if response.status != 200:
                    _LOGGER.warning("Failed to fetch article from %s: HTTP %d", url, response.status)
                    return ""
                
                html_content = await response.text()
                
                # Use readability-lxml to extract article content
                try:
                    from readability import Document
                    from lxml import html as lxml_html
                    
                    # Parse HTML with lxml
                    doc = lxml_html.fromstring(html_content.encode('utf-8'))
                    
                    # Use readability to extract article content
                    readable_article = Document(doc)
                    article_html = readable_article.summary()
                    
                    # Parse the extracted HTML to get text
                    article_doc = lxml_html.fromstring(article_html.encode('utf-8'))
                    article_text = article_doc.text_content()
                    
                    # Clean up the text
                    # Decode HTML entities
                    article_text = html.unescape(article_text)
                    # Collapse whitespace
                    article_text = re.sub(r'\s+', ' ', article_text)
                    article_text = article_text.strip()
                    
                    # Limit to reasonable length (5000 chars for full articles)
                    if len(article_text) > 5000:
                        article_text = article_text[:5000] + "..."
                    
                    if article_text:
                        _LOGGER.debug("Successfully scraped article from %s (%d chars)", url, len(article_text))
                        return article_text
                    else:
                        _LOGGER.warning("Readability extracted empty content from %s", url)
                        return ""
                        
                except ImportError:
                    _LOGGER.debug("readability-lxml not available, falling back to basic extraction for %s", url)
                    # Fallback to basic extraction if readability is not available
                    result = self._basic_extract_article(html_content)
                    if not result:
                        _LOGGER.warning("Both readability and basic extraction failed for %s", url)
                    return result
                except Exception as err:
                    _LOGGER.debug("Readability extraction failed for %s: %s, trying fallback", url, err)
                    # Fallback to basic extraction
                    result = self._basic_extract_article(html_content)
                    if not result:
                        _LOGGER.warning("Both readability and basic extraction failed for %s: %s", url, err)
                    return result
                
        except Exception as err:
            _LOGGER.warning("Failed to scrape article from %s: %s", url, err)
            return ""
    
    def _basic_extract_article(self, html_content: str) -> str:
        """Basic fallback article extraction."""
        try:
            # Remove script and style tags
            html_content = re.sub(r'<script[^>]*>.*?</script>', '', html_content, flags=re.DOTALL | re.IGNORECASE)
            html_content = re.sub(r'<style[^>]*>.*?</style>', '', html_content, flags=re.DOTALL | re.IGNORECASE)
            html_content = re.sub(r'<noscript[^>]*>.*?</noscript>', '', html_content, flags=re.DOTALL | re.IGNORECASE)
            
            # Try to extract from common article tags (more patterns)
            article_patterns = [
                r'<article[^>]*>(.*?)</article>',
                r'<div[^>]*class="[^"]*article[^"]*"[^>]*>(.*?)</div>',
                r'<div[^>]*class="[^"]*content[^"]*"[^>]*>(.*?)</div>',
                r'<div[^>]*class="[^"]*post[^"]*"[^>]*>(.*?)</div>',
                r'<div[^>]*class="[^"]*entry[^"]*"[^>]*>(.*?)</div>',
                r'<div[^>]*id="[^"]*content[^"]*"[^>]*>(.*?)</div>',
                r'<div[^>]*id="[^"]*article[^"]*"[^>]*>(.*?)</div>',
                r'<main[^>]*>(.*?)</main>',
                r'<section[^>]*class="[^"]*content[^"]*"[^>]*>(.*?)</section>',
            ]
            
            content = ""
            for pattern in article_patterns:
                matches = re.findall(pattern, html_content, re.DOTALL | re.IGNORECASE)
                if matches:
                    # Get the longest match (likely the main content)
                    content = max(matches, key=len)
                    if len(content) > 200:  # Only use if substantial content
                        break
            
            if not content or len(content) < 200:
                # Fallback: extract from body, but exclude common non-content elements
                body_match = re.search(r'<body[^>]*>(.*?)</body>', html_content, re.DOTALL | re.IGNORECASE)
                if body_match:
                    body_content = body_match.group(1)
                    # Remove navigation, header, footer, sidebar
                    body_content = re.sub(r'<nav[^>]*>.*?</nav>', '', body_content, flags=re.DOTALL | re.IGNORECASE)
                    body_content = re.sub(r'<header[^>]*>.*?</header>', '', body_content, flags=re.DOTALL | re.IGNORECASE)
                    body_content = re.sub(r'<footer[^>]*>.*?</footer>', '', body_content, flags=re.DOTALL | re.IGNORECASE)
                    body_content = re.sub(r'<aside[^>]*>.*?</aside>', '', body_content, flags=re.DOTALL | re.IGNORECASE)
                    content = body_content
            
            # Strip HTML tags but preserve paragraph breaks
            content = re.sub(r'</p>', '\n\n', content, flags=re.IGNORECASE)
            content = re.sub(r'</div>', '\n', content, flags=re.IGNORECASE)
            content = re.sub(r'<br[^>]*>', '\n', content, flags=re.IGNORECASE)
            content = re.sub(r'<[^>]+>', ' ', content)
            
            # Decode HTML entities
            content = html.unescape(content)
            
            # Clean up whitespace
            content = re.sub(r'\n\s*\n\s*\n+', '\n\n', content)  # Max 2 consecutive newlines
            content = re.sub(r'[ \t]+', ' ', content)  # Collapse spaces
            content = content.strip()
            
            # Limit to reasonable length (5000 chars)
            if len(content) > 5000:
                content = content[:5000] + "..."
            
            if content and len(content) > 50:
                _LOGGER.debug("Basic extraction succeeded (%d chars)", len(content))
                return content
            else:
                _LOGGER.warning("Basic extraction produced insufficient content (%d chars)", len(content) if content else 0)
                return ""
        except Exception as err:
            _LOGGER.warning("Basic extraction failed: %s", err, exc_info=True)
            return ""

