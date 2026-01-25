from __future__ import annotations

import json
import re
from typing import Any

from homeassistant.components.mqtt import async_publish
from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfElectricCurrent, UnitOfElectricPotential, STATE_UNKNOWN, STATE_UNAVAILABLE, UnitOfElectricPotential, STATE_UNKNOWN, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DOMAIN, HUB_MODEL, HUB_NAME, MANUFACTURER

_VEBUS_AC_IN_LIMIT_RE = re.compile(
    r"^(?P<prefix>[^/]+)/N/(?P<portal>[^/]+)/vebus/(?P<instance>\d+)/Ac/(?P<sub>(?:ActiveIn|In))/CurrentLimit$"
)

_DVCC_MAX_CHARGE_VOLTAGE_RE = re.compile(
    r"^(?P<prefix>[^/]+)/N/(?P<portal>[^/]+)/settings/(?P<sid>\d+)/Settings/SystemSetup/MaxChargeVoltage$"
)
_DVCC_MAX_CHARGE_CURRENT_RE = re.compile(
    r"^(?P<prefix>[^/]+)/N/(?P<portal>[^/]+)/settings/(?P<sid>\d+)/Settings/SystemSetup/MaxChargeCurrent$"
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


class _VictronRestoreNumber(NumberEntity, RestoreEntity):
    """Number entity that restores last known value if broker does not publish retained values."""

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last = await self.async_get_last_state()
        if last is None:
            return
        if last.state in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            return
        try:
            self._attr_native_value = float(str(last.state).replace(",", "."))
            self.async_write_ha_state()
        except (ValueError, TypeError):
            return


class VictronVeBusAcInCurrentLimit(_VictronRestoreNumber):
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



class VictronDvccMaxChargeVoltage(_VictronRestoreNumber):
    _attr_has_entity_name = False

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, cfg_slug: str, portal_id: str, settings_id: str) -> None:
        self.hass = hass
        self._entry = entry
        self._cfg_slug = cfg_slug
        self._portal = portal_id
        self._sid = settings_id

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{portal_id}_cerbo_gx")},
            name=HUB_NAME,
            manufacturer=MANUFACTURER,
            model=HUB_MODEL,
        )

        self._attr_name = "VE-Bus Battery DVCC Max Charge Voltage"
        self._attr_unique_id = f"{portal_id}_settings_{settings_id}_dvcc_max_charge_voltage"
        self._attr_suggested_object_id = f"{cfg_slug}_ve_bus_battery_dvcc_max_charge_voltage"
        self._attr_native_unit_of_measurement = UnitOfElectricPotential.VOLT
        self._attr_native_step = 0.01
        self._attr_suggested_display_precision = 2

    def handle_payload(self, payload: dict[str, Any]) -> None:
        val = _parse_numeric(payload, "value")
        if val is None:
            return
        self._attr_native_value = round(val, 2)

        mn = _parse_numeric(payload, "min")
        mx = _parse_numeric(payload, "max")
        if mn is not None:
            self._attr_native_min_value = mn
        if mx is not None:
            self._attr_native_max_value = mx

        self.async_write_ha_state()

    async def async_set_native_value(self, value: float) -> None:
        prefix = self._entry.data["topic_prefix"]
        topic = f"{prefix}/W/{self._portal}/settings/{self._sid}/Settings/SystemSetup/MaxChargeVoltage"
        await async_publish(self.hass, topic, json.dumps({"value": round(float(value), 2)}), qos=0, retain=False)


