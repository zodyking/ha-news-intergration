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

from .const import CATEGORY_MAP, DEFAULTS, DOMAIN, GOOGLE_RSS_BASE

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
        self._session = None

    async def _async_update_data(
        self,
    ) -> dict[str, list[dict[str, str]]]:
        """Fetch data from Google News RSS feeds."""
        if self._session is None:
            from homeassistant.helpers import aiohttp_client
            self._session = aiohttp_client.async_get_clientsession(self.hass)

        results: dict[str, list[dict[str, str]]] = {}

        # Fetch all enabled categories in parallel
        tasks = []
        for category, enabled in self._enabled_categories.items():
            if not enabled:
                results[category] = []
                continue

            if category == "Local":
                tasks.append(self._fetch_local_feed(category))
            else:
                tasks.append(self._fetch_topic_feed(category))

        fetched_data = await asyncio.gather(*tasks, return_exceptions=True)

        for category, data in zip(
            [cat for cat, enabled in self._enabled_categories.items() if enabled],
            fetched_data,
        ):
            if isinstance(data, Exception):
                _LOGGER.warning(
                    "Error fetching %s: %s", category, data, exc_info=data
                )
                results[category] = []
            else:
                results[category] = data[: self._max_per_category]

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

    def _parse_rss(self, xml_text: str) -> list[dict[str, str]]:
        """Parse RSS XML and extract articles."""
        articles = []
        try:
            root = ET.fromstring(xml_text)
            # Find all items
            for item in root.findall(".//item"):
                title_elem = item.find("title")
                desc_elem = item.find("description")

                title = ""
                if title_elem is not None and title_elem.text:
                    title = html.unescape(title_elem.text.strip())

                summary = ""
                if desc_elem is not None and desc_elem.text:
                    # Remove HTML tags and clean up
                    text = html.unescape(desc_elem.text)
                    # Strip HTML tags using regex
                    text = re.sub(r"<[^>]+>", "", text)
                    # Collapse whitespace
                    text = re.sub(r"\s+", " ", text)
                    summary = text.strip()[:600]  # Limit to 600 chars

                if title:
                    articles.append({"title": title, "summary": summary})

        except ET.ParseError as err:
            _LOGGER.warning("Failed to parse RSS XML: %s", err)
        except Exception as err:
            _LOGGER.warning("Unexpected error parsing RSS: %s", err)

        return articles

