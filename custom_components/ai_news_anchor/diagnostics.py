"""Diagnostics support for AI News Anchor."""
from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = hass.data[DOMAIN].get(entry.entry_id)

    if not coordinator:
        return {"error": "Coordinator not found"}

    data = coordinator.data
    options = entry.options

    # Build diagnostics without full article text
    diagnostics = {
        "config": {
            "scan_interval": options.get("scan_interval"),
            "max_per_category": options.get("max_per_category"),
            "local_geo": options.get("local_geo"),
            "tts_entity": options.get("tts_entity"),
            "media_players": options.get("media_players", []),
            "ai_mode": options.get("ai_mode"),
            "preroll_ms": options.get("preroll_ms"),
            "enabled_categories": options.get("enabled_categories", {}),
        },
        "coordinator": {
            "last_update_success": coordinator.last_update_success,
            "last_update_success_time": (
                coordinator.last_update_success_time.isoformat()
                if coordinator.last_update_success_time
                else None
            ),
            "last_exception": str(coordinator.last_exception)
            if coordinator.last_exception
            else None,
        },
        "categories": {},
    }

    # Add category counts and article titles (not full text)
    for category, articles in data.items():
        diagnostics["categories"][category] = {
            "count": len(articles),
            "articles": [
                {"title": art["title"], "summary_length": len(art.get("summary", ""))}
                for art in articles
            ],
        }

    return diagnostics


