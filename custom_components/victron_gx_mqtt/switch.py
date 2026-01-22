from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.components import mqtt

from .const import (
    DOMAIN,
    CONF_NAME,
    CONF_TOPIC_PREFIX,
    CONF_PORTAL_ID,
    MANUFACTURER,
    HUB_NAME,
    HUB_MODEL,
)

# Victron VE.Bus Mode topic (read)
# <prefix>/N/<portal_id>/vebus/<instance>/Mode
_VEBUS_MODE_RE = re.compile(
    r"^(?P<prefix>[^/]+)/N/(?P<portal>[^/]+)/vebus/(?P<instance>\d+)/Mode$"
)


@dataclass
class _Runtime:
    # per vebus instance
    emergency: dict[str, "VictronVeBusEmergencyShutdownSwitch"]
    grid: dict[str, "VictronVeBusGridActiveSwitch"]


def _slug(text: str) -> str:
    """Deterministic slug for cfg_name.

    Keep local to avoid depending on frontend slug rules.
    """
    text = (text or "").strip().lower()
    out: list[str] = []
    prev_us = False
    for ch in text:
        ok = ("a" <= ch <= "z") or ("0" <= ch <= "9")
        if ok:
            out.append(ch)
            prev_us = False
        else:
            if not prev_us:
                out.append("_")
                prev_us = True
    s = "".join(out).strip("_")
    return s or "home"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    cfg_name: str = (entry.title or entry.data.get(CONF_NAME) or "home")
    cfg_slug: str = _slug(cfg_name)

    prefix: str = entry.data[CONF_TOPIC_PREFIX]
    portal: str = entry.data[CONF_PORTAL_ID]

    runtime: _Runtime = hass.data[DOMAIN][entry.entry_id].setdefault(
        "switch_runtime",
        _Runtime(emergency={}, grid={}),
    )

    signal: str = hass.data[DOMAIN][entry.entry_id]["signal"]

    @callback
    def _on_message(topic: str, payload: dict[str, Any]) -> None:
        m = _VEBUS_MODE_RE.match(topic)
        if not m:
            return
        if m.group("prefix") != prefix or m.group("portal") != portal:
            return

        inst = m.group("instance")

        # Emergency shutdown switch (Mode -> 4)
        ent_em = runtime.emergency.get(inst)
        if ent_em is None:
            ent_em = VictronVeBusEmergencyShutdownSwitch(
                hass=hass,
                entry=entry,
                cfg_slug=cfg_slug,
                topic_prefix=prefix,
                portal_id=portal,
                vebus_instance=inst,
            )
            runtime.emergency[inst] = ent_em
            async_add_entities([ent_em])

        # Grid active switch (Mode -> 3)
        ent_grid = runtime.grid.get(inst)
        if ent_grid is None:
            ent_grid = VictronVeBusGridActiveSwitch(
                hass=hass,
                entry=entry,
                cfg_slug=cfg_slug,
                topic_prefix=prefix,
                portal_id=portal,
                vebus_instance=inst,
            )
            runtime.grid[inst] = ent_grid
            async_add_entities([ent_grid])

        # Update both from the same Mode payload
        ent_em.handle_mode(payload)
        ent_grid.handle_mode(payload)

    async_dispatcher_connect(hass, signal, _on_message)


