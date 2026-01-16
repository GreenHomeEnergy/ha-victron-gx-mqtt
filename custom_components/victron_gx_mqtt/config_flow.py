from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    DOMAIN,
    CONF_NAME,
    CONF_TOPIC_PREFIX,
    CONF_PORTAL_ID,
    CONF_SELECTED_SERVICES,
    SERVICE_VEBUS,
    SERVICE_SYSTEM,
    SERVICE_SOLARCHARGER,
    SERVICE_BATTERY,
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Victron GX MQTT."""

    VERSION = 1

    def __init__(self) -> None:
        self._base_data: dict = {}

    async def async_step_user(self, user_input=None):
        errors: dict[str, str] = {}

        if user_input is not None:
            name = (user_input.get(CONF_NAME) or "").strip() or "Victron GX MQTT"
            prefix = (user_input.get(CONF_TOPIC_PREFIX) or "").strip().strip("/")
            portal_id = (user_input.get(CONF_PORTAL_ID) or "").strip()

            if not prefix:
                errors[CONF_TOPIC_PREFIX] = "required"
            if not portal_id:
                errors[CONF_PORTAL_ID] = "required"

            if not errors:
                self._base_data = {
                    CONF_NAME: name,
                    CONF_TOPIC_PREFIX: prefix,
                    CONF_PORTAL_ID: portal_id,
                }
                return await self.async_step_services()

        schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default="Zuhause"): selector.TextSelector(
                    selector.TextSelectorConfig()
                ),
                vol.Required(CONF_TOPIC_PREFIX, default="venus-home"): selector.TextSelector(
                    selector.TextSelectorConfig()
                ),
                vol.Required(CONF_PORTAL_ID): selector.TextSelector(
                    selector.TextSelectorConfig()
                ),
            }
        )

        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_services(self, user_input=None):
        if user_input is not None:
            selected = user_input.get(CONF_SELECTED_SERVICES, [])
            title = self._base_data.get(CONF_NAME, "Victron GX MQTT")

            unique_id = f"{self._base_data[CONF_TOPIC_PREFIX]}::{self._base_data[CONF_PORTAL_ID]}".lower()
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=title,
                data=self._base_data,
                options={CONF_SELECTED_SERVICES: selected},
            )

        schema = vol.Schema(
            {
                vol.Required(CONF_SELECTED_SERVICES, default=[SERVICE_VEBUS]): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            {"value": SERVICE_VEBUS, "label": "VE.Bus (Basis)"},
                            {"value": SERVICE_SYSTEM, "label": "System (später)"},
                            {"value": SERVICE_SOLARCHARGER, "label": "Solar Charger (später)"},
                            {"value": SERVICE_BATTERY, "label": "Battery (später)"},
                        ],
                        multiple=True,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                )
            }
        )

        return self.async_show_form(step_id="services", data_schema=schema)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Options flow: allow changing selected services."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._entry = config_entry

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = self._entry.options.get(CONF_SELECTED_SERVICES, [SERVICE_VEBUS])

        schema = vol.Schema(
            {
                vol.Required(CONF_SELECTED_SERVICES, default=current): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            {"value": SERVICE_VEBUS, "label": "VE.Bus (Basis)"},
                            {"value": SERVICE_SYSTEM, "label": "System (später)"},
                            {"value": SERVICE_SOLARCHARGER, "label": "Solar Charger (später)"},
                            {"value": SERVICE_BATTERY, "label": "Battery (später)"},
                        ],
                        multiple=True,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                )
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
