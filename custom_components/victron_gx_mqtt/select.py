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
    SIGNAL_VICTRON_MQTT_MESSAGE,
    VE_BUS_MODE_MAP,
    VE_BUS_MODE_MAP_INV,
    VE_BUS_MODE_OPTIONS,
)

# Topic examples:
#   venus-home/N/<portal_id>/vebus/276/Mode
#   venus-home/W/<portal_id>/vebus/276/Mode  (write)
#
# Payload example:
#   {"value": 3}

_VEBUS_MODE_TOPIC_RE = re.compile(
    r"^(?P<prefix>[^/]+)/N/(?P<portal>[^/]+)/vebus/(?P<instance>\d+)/Mode$"
)

_VEBUS_CUSTOMNAME_TOPIC_RE = re.compile(
    r"^(?P<prefix>[^/]+)/N/(?P<portal>[^/]+)/vebus/(?P<instance>\d+)/CustomName$"
)


@dataclass
class _Runtime:
    """Entry runtime cache (per ConfigEntry)."""

    entities_by_instance: dict[str, "VictronVeBusModeSelect"]
    customname_by_instance: dict[str, str]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up VE.Bus Select entities via MQTT discovery."""
    data = entry.data
    cfg_name: str = data.get(CONF_NAME, "Victron")
    topic_prefix: str = data[CONF_TOPIC_PREFIX]
    portal_id: str = data[CONF_PORTAL_ID]

    runtime: _Runtime = hass.data.setdefault(DOMAIN, {}).setdefault(entry.entry_id, {}).setdefault(
        "select_runtime",
        _Runtime(entities_by_instance={}, customname_by_instance={}),
    )

    @callback
    def _handle_message(topic: str, payload: dict[str, Any]) -> None:
        # 1) CustomName merken (damit Device/Entity Names hübsch werden)
        m_name = _VEBUS_CUSTOMNAME_TOPIC_RE.match(topic)
        if m_name and m_name.group("prefix") == topic_prefix and m_name.group("portal") == portal_id:
            inst = m_name.group("instance")
            value = payload.get("value")
            if isinstance(value, str) and value.strip():
                runtime.customname_by_instance[inst] = value.strip()
                # Falls Entity bereits existiert: sofort umbenennen
                ent = runtime.entities_by_instance.get(inst)
                if ent is not None:
                    ent.set_custom_name(value.strip())
            return

        # 2) Mode discovery
        m_mode = _VEBUS_MODE_TOPIC_RE.match(topic)
        if not m_mode:
            return
        if m_mode.group("prefix") != topic_prefix or m_mode.group("portal") != portal_id:
            return

        inst = m_mode.group("instance")

        ent = runtime.entities_by_instance.get(inst)
        if ent is None:
            custom = runtime.customname_by_instance.get(inst)
            ent = VictronVeBusModeSelect(
                hass=hass,
                entry=entry,
                cfg_name=cfg_name,
                topic_prefix=topic_prefix,
                portal_id=portal_id,
                vebus_instance=inst,
                custom_name=custom,
            )
            runtime.entities_by_instance[inst] = ent
            async_add_entities([ent])

        # Payload anwenden
        ent.handle_mode_payload(payload)

    # Registrierung am Dispatcher
    # -> Dein MQTT-Client muss dieses Signal feuern.
    async_dispatcher_connect(hass, SIGNAL_VICTRON_MQTT_MESSAGE, _handle_message)


class VictronVeBusModeSelect(SelectEntity):
    """VE.Bus Mode (writeable) as a Home Assistant SelectEntity."""

    _attr_has_entity_name = True
    _attr_options = VE_BUS_MODE_OPTIONS
    _attr_translation_key = "vebus_mode"

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
        self.entry = entry
        self._cfg_name = cfg_name
        self._topic_prefix = topic_prefix
        self._portal_id = portal_id
        self._instance = vebus_instance
        self._custom_name = custom_name

        # Device: 1 Device je VE.Bus instance (identifiers stabil)
        dev_name = custom_name or f"VE.Bus {vebus_instance}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.entry_id}_vebus_{vebus_instance}")},
            name=dev_name,
            manufacturer="Victron Energy",
            model="VE.Bus",
        )

        # Entity naming
        # Anzeige: "<CustomName> VE-Bus Mode" / falls kein CustomName -> "VE-Bus Mode"
        self._attr_name = "VE-Bus Mode"

        # Unique ID ist stabil; Entity-ID kann der User später ändern.
        # Wichtig: Entity-ID-Autogen basiert auf object_id (siehe _attr_object_id).
        self._attr_unique_id = f"{entry.entry_id}_vebus_{vebus_instance}_mode"

        # Damit deine Wunsch-Entity-ID entsteht:
        # sensor.ve_home_... war vorher Sensor.
        # Hier ist es select.ve_zuhause_ve_bus_mode (Select-Domain).
        #
        # Wenn du wirklich *sensor.ve_home_...* willst, wäre das technisch falsch,
        # weil Mode eben ein Select ist. Ich setze sauber:
        # select.ve_<cfg_name>_ve_bus_mode
        slug_cfg = _slug(cfg_name)
        self._attr_object_id = f"ve_{slug_cfg}_ve_bus_mode"

        self._mode_value: int | None = None
        self._attr_current_option: str | None = None

    def set_custom_name(self, custom_name: str) -> None:
        """Update device display name when CustomName arrives."""
        self._custom_name = custom_name
        # Device name wird über device_registry gehandhabt; Entity bleibt "VE-Bus Mode".
        # Das UI zeigt es dann als "<DeviceName> VE-Bus Mode".
        self.async_write_ha_state()

    @callback
    def handle_mode_payload(self, payload: dict[str, Any]) -> None:
        value = payload.get("value")
        if not isinstance(value, int):
            # Victron sendet gelegentlich floats -> int versuchen
            if isinstance(value, float) and value.is_integer():
                value = int(value)
            else:
                return

        self._mode_value = value
        self._attr_current_option = VE_BUS_MODE_MAP.get(value, f"Unknown ({value})")
        self.async_write_ha_state()

    async def async_select_option(self, option: str) -> None:
        """Handle user selecting a new mode."""
        if option not in VE_BUS_MODE_MAP_INV:
            return

        value = VE_BUS_MODE_MAP_INV[option]

        # Publish to write topic:
        # <prefix>/W/<portal_id>/vebus/<instance>/Mode
        write_topic = f"{self._topic_prefix}/W/{self._portal_id}/vebus/{self._instance}/Mode"
        await mqtt.async_publish(self.hass, write_topic, payload=_json_payload(value), qos=0, retain=False)

        # Optimistisch UI aktualisieren (HA bekommt in der Regel kurz danach N/.../Mode zurück)
        self._mode_value = value
        self._attr_current_option = option
        self.async_write_ha_state()


def _json_payload(value: int) -> str:
    return f'{{"value": {value}}}'


def _slug(text: str) -> str:
    text = (text or "").strip().lower()
    # minimaler slug: nur a-z0-9 und _
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
