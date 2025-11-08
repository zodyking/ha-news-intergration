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
        return OptionsFlowHandler()


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for Home Assistant News."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Convert flattened category fields back to nested dict
            enabled_categories_dict = {
                "U.S.": user_input.pop("category_u_s", True),
                "World": user_input.pop("category_world", True),
                "Local": user_input.pop("category_local", True),
                "Business": user_input.pop("category_business", True),
                "Technology": user_input.pop("category_technology", True),
                "Entertainment": user_input.pop("category_entertainment", True),
                "Sports": user_input.pop("category_sports", True),
                "Science": user_input.pop("category_science", True),
                "Health": user_input.pop("category_health", True),
            }
            user_input["enabled_categories"] = enabled_categories_dict
            
            # Save options (no validation needed - just AI setup)
            return self.async_create_entry(title="", data=user_input)

        # Get current options
        config_entry = self.config_entry
        options = config_entry.options or config_entry.data or {}

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
                    "ai_mode",
                    default=options.get("ai_mode", DEFAULTS["ai_mode"]),
                ): vol.In(["auto", "google_generative_ai_conversation", "conversation"]),
                vol.Optional(
                    "conversation_agent_id",
                    default=options.get("conversation_agent_id", DEFAULTS["conversation_agent_id"]),
                ): str,
                # Flatten enabled_categories to avoid nested schema serialization issues
                vol.Optional(
                    "category_u_s",
                    default=enabled_categories.get("U.S.", True),
                ): bool,
                vol.Optional(
                    "category_world",
                    default=enabled_categories.get("World", True),
                ): bool,
                vol.Optional(
                    "category_local",
                    default=enabled_categories.get("Local", True),
                ): bool,
                vol.Optional(
                    "category_business",
                    default=enabled_categories.get("Business", True),
                ): bool,
                vol.Optional(
                    "category_technology",
                    default=enabled_categories.get("Technology", True),
                ): bool,
                vol.Optional(
                    "category_entertainment",
                    default=enabled_categories.get("Entertainment", True),
                ): bool,
                vol.Optional(
                    "category_sports",
                    default=enabled_categories.get("Sports", True),
                ): bool,
                vol.Optional(
                    "category_science",
                    default=enabled_categories.get("Science", True),
                ): bool,
                vol.Optional(
                    "category_health",
                    default=enabled_categories.get("Health", True),
                ): bool,
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=data_schema,
            errors=errors,
        )

