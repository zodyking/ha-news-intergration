"""Sensor platform for Home Assistant News."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import NewsCoordinator

_LOGGER = logging.getLogger(__name__)

CATEGORIES = [
    "U.S.",
    "World",
    "Local",
    "Business",
    "Technology",
    "Entertainment",
    "Sports",
    "Science",
    "Health",
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Home Assistant News sensors from a config entry."""
    coordinator: NewsCoordinator = hass.data[DOMAIN][entry.entry_id]

    # Create a sensor for each category
    sensors = []
    for category in CATEGORIES:
        sensors.append(
            NewsCategorySensor(
                coordinator=coordinator,
                entry=entry,
                category=category,
            )
        )
    
    # Create sensors for custom sources
    custom_sources = entry.options.get("custom_sources", [])
    for source in custom_sources:
        sensors.append(
            NewsCategorySensor(
                coordinator=coordinator,
                entry=entry,
                category=source.get("name", ""),
                is_custom=True,
            )
        )

    async_add_entities(sensors)


class NewsCategorySensor(
    CoordinatorEntity[NewsCoordinator], SensorEntity
):
    """Sensor representing news articles for a specific category."""

    def __init__(
        self,
        coordinator: NewsCoordinator,
        entry: ConfigEntry,
        category: str,
        is_custom: bool = False,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._category = category
        self._is_custom = is_custom
        # Create entity ID friendly name
        category_slug = category.lower().replace('.', '').replace(' ', '_').replace('-', '_')
        self._attr_name = f"Home Assistant News {category}"
        self._attr_unique_id = f"{entry.entry_id}_{category_slug}"
        self._attr_icon = "mdi:newspaper-variant-multiple"
        self._attr_entity_registry_enabled_default = True

    @property
    def native_value(self) -> int:
        """Return the number of articles in this category."""
        if not self.coordinator.data:
            return 0
        articles = self.coordinator.data.get(self._category, [])
        return len(articles)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        if not self.coordinator.data:
            return {
                "article_count": 0,
            }

        articles = self.coordinator.data.get(self._category, [])
        attrs: dict[str, Any] = {
            "article_count": len(articles),
        }
        
        # Format as Story 1 Title, Story 1 Article, etc. (up to 10 stories)
        # Don't include title in article text - just the article content
        for i, article in enumerate(articles[:10], start=1):
            attrs[f"Story {i} Title"] = article.get("title", "")
            # Only include the article content, not the title
            article_content = article.get("summary", "").strip()
            # Remove title if it appears at the start of the content
            title = article.get("title", "")
            if title and article_content.startswith(title):
                article_content = article_content[len(title):].strip()
            attrs[f"Story {i} Article"] = article_content
        
        return attrs

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success

