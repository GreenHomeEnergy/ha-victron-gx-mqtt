from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from homeassistant.components.select import SelectEntity
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
    VE_BUS_MODE_MAP,
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


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    cfg_name: str = entry.data[CONF_NAME]
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
                runtime.customname_by_instance[inst] = v.strip()
                ent = runtime.mode_entities.get(inst)
                if ent:
                    ent.set_custom_name(v.strip())
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
    _attr_has_entity_name = True
    _attr_options = VE_BUS_MODE_OPTIONS

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        cfg_name: str,
        topic_prefix: str,
        portal_id: str,
        vebus_instance: str,
        custom_name: str | None,
    ) -> None:
        self.hass = hass
        self._entry = entry
        self._cfg_name = cfg_name
        self._prefix = topic_prefix
        self._portal = portal_id
        self._instance = vebus_instance

        self._mode_code: int | None = None
        self._custom_name = custom_name

        dev_name = custom_name or f"VE.Bus {vebus_instance}"
        self._attr_device_info = DeviceInfo(
            # MUST match the State sensor device identifiers (same device in HA)
            identifiers={(DOMAIN, f"{portal_id}_vebus_{vebus_instance}")},
            name=dev_name,
            manufacturer="Victron Energy",
            model="VE.Bus",
        )

        self._attr_name = "VE-Bus Mode"
        self._attr_unique_id = f"{entry.entry_id}_vebus_{vebus_instance}_mode"

        slug_cfg = _slug(cfg_name)
        self._attr_object_id = f"ve_{slug_cfg}_vebus_{vebus_instance}_mode"

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
        self._attr_current_option = VE_BUS_MODE_MAP.get(value, f"Unknown ({value})")
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
        if option not in VE_BUS_MODE_MAP_INV:
            return

        value = VE_BUS_MODE_MAP_INV[option]
        write_topic = f"{self._prefix}/W/{self._portal}/vebus/{self._instance}/Mode"
        payload = f'{{"value": {value}}}'
        await mqtt.async_publish(self.hass, write_topic, payload=payload, qos=0, retain=False)

        # Optimistisch setzen (inkl. code für zweisprachige Attribute)
        self._attr_current_option = option
        self._mode_code = value
        self.async_write_ha_state()


def _slug(text: str) -> str:
    text = (text or "").strip().lower()
    out = []
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
    return s or "gx"