class VictronDvccMaxChargeCurrent(_VictronRestoreNumber):
    _attr_has_entity_name = False

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, cfg_slug: str, portal_id: str, settings_id: str) -> None:
        self.hass = hass
        self._entry = entry
        self._cfg_slug = cfg_slug
        self._portal = portal_id
        self._sid = settings_id

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{portal_id}_cerbo_gx")},
            name=HUB_NAME,
            manufacturer=MANUFACTURER,
            model=HUB_MODEL,
        )

        self._attr_name = "VE-Bus Battery DVCC Max Charge Current"
        self._attr_unique_id = f"{portal_id}_settings_{settings_id}_dvcc_max_charge_current"
        self._attr_suggested_object_id = f"{cfg_slug}_ve_bus_battery_dvcc_max_charge_current"
        self._attr_native_unit_of_measurement = UnitOfElectricCurrent.AMPERE
        self._attr_native_step = 1
        self._attr_suggested_display_precision = 0

    def handle_payload(self, payload: dict[str, Any]) -> None:
        val = _parse_numeric(payload, "value")
        if val is None:
            return
        self._attr_native_value = int(round(val))

        mn = _parse_numeric(payload, "min")
        mx = _parse_numeric(payload, "max")
        if mn is not None:
            self._attr_native_min_value = mn
        if mx is not None:
            self._attr_native_max_value = mx

        self.async_write_ha_state()

    async def async_set_native_value(self, value: float) -> None:
        prefix = self._entry.data["topic_prefix"]
        topic = f"{prefix}/W/{self._portal}/settings/{self._sid}/Settings/SystemSetup/MaxChargeCurrent"
        await async_publish(self.hass, topic, json.dumps({"value": int(round(float(value)))}), qos=0, retain=False)



async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:
    cfg_name = entry.data.get("name") or entry.title
    cfg_slug = (cfg_name or "victron").strip().lower().replace(" ", "_").replace("-", "_")

    portal = entry.data["portal_id"]
    prefix = entry.data["topic_prefix"]
    signal = hass.data[DOMAIN][entry.entry_id]["signal"]

    runtime = hass.data[DOMAIN][entry.entry_id].setdefault("runtime_number", {"entities": {}})

    # Create DVCC entities proactively (settings id 0) so they are visible even if the broker
    # does not publish retained values on startup.
    sid0 = "0"
    if ("dvcc_v", sid0) not in runtime["entities"]:
        ent_v = VictronDvccMaxChargeVoltage(hass, entry, cfg_slug, portal, sid0)
        runtime["entities"][("dvcc_v", sid0)] = ent_v
        async_add_entities([ent_v])
    if ("dvcc_a", sid0) not in runtime["entities"]:
        ent_a = VictronDvccMaxChargeCurrent(hass, entry, cfg_slug, portal, sid0)
        runtime["entities"][("dvcc_a", sid0)] = ent_a
        async_add_entities([ent_a])


    @callback
    def _on_message(topic: str, payload: dict[str, Any]) -> None:
        # VE.Bus AC In Current Limit
        m = _VEBUS_AC_IN_LIMIT_RE.match(topic)
        if m:
            if m.group("prefix") == prefix and m.group("portal") == portal:
                inst = m.group("instance")
                ent = runtime["entities"].get(("ac_in_limit", inst))
                if ent is None:
                    ent = VictronVeBusAcInCurrentLimit(hass, entry, cfg_slug, portal, inst)
                    runtime["entities"][("ac_in_limit", inst)] = ent
                    async_add_entities([ent])
                ent.handle_payload(payload)
            return

        # DVCC Max Charge Voltage (settings)
        m = _DVCC_MAX_CHARGE_VOLTAGE_RE.match(topic)
        if m:
            if m.group("prefix") == prefix and m.group("portal") == portal:
                sid = m.group("sid")
                ent = runtime["entities"].get(("dvcc_v", sid))
                if ent is None:
                    ent = VictronDvccMaxChargeVoltage(hass, entry, cfg_slug, portal, sid)
                    runtime["entities"][("dvcc_v", sid)] = ent
                    async_add_entities([ent])
                ent.handle_payload(payload)
            return

        # DVCC Max Charge Current (settings)
        m = _DVCC_MAX_CHARGE_CURRENT_RE.match(topic)
        if m:
            if m.group("prefix") == prefix and m.group("portal") == portal:
                sid = m.group("sid")
                ent = runtime["entities"].get(("dvcc_a", sid))
                if ent is None:
                    ent = VictronDvccMaxChargeCurrent(hass, entry, cfg_slug, portal, sid)
                    runtime["entities"][("dvcc_a", sid)] = ent
                    async_add_entities([ent])
                ent.handle_payload(payload)
            return

    entry.async_on_unload(async_dispatcher_connect(hass, signal, _on_message))

