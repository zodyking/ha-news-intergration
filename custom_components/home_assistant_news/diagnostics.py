"""Diagnostics support for Home Assistant News."""
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
            "ai_mode": options.get("ai_mode"),
            "conversation_agent_id": options.get("conversation_agent_id"),
            "enabled_categories": options.get("enabled_categories", {}),
            "custom_sources": options.get("custom_sources", []),
        },
        "coordinator": {
            "last_update_success": coordinator.last_update_success,
            "last_update_time": (
                coordinator.last_update_time.isoformat()
                if coordinator.last_update_time
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


