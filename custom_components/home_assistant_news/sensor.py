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
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._category = category
        self._attr_name = f"Home Assistant News {category}"
        self._attr_unique_id = f"{entry.entry_id}_{category.lower().replace('.', '').replace(' ', '_')}"
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
                "articles": [],
                "article_count": 0,
            }

        articles = self.coordinator.data.get(self._category, [])
        
        return {
            "articles": [
                {
                    "title": article.get("title", ""),
                    "summary": article.get("summary", ""),
                }
                for article in articles
            ],
            "article_count": len(articles),
        }

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success

