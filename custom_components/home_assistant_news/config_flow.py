"""Config flow for Home Assistant News."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_validation as cv, entity_registry as er

from .const import CATEGORY_MAP, DEFAULTS, DOMAIN

_LOGGER = logging.getLogger(__name__)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Home Assistant News."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is not None:
            return self.async_create_entry(title="Home Assistant News", data={})

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({}),
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> OptionsFlowHandler:
        """Get the options flow for this handler."""
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for Home Assistant News."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Validate
            if not user_input.get("tts_entity"):
                errors["base"] = "tts_entity_required"
            elif not user_input.get("media_players"):
                errors["base"] = "media_players_required"
            else:
                # Save options
                return self.async_create_entry(title="", data=user_input)

        # Get current options
        config_entry = self._config_entry
        options = config_entry.options or config_entry.data or {}

        # Get available entities
        entity_reg = er.async_get(self.hass)
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

        # Build enabled categories dict
        enabled_categories = options.get(
            "enabled_categories",
            DEFAULTS["enabled_categories"],
        )

        data_schema = vol.Schema(
            {
                vol.Required(
                    "local_geo",
                    default=options.get("local_geo", DEFAULTS["local_geo"]),
                ): str,
                vol.Required(
                    "max_per_category",
                    default=options.get("max_per_category", DEFAULTS["max_per_category"]),
                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=3)),
                vol.Required(
                    "scan_interval",
                    default=options.get("scan_interval", DEFAULTS["scan_interval"]),
                ): vol.All(vol.Coerce(int), vol.Range(min=600, max=7200)),
                vol.Required(
                    "tts_entity",
                    default=options.get("tts_entity", DEFAULTS["tts_entity"]),
                ): vol.In(tts_entities + [""]) if tts_entities else str,
                vol.Required(
                    "media_players",
                    default=options.get("media_players", DEFAULTS["media_players"]),
                ): vol.All(
                    cv.multi_select(media_player_entities) if media_player_entities else [str],
                    vol.Length(min=1),
                ),
                vol.Required(
                    "ai_mode",
                    default=options.get("ai_mode", DEFAULTS["ai_mode"]),
                ): vol.In(["auto", "google_generative_ai_conversation", "conversation"]),
                vol.Optional(
                    "conversation_agent_id",
                    default=options.get("conversation_agent_id", DEFAULTS["conversation_agent_id"]),
                ): str,
                vol.Required(
                    "preroll_ms",
                    default=options.get("preroll_ms", DEFAULTS["preroll_ms"]),
                ): vol.All(vol.Coerce(int), vol.Range(min=0, max=300)),
                vol.Required(
                    "enabled_categories",
                    default=enabled_categories,
                ): vol.Schema(
                    {
                        vol.Optional("U.S.", default=enabled_categories.get("U.S.", True)): bool,
                        vol.Optional("World", default=enabled_categories.get("World", True)): bool,
                        vol.Optional("Local", default=enabled_categories.get("Local", True)): bool,
                        vol.Optional("Business", default=enabled_categories.get("Business", True)): bool,
                        vol.Optional("Technology", default=enabled_categories.get("Technology", True)): bool,
                        vol.Optional("Entertainment", default=enabled_categories.get("Entertainment", True)): bool,
                        vol.Optional("Sports", default=enabled_categories.get("Sports", True)): bool,
                        vol.Optional("Science", default=enabled_categories.get("Science", True)): bool,
                        vol.Optional("Health", default=enabled_categories.get("Health", True)): bool,
                    }
                ),
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=data_schema,
            errors=errors,
        )

