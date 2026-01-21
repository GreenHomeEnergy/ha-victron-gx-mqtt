from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
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
    VE_BUS_MODE_MAP_DE,
    VE_BUS_MODE_MAP_EN,
    VE_BUS_MODE_MAP_INV,
    VE_BUS_MODE_OPTIONS,
)

_VEBUS_MODE_RE = re.compile(
    r"^(?P<prefix>[^/]+)/N/(?P<portal>[^/]+)/vebus/(?P<instance>\d+)/Mode$"
)
_VEBUS_CUSTOMNAME_RE = re.compile(
    r"^(?P<prefix>[^/]+)/N/(?P<portal>[^/]+)/vebus/(?P<instance>\d+)/CustomName$"
)


@dataclass
class _Runtime:
    mode_entities: dict[str, "VictronVeBusModeSelect"]
    customname_by_instance: dict[str, str]


def _device_ident(portal_id: str, vebus_instance: str) -> str:
    return f"{portal_id}_vebus_{vebus_instance}"


def _update_device_name(hass: HomeAssistant, portal_id: str, vebus_instance: str, name: str) -> None:
    """CustomName is intentionally not used for the HA device name (fixed naming)."""
    return



def _label_en(code: int) -> str:
    """Return the canonical (English) label for a given VE.Bus mode code."""
    return VE_BUS_MODE_MAP_EN.get(code, f"Unknown ({code})")


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    cfg_name: str = (entry.title or entry.data.get(CONF_NAME) or 'home')
    cfg_slug: str = _slug(cfg_name)
    prefix: str = entry.data[CONF_TOPIC_PREFIX]
    portal: str = entry.data[CONF_PORTAL_ID]

    runtime: _Runtime = hass.data[DOMAIN][entry.entry_id].setdefault(
        "select_runtime",
        _Runtime(mode_entities={}, customname_by_instance={}),
    )

    signal: str = hass.data[DOMAIN][entry.entry_id]["signal"]

    @callback
    def _on_message(topic: str, payload: dict[str, Any]) -> None:
        # CustomName
        m_cn = _VEBUS_CUSTOMNAME_RE.match(topic)
        if m_cn and m_cn.group("prefix") == prefix and m_cn.group("portal") == portal:
            inst = m_cn.group("instance")
            v = payload.get("value")
            if isinstance(v, str) and v.strip():
                custom_name = v.strip()
                runtime.customname_by_instance[inst] = custom_name
                ent = runtime.mode_entities.get(inst)
                if ent:
                    ent.set_custom_name(custom_name)
            return

        # Mode
        m = _VEBUS_MODE_RE.match(topic)
        if not m:
            return
        if m.group("prefix") != prefix or m.group("portal") != portal:
            return

        inst = m.group("instance")
        ent = runtime.mode_entities.get(inst)
        if ent is None:
            ent = VictronVeBusModeSelect(
                hass=hass,
                entry=entry,
                cfg_name=cfg_name,
                cfg_slug=cfg_slug,
                topic_prefix=prefix,
                portal_id=portal,
                vebus_instance=inst,
                custom_name=runtime.customname_by_instance.get(inst),
            )
            runtime.mode_entities[inst] = ent
            async_add_entities([ent])

        ent.handle_mode(payload)

    async_dispatcher_connect(hass, signal, _on_message)


class VictronVeBusModeSelect(SelectEntity):
    """VE.Bus Mode select."""

    # Use explicit entity names (not "device name + entity name") to keep naming
    # stable and predictable across installations.
    _attr_has_entity_name = False
    _attr_options = VE_BUS_MODE_OPTIONS

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        cfg_name: str,
        cfg_slug: str,
        topic_prefix: str,
        portal_id: str,
        vebus_instance: str,
        custom_name: str | None,
    ) -> None:
        self.hass = hass
        self._entry = entry
        self._cfg_name = cfg_name
        self._cfg_slug = cfg_slug
        self._prefix = topic_prefix
        self._portal = portal_id
        self._instance = vebus_instance
        self._custom_name = custom_name

        self._mode_code: int | None = None

        # Attach to the single Victron GX device (Cerbo GX).
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{portal_id}_cerbo_gx")},
            name=HUB_NAME,
            manufacturer=MANUFACTURER,
            model=HUB_MODEL,
        )

        # Entity name (UI). Keep single-language; DE/EN mappings are exposed via attributes.
        self._attr_name = "VE-Bus Mode"
        self._attr_unique_id = f"{entry.entry_id}_vebus_{vebus_instance}_mode"

        # Suggested entity_id (object_id). Includes config slug, but no instance number.
        self._attr_suggested_object_id = f"{cfg_slug}_ve_bus_mode"

        self._attr_current_option = None

    def set_custom_name(self, custom_name: str) -> None:
        self._custom_name = custom_name
        self.async_write_ha_state()

    @callback
    def handle_mode(self, payload: dict[str, Any]) -> None:
        value = payload.get("value")
        if isinstance(value, float) and value.is_integer():
            value = int(value)
        if not isinstance(value, int):
            return

        self._mode_code = value
        self._attr_current_option = _label_en(value)
        self.async_write_ha_state()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        if self._mode_code is None:
            return {}
        code = self._mode_code
        return {
            "code": code,
            "mode_en": VE_BUS_MODE_MAP_EN.get(code, f"Unknown ({code})"),
            "mode_de": VE_BUS_MODE_MAP_DE.get(code, f"Unbekannt ({code})"),
        }

    async def async_select_option(self, option: str) -> None:
        value = VE_BUS_MODE_MAP_INV.get(option)
        if value is None:
            return

        write_topic = f"{self._prefix}/W/{self._portal}/vebus/{self._instance}/Mode"
        payload = f'{{"value": {value}}}'
        await mqtt.async_publish(self.hass, write_topic, payload=payload, qos=0, retain=False)

        # Optimistic update.
        self._mode_code = value
        self._attr_current_option = _label_en(value)
        self.async_write_ha_state()


def _slug(text: str) -> str:
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
