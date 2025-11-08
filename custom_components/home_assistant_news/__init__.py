"""Home Assistant News integration."""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

from aiohttp import web
from homeassistant.components.http import HomeAssistantView
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import entity_registry as er
from homeassistant.components import persistent_notification
from homeassistant.util import dt as dt_util

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
    # Register API endpoints (only once)
    if "_views_registered" not in hass.data[DOMAIN]:
        # Views are defined at the bottom of this file
        hass.http.register_view(AINewsAnchorConfigView)
        hass.http.register_view(AINewsAnchorEntitiesView)
        hass.http.register_view(AINewsAnchorRefreshView)
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

    # Register service
    async def handle_play_briefing(call: ServiceCall) -> None:
        """Handle the play_briefing service call."""
        try:
            await _play_briefing(hass, entry, call)
        except Exception as err:
            _LOGGER.exception("Error in play_briefing service: %s", err)
            persistent_notification.create(
                hass,
                f"Home Assistant News error: {err}",
                "Home Assistant News",
                notification_id=f"{DOMAIN}_error",
            )

    hass.services.async_register(DOMAIN, "play_briefing", handle_play_briefing)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
        hass.services.async_remove(DOMAIN, "play_briefing")
    return unload_ok


async def _play_briefing(
    hass: HomeAssistant, entry: ConfigEntry, call: ServiceCall
) -> None:
    """Play a news briefing."""
    from .summarizer import async_generate_briefing

    coordinator: NewsCoordinator = hass.data[DOMAIN][entry.entry_id]

    # Update options from service call
    max_per_category = call.data.get(
        "override_max_per_category",
        entry.options.get("max_per_category", 2),
    )
    media_players = call.data.get(
        "override_media_players",
        entry.options.get("media_players", []),
    )
    preroll_ms = call.data.get(
        "override_preroll_ms",
        entry.options.get("preroll_ms", 150),
    )
    tts_entity = entry.options.get("tts_entity", "")
    ai_mode = entry.options.get("ai_mode", "auto")
    agent_id = entry.options.get("conversation_agent_id", "")

    # Validate required settings
    if not tts_entity:
        persistent_notification.create(
            hass,
            "Home Assistant News: TTS entity not configured. Please configure it in integration options.",
            "Home Assistant News",
            notification_id=f"{DOMAIN}_config_error",
        )
        return

    if not media_players:
        persistent_notification.create(
            hass,
            "Home Assistant News: No media players configured. Please configure at least one in integration options.",
            "Home Assistant News",
            notification_id=f"{DOMAIN}_config_error",
        )
        return

    # Check if data is stale and refresh if needed
    scan_interval = entry.options.get("scan_interval", 1800)
    if coordinator.last_update_success:
        last_update = coordinator.last_update_success_time
        if last_update:
            age = (dt_util.utcnow() - last_update).total_seconds()
            if age > scan_interval:
                _LOGGER.info("Data is stale (%.0f seconds old), refreshing", age)
                await coordinator.async_request_refresh()

    # Get current data
    data = coordinator.data

    # Build ordered category list
    category_order = [
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

    # Build JSON payload with only categories that have articles
    payload = []
    for category in category_order:
        if category in data and data[category]:
            articles = data[category][:max_per_category]
            payload.append(
                {
                    "category": category,
                    "articles": [
                        {"title": art["title"], "summary": art["summary"]}
                        for art in articles
                    ],
                }
            )

    if not payload:
        persistent_notification.create(
            hass,
            "Home Assistant News: No items to brief. Check your enabled categories and RSS feeds.",
            "Home Assistant News",
            notification_id=f"{DOMAIN}_no_items",
        )
        return

    # Determine greeting based on local time
    now = dt_util.now()
    hour = now.hour
    if 5 <= hour < 12:
        greeting = "morning"
    elif 12 <= hour < 18:
        greeting = "afternoon"
    else:
        greeting = "night"

    # Generate script
    try:
        script_text = await async_generate_briefing(
            hass,
            payload,
            greeting,
            max_per_category,
            ai_mode,
            agent_id,
        )
    except RuntimeError as err:
        error_msg = str(err)
        persistent_notification.create(
            hass,
            f"Home Assistant News: {error_msg}",
            "Home Assistant News",
            notification_id=f"{DOMAIN}_ai_error",
        )
        _LOGGER.error("AI generation failed: %s", err)
        return

    if not script_text or not script_text.strip():
        persistent_notification.create(
            hass,
            "Home Assistant News: Generated script is empty.",
            "Home Assistant News",
            notification_id=f"{DOMAIN}_empty_script",
        )
        return

    # Play on each media player
    for player in media_players:
        try:
            # Pre-roll delay
            if preroll_ms > 0:
                await asyncio.sleep(preroll_ms / 1000.0)

            # Call TTS service
            await hass.services.async_call(
                "tts",
                "speak",
                {
                    "entity_id": tts_entity,
                    "media_player_entity_id": player,
                    "cache": False,
                    "message": script_text,
                },
                blocking=True,
            )
            _LOGGER.info("Playing briefing on %s", player)
        except Exception as err:
            _LOGGER.error("Error playing on %s: %s", player, err)


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
            "tts_entity": entry.options.get("tts_entity", ""),
            "media_players": entry.options.get("media_players", []),
            "ai_mode": entry.options.get("ai_mode", "auto"),
            "conversation_agent_id": entry.options.get("conversation_agent_id", ""),
            "preroll_ms": entry.options.get("preroll_ms", 150),
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
            
            return self.json({"success": True})
        except Exception as err:
            _LOGGER.exception("Error updating config: %s", err)
            return self.json({"error": str(err)}, status_code=400)


class AINewsAnchorEntitiesView(HomeAssistantView):
    """View to get available entities."""

    url = "/api/home_assistant_news/entities"
    name = "api:home_assistant_news:entities"
    requires_auth = True

    async def get(self, request: web.Request) -> web.Response:
        """Get available TTS and media player entities."""
        hass: HomeAssistant = request.app["hass"]
        entity_reg = er.async_get(hass)

        tts_entities = [
            entity.entity_id
            for entity in entity_reg.entities.values()
            if entity.domain == "tts"
        ]
        media_player_entities = [
            entity.entity_id
            for entity in entity_reg.entities.values()
            if entity.domain == "media_player"
        ]

        return self.json(
            {
                "tts": sorted(tts_entities),
                "media_players": sorted(media_player_entities),
            }
        )


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

