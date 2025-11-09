"""Home Assistant News integration."""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

import os
from aiohttp import web
from homeassistant.components.http import HomeAssistantView
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN
from .coordinator import NewsCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[str] = ["sensor"]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Home Assistant News integration."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Home Assistant News from a config entry."""
    # Register API endpoints and static path (only once)
    if "_views_registered" not in hass.data[DOMAIN]:
        # Views are defined at the bottom of this file
        hass.http.register_view(AINewsAnchorConfigView)
        hass.http.register_view(AINewsAnchorRefreshView)
        
        # Register static path for panel HTML
        panel_path = os.path.join(
            os.path.dirname(__file__), "www", "home_assistant_news", "panel.html"
        )
        if os.path.exists(panel_path):
            hass.http.register_static_path(
                "/local/home_assistant_news/panel.html",
                panel_path,
                cache_headers=False,
            )
        
        hass.data[DOMAIN]["_views_registered"] = True
    
    coordinator = NewsCoordinator(
        hass,
        scan_interval=entry.options.get("scan_interval", 1800),
        max_per_category=entry.options.get("max_per_category", 2),
        local_geo=entry.options.get("local_geo", "New York, NY"),
        enabled_categories=entry.options.get(
            "enabled_categories",
            {
                "U.S.": True,
                "World": True,
                "Local": True,
                "Business": True,
                "Technology": True,
                "Entertainment": True,
                "Sports": True,
                "Science": True,
                "Health": True,
            },
        ),
        custom_sources=entry.options.get("custom_sources", []),
    )

    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Forward entry setup to sensor platform
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Start initial fetch
    await coordinator.async_config_entry_first_refresh()

    # Update coordinator when options change
    async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Handle options update."""
        old_custom_sources = coordinator._custom_sources
        coordinator._max_per_category = entry.options.get("max_per_category", 2)
        coordinator._local_geo = entry.options.get("local_geo", "New York, NY")
        coordinator._enabled_categories = entry.options.get(
            "enabled_categories",
            {
                "U.S.": True,
                "World": True,
                "Local": True,
                "Business": True,
                "Technology": True,
                "Entertainment": True,
                "Sports": True,
                "Science": True,
                "Health": True,
            },
        )
        coordinator._custom_sources = entry.options.get("custom_sources", [])
        coordinator.update_interval = timedelta(
            seconds=entry.options.get("scan_interval", 1800)
        )
        
        # If custom sources changed, reload the entry to recreate sensors
        if old_custom_sources != coordinator._custom_sources:
            await hass.config_entries.async_reload(entry.entry_id)
        else:
            await coordinator.async_request_refresh()

    entry.async_on_unload(entry.add_update_listener(update_listener))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


class AINewsAnchorConfigView(HomeAssistantView):
    """View to handle config API requests."""

    url = "/api/home_assistant_news/config"
    name = "api:home_assistant_news:config"
    requires_auth = True

    async def get(self, request: web.Request) -> web.Response:
        """Get current configuration."""
        hass: HomeAssistant = request.app["hass"]
        entries = hass.config_entries.async_entries(DOMAIN)
        if not entries:
            return self.json({"error": "No config entry found"}, status_code=404)

        entry = entries[0]
        config = {
            "entry_id": entry.entry_id,
            "local_geo": entry.options.get("local_geo", "New York, NY"),
            "max_per_category": entry.options.get("max_per_category", 2),
            "scan_interval": entry.options.get("scan_interval", 1800),
            "ai_mode": entry.options.get("ai_mode", "auto"),
            "conversation_agent_id": entry.options.get("conversation_agent_id", ""),
            "enabled_categories": entry.options.get(
                "enabled_categories",
                {
                    "U.S.": True,
                    "World": True,
                    "Local": True,
                    "Business": True,
                    "Technology": True,
                    "Entertainment": True,
                    "Sports": True,
                    "Science": True,
                    "Health": True,
                },
            ),
            "custom_sources": entry.options.get("custom_sources", []),
        }
        return self.json(config)

    async def post(self, request: web.Request) -> web.Response:
        """Update configuration."""
        hass: HomeAssistant = request.app["hass"]
        entries = hass.config_entries.async_entries(DOMAIN)
        if not entries:
            return self.json({"error": "No config entry found"}, status_code=404)

        entry = entries[0]
        data = await request.json()

        try:
            # Ensure enabled_categories is properly formatted
            if "enabled_categories" not in data or not isinstance(data["enabled_categories"], dict):
                # If not provided, use defaults
                data["enabled_categories"] = entry.options.get(
                    "enabled_categories",
                    {
                        "U.S.": True,
                        "World": True,
                        "Local": True,
                        "Business": True,
                        "Technology": True,
                        "Entertainment": True,
                        "Sports": True,
                        "Science": True,
                        "Health": True,
                    },
                )
            
            # Update options
            hass.config_entries.async_update_entry(entry, options=data)
            
            # Trigger coordinator update
            if entry.entry_id in hass.data[DOMAIN]:
                coordinator = hass.data[DOMAIN][entry.entry_id]
                coordinator._local_geo = data.get("local_geo", coordinator._local_geo)
                coordinator._max_per_category = data.get("max_per_category", coordinator._max_per_category)
                coordinator._enabled_categories = data.get("enabled_categories", coordinator._enabled_categories)
                coordinator._custom_sources = data.get("custom_sources", [])
                coordinator.update_interval = timedelta(
                    seconds=data.get("scan_interval", entry.options.get("scan_interval", 1800))
                )
            
            return self.json({"success": True})
        except Exception as err:
            _LOGGER.exception("Error updating config: %s", err)
            return self.json({"error": str(err)}, status_code=400)




class AINewsAnchorRefreshView(HomeAssistantView):
    """View to manually refresh news data."""

    url = "/api/home_assistant_news/refresh"
    name = "api:home_assistant_news:refresh"
    requires_auth = True

    async def post(self, request: web.Request) -> web.Response:
        """Trigger a manual refresh of news data."""
        hass: HomeAssistant = request.app["hass"]
        entries = hass.config_entries.async_entries(DOMAIN)
        if not entries:
            return self.json({"error": "No config entry found"}, status_code=404)

        entry = entries[0]
        
        try:
            if entry.entry_id in hass.data[DOMAIN]:
                coordinator = hass.data[DOMAIN][entry.entry_id]
                await coordinator.async_request_refresh()
                return self.json({"success": True, "message": "Refresh triggered"})
            else:
                return self.json({"error": "Coordinator not found"}, status_code=404)
        except Exception as err:
            _LOGGER.exception("Error refreshing data: %s", err)
            return self.json({"error": str(err)}, status_code=500)

