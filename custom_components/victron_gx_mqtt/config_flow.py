from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN, CONF_NAME, CONF_TOPIC_PREFIX, CONF_PORTAL_ID


def _normalize_prefix(prefix: str) -> str:
    prefix = (prefix or "").strip().strip("/")
    return prefix


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

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
