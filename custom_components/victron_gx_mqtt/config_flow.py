from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN, CONF_NAME, CONF_TOPIC_PREFIX, CONF_PORTAL_ID, CONF_ENABLE_AC_LOAD


def _normalize_prefix(prefix: str) -> str:
    prefix = (prefix or "").strip().strip("/")
    return prefix


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        return OptionsFlowHandler(config_entry)

    async def async_step_user(self, user_input=None) -> FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            name = (user_input[CONF_NAME] or "").strip()
            topic_prefix = _normalize_prefix(user_input[CONF_TOPIC_PREFIX])
            portal_id = (user_input[CONF_PORTAL_ID] or "").strip()

            if not name:
                errors[CONF_NAME] = "required"
            if not topic_prefix:
                errors[CONF_TOPIC_PREFIX] = "required"
            if not portal_id:
                errors[CONF_PORTAL_ID] = "required"

            if not errors:
                await self.async_set_unique_id(f"{topic_prefix}:{portal_id}")
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=name,
                    data={
                        CONF_NAME: name,
                        CONF_TOPIC_PREFIX: topic_prefix,
                        CONF_PORTAL_ID: portal_id,
                    },
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default="home"): str,
                vol.Required(CONF_TOPIC_PREFIX, default="venus-home"): str,
                vol.Required(CONF_PORTAL_ID): str,
            }
        )

        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options for Victron GX MQTT."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._config_entry = config_entry

    async def async_step_init(self, user_input=None) -> FlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_ENABLE_AC_LOAD,
                    default=self._config_entry.options.get(CONF_ENABLE_AC_LOAD, False),
                ): bool,
            }
        )

        return self.async_show_form(step_id="init", data_schema=schema)