class _BaseVeBusModeSwitch(SwitchEntity):
    """Base class for VE.Bus mode derived switches."""

    _attr_has_entity_name = False

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        cfg_slug: str,
        topic_prefix: str,
        portal_id: str,
        vebus_instance: str,
    ) -> None:
        self.hass = hass
        self._entry = entry
        self._cfg_slug = cfg_slug
        self._prefix = topic_prefix
        self._portal = portal_id
        self._instance = vebus_instance

        self._mode_code: int | None = None

        # Single HA device per installation (Cerbo GX).
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{portal_id}_cerbo_gx")},
            name=HUB_NAME,
            manufacturer=MANUFACTURER,
            model=HUB_MODEL,
        )

    @callback
    def handle_mode(self, payload: dict[str, Any]) -> None:
        value = payload.get("value")
        if isinstance(value, float) and value.is_integer():
            value = int(value)
        if not isinstance(value, int):
            return

        self._mode_code = value
        self.async_write_ha_state()

    def _write_mode(self, mode: int) -> Any:
        write_topic = f"{self._prefix}/W/{self._portal}/vebus/{self._instance}/Mode"
        payload = f'{{"value": {mode}}}'
        return mqtt.async_publish(self.hass, write_topic, payload=payload, qos=0, retain=False)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        if self._mode_code is None:
            return {}
        return {"vebus_mode_code": self._mode_code}


class VictronVeBusEmergencyShutdownSwitch(_BaseVeBusModeSwitch):
    """Emergency shutdown switch that forces VE.Bus Mode to 4 (Off).

    Requirements:
    - Turning ON publishes Mode=4.
    - If Mode is 0-3 the switch shows OFF automatically.
    - It must NOT be possible to switch from 4 to another value via this switch
      (turning OFF is a no-op).
    """

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        cfg_slug: str,
        topic_prefix: str,
        portal_id: str,
        vebus_instance: str,
    ) -> None:
        super().__init__(hass, entry, cfg_slug, topic_prefix, portal_id, vebus_instance)

        self._attr_name = "VE-Bus Emergency Shutdown"
        self._attr_unique_id = f"{entry.entry_id}_vebus_{vebus_instance}_emergency_shutdown"

        # Global naming rule: <cfg_slug>_ve_bus_<suffix>
        self._attr_suggested_object_id = f"{cfg_slug}_ve_bus_emergency_shutdown"

    @property
    def is_on(self) -> bool | None:
        if self._mode_code is None:
            return None
        return self._mode_code == 4

    @property
    def icon(self) -> str:
        return "mdi:transmission-tower"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        base = super().extra_state_attributes
        base.update(
            {
                "active": self._mode_code == 4 if self._mode_code is not None else None,
                "note": "Turning OFF is intentionally disabled; change VE.Bus Mode elsewhere.",
            }
        )
        return base

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._write_mode(4)

        # Optimistic update.
        self._mode_code = 4
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        # Explicitly disabled: this switch must not switch from 4 to other modes.
        self.async_write_ha_state()


class VictronVeBusGridActiveSwitch(_BaseVeBusModeSwitch):
    """Grid active switch that forces VE.Bus Mode to 3.

    Requirements:
    - Shows OFF when Mode is 1,2,4 (and generally anything other than 3).
    - Turning ON publishes Mode=3.
    - Turning OFF is a no-op (no switching back via this entity).
    """

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        cfg_slug: str,
        topic_prefix: str,
        portal_id: str,
        vebus_instance: str,
    ) -> None:
        super().__init__(hass, entry, cfg_slug, topic_prefix, portal_id, vebus_instance)

        self._attr_name = "Grid Active"
        self._attr_unique_id = f"{entry.entry_id}_vebus_{vebus_instance}_grid_active"

        # Global naming rule: <cfg_slug>_ve_bus_<suffix>
        self._attr_suggested_object_id = f"{cfg_slug}_ve_bus_grid_active"

    @property
    def is_on(self) -> bool | None:
        if self._mode_code is None:
            return None
        return self._mode_code == 3

    @property
    def icon(self) -> str:
        return "mdi:transmission-tower"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        base = super().extra_state_attributes
        base.update(
            {
                "active": self._mode_code == 3 if self._mode_code is not None else None,
                "note": "Turning OFF is intentionally disabled; change VE.Bus Mode elsewhere.",
            }
        )
        return base

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._write_mode(3)

        # Optimistic update.
        self._mode_code = 3
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        # Explicitly disabled: this switch must not switch from 3 to other modes.
        self.async_write_ha_state()
