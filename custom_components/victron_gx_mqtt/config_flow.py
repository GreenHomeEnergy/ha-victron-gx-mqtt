from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback

from .const import DOMAIN

CONF_NAME = "name"


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Victron GX MQTT."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """First step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            name = (user_input.get(CONF_NAME) or "").strip() or "Victron GX MQTT"

            # Make multiple installs possible by including name in unique_id
            await self.async_set_unique_id(f"victron_gx_mqtt_{name.lower()}")
            self._abort_if_unique_id_configured()

            return self.async_create_entry(title=name, data={CONF_NAME: name})

        schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default="Zuhause"): str,
            }
        )

        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Options flow (MVP: no options yet)."""

    def __init__(self, config_entry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(step_id="init", data_schema=vol.Schema({}))
