from __future__ import annotations

import json
import re
from typing import Any

from homeassistant.components.mqtt import async_publish
from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfElectricCurrent
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DOMAIN, HUB_MODEL, HUB_NAME, MANUFACTURER

_VEBUS_AC_IN_LIMIT_RE = re.compile(
    r"^(?P<prefix>[^/]+)/N/(?P<portal>[^/]+)/vebus/(?P<instance>\d+)/Ac/(?P<sub>(?:ActiveIn|In))/CurrentLimit$"
)


def _parse_numeric(payload: dict[str, Any], key: str = "value") -> float | None:
    v = payload.get(key)
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        s = v.strip().replace(",", ".")
        if not s:
            return None
        try:
            return float(s)
        except ValueError:
            return None
    return None


class VictronVeBusAcInCurrentLimit(NumberEntity):
    _attr_has_entity_name = False

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        cfg_slug: str,
        portal_id: str,
        vebus_instance: str,
    ) -> None:
        self.hass = hass
        self._entry = entry
        self._cfg_slug = cfg_slug
        self._portal = portal_id
        self._instance = vebus_instance

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{portal_id}_cerbo_gx")},
            name=HUB_NAME,
            manufacturer=MANUFACTURER,
            model=HUB_MODEL,
        )

        self._attr_name = "VE-Bus AC In Current Limit"
        self._attr_unique_id = f"{portal_id}_vebus_{vebus_instance}_ac_in_current_limit"
        self._attr_suggested_object_id = f"{cfg_slug}_ve_bus_ac_in_current_limit"
        self._attr_native_unit_of_measurement = UnitOfElectricCurrent.AMPERE
        self._attr_native_step = 0.1

    def handle_payload(self, payload: dict[str, Any]) -> None:
        val = _parse_numeric(payload, "value")
        if val is None:
            return

        self._attr_native_value = val

        mn = _parse_numeric(payload, "min")
        mx = _parse_numeric(payload, "max")
        if mn is not None:
            self._attr_native_min_value = mn
        if mx is not None:
            self._attr_native_max_value = mx

        self.async_write_ha_state()

    async def async_set_native_value(self, value: float) -> None:
        prefix = self._entry.data["topic_prefix"]
        topic = f"{prefix}/W/{self._portal}/vebus/{self._instance}/Ac/ActiveIn/CurrentLimit"
        await async_publish(self.hass, topic, json.dumps({"value": value}), qos=0, retain=False)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:
    cfg_name = entry.data.get("name") or entry.title
    cfg_slug = (cfg_name or "victron").strip().lower().replace(" ", "_").replace("-", "_")

    portal = entry.data["portal_id"]
    prefix = entry.data["topic_prefix"]
    signal = hass.data[DOMAIN][entry.entry_id]["signal"]

    runtime = hass.data[DOMAIN][entry.entry_id].setdefault("runtime_number", {"entities": {}})

    @callback
    def _on_message(topic: str, payload: dict[str, Any]) -> None:
        m = _VEBUS_AC_IN_LIMIT_RE.match(topic)
        if not m:
            return
        if m.group("prefix") != prefix or m.group("portal") != portal:
            return

        inst = m.group("instance")
        ent = runtime["entities"].get(inst)
        if ent is None:
            ent = VictronVeBusAcInCurrentLimit(hass, entry, cfg_slug, portal, inst)
            runtime["entities"][inst] = ent
            async_add_entities([ent])

        ent.handle_payload(payload)

    entry.async_on_unload(async_dispatcher_connect(hass, signal, _on_message))
