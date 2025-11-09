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

        # Update articles with content - use description as primary source, scrape only if needed
        scrape_tasks = []
        article_list = []
        for category, articles in results.items():
            for article in articles:
                article_list.append((category, article))
                description = article.get("description", "")
                
                # If description is substantial (>= 100 chars), use it directly
                if description and len(description) >= 100:
                    article["summary"] = description
                    _LOGGER.debug("Using RSS description (%d chars) for article", len(description))
                    scrape_tasks.append(None)  # No scraping needed
                else:
                    # Description is missing or too short, try to scrape
                    scrape_tasks.append(self._scrape_article(article.get("link", "")))
        
        # Scrape articles that need it in parallel
        if any(task is not None for task in scrape_tasks):
            async def noop():
                return ""
            
            scraped_results = await asyncio.gather(
                *[task if task else noop() for task in scrape_tasks],
                return_exceptions=True
            )
            
            # Update articles with scraped content
            for (category, article), scraped in zip(article_list, scraped_results):
                description = article.get("description", "")
                
                # If we already set summary from description, skip
                if article.get("summary"):
                    continue
                
                if isinstance(scraped, Exception):
                    _LOGGER.debug("Error scraping article: %s, using description", scraped)
                    article["summary"] = description if description else ""
                elif scraped and len(scraped) > 50:
                    article["summary"] = scraped
                    _LOGGER.debug("Using scraped content (%d chars) for article", len(scraped))
                else:
                    # Scraping failed or returned insufficient content, use description if available
                    article["summary"] = description if description else ""
                    if description:
                        _LOGGER.debug("Scraping failed, using RSS description (%d chars)", len(description))
                    else:
                        _LOGGER.debug("No description or scraped content available for article")

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
                desc_elem = item.find("description")

                title = ""
                if title_elem is not None and title_elem.text:
                    title = html.unescape(title_elem.text.strip())

                link = ""
                if link_elem is not None and link_elem.text:
                    link = html.unescape(link_elem.text.strip())

                # Extract description as fallback
                description = ""
                if desc_elem is not None and desc_elem.text:
                    description = html.unescape(desc_elem.text.strip())
                    # Clean HTML from description
                    description = re.sub(r'<[^>]+>', ' ', description)
                    description = re.sub(r'\s+', ' ', description).strip()

                if title:
                    articles.append({"title": title, "link": link, "summary": "", "description": description})

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
            # For Google News redirect URLs, we need to extract the actual article URL
            actual_url = url
            if "news.google.com/rss/articles" in url:
                # This is a Google News redirect URL, try to get the actual URL
                try:
                    async with self._session.get(
                        url,
                        timeout=10,
                        allow_redirects=False,
                        headers={
                            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                        }
                    ) as redirect_response:
                        # Check for redirect location header
                        if redirect_response.status in (301, 302, 303, 307, 308):
                            location = redirect_response.headers.get("Location", "")
                            if location:
                                actual_url = location
                                _LOGGER.debug("Extracted actual URL from redirect header: %s", actual_url)
                        elif redirect_response.status == 200:
                            # Try to extract URL from HTML (Google News sometimes uses meta refresh or JS redirects)
                            redirect_html = await redirect_response.text()
                            # Look for meta refresh
                            meta_refresh = re.search(r'<meta[^>]*http-equiv=["\']?refresh["\']?[^>]*content=["\']?[^"\']*url=([^"\']+)["\']?', redirect_html, re.IGNORECASE)
                            if meta_refresh:
                                actual_url = meta_refresh.group(1)
                                _LOGGER.debug("Extracted actual URL from meta refresh: %s", actual_url)
                            else:
                                # Look for JavaScript redirect
                                js_redirect = re.search(r'window\.location\.href\s*=\s*["\']([^"\']+)["\']', redirect_html, re.IGNORECASE)
                                if js_redirect:
                                    actual_url = js_redirect.group(1)
                                    _LOGGER.debug("Extracted actual URL from JavaScript redirect: %s", actual_url)
                except Exception as redirect_err:
                    _LOGGER.debug("Could not extract URL from redirect: %s", redirect_err)
            
            # Follow redirects to get actual article URL
            async with self._session.get(
                actual_url, 
                timeout=20, 
                allow_redirects=True,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.5",
                    "Accept-Encoding": "gzip, deflate, br",
                    "Connection": "keep-alive",
                    "Upgrade-Insecure-Requests": "1"
                }
            ) as response:
                if response.status != 200:
                    _LOGGER.debug("Failed to fetch article from %s: HTTP %d", actual_url, response.status)
                    return ""
                
                html_content = await response.text()
                final_url = str(response.url)
                _LOGGER.debug("Fetched article from %s (final URL: %s)", actual_url, final_url)
                
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
                # Try to extract paragraphs directly
                para_matches = re.findall(r'<p[^>]*>(.*?)</p>', html_content, re.DOTALL | re.IGNORECASE)
                if para_matches:
                    # Combine all paragraphs
                    para_texts = []
                    for para in para_matches:
                        # Strip HTML from paragraph
                        para_clean = re.sub(r'<[^>]+>', ' ', para)
                        para_clean = html.unescape(para_clean)
                        para_clean = re.sub(r'\s+', ' ', para_clean).strip()
                        if len(para_clean) > 50:  # Only include substantial paragraphs
                            para_texts.append(para_clean)
                    if para_texts:
                        content = ' '.join(para_texts)
                        _LOGGER.debug("Extracted content from paragraphs (%d chars)", len(content))
            
            if not content or len(content) < 200:
                # Fallback: extract from body, but exclude common non-content elements
                body_match = re.search(r'<body[^>]*>(.*?)</body>', html_content, re.DOTALL | re.IGNORECASE)
                if body_match:
                    body_content = body_match.group(1)
                    # Remove navigation, header, footer, sidebar, ads
                    body_content = re.sub(r'<nav[^>]*>.*?</nav>', '', body_content, flags=re.DOTALL | re.IGNORECASE)
                    body_content = re.sub(r'<header[^>]*>.*?</header>', '', body_content, flags=re.DOTALL | re.IGNORECASE)
                    body_content = re.sub(r'<footer[^>]*>.*?</footer>', '', body_content, flags=re.DOTALL | re.IGNORECASE)
                    body_content = re.sub(r'<aside[^>]*>.*?</aside>', '', body_content, flags=re.DOTALL | re.IGNORECASE)
                    body_content = re.sub(r'<div[^>]*class="[^"]*ad[^"]*"[^>]*>.*?</div>', '', body_content, flags=re.DOTALL | re.IGNORECASE)
                    body_content = re.sub(r'<div[^>]*id="[^"]*ad[^"]*"[^>]*>.*?</div>', '', body_content, flags=re.DOTALL | re.IGNORECASE)
                    # Extract text from remaining body
                    body_content = re.sub(r'<[^>]+>', ' ', body_content)
                    body_content = html.unescape(body_content)
                    body_content = re.sub(r'\s+', ' ', body_content).strip()
                    if len(body_content) > 200:
                        content = body_content
                        _LOGGER.debug("Extracted content from body (%d chars)", len(content))
            
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

