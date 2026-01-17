from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Callable

from homeassistant.components import mqtt
from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    CONF_NAME,
    CONF_TOPIC_PREFIX,
    CONF_PORTAL_ID,
    CONF_SELECTED_SERVICES,
    SERVICE_VEBUS,
)

_VEBUS_STATE_TOPIC_RE = re.compile(r"^(.+)/N/([^/]+)/vebus/(\d+)/State$")
_VEBUS_CUSTOMNAME_TOPIC_RE = re.compile(r"^(.+)/N/([^/]+)/vebus/(\d+)/CustomName$")

# VE.Bus / System state mapping used in Victron UI (common mapping)
# Unknown codes will be shown as "Unknown (<code>)"
VEBUS_STATE_TEXT: dict[int, str] = {
    0: "Off",
    1: "AES mode",
    2: "Fault",
    3: "Bulk",
    4: "Absorption",
    5: "Float",
    6: "Storage",
    7: "Equalize",
    8: "Passthru",
    9: "Inverting",
    10: "Assisting",
    11: "Power Supply",
    245: "Wakeup",
    246: "Rep. Absorption",
    247: "Equalize",
    248: "Battery Safe",
    249: "Test",
    250: "Blocked",
    251: "Test",
    252: "Ext. control",
    256: "Discharging",
    257: "Sustain",
    258: "Recharge",
    259: "Scheduled",
}


@dataclass(frozen=True)
class VictronBaseConfig:
    name: str
    topic_prefix: str
    portal_id: str


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    cfg = VictronBaseConfig(
        name=entry.data[CONF_NAME],
        topic_prefix=entry.data[CONF_TOPIC_PREFIX].strip().strip("/"),
        portal_id=entry.data[CONF_PORTAL_ID].strip(),
    )

    selected = entry.options.get(CONF_SELECTED_SERVICES, [])
    entities: list[SensorEntity] = []

    if SERVICE_VEBUS in selected:
        entities.append(VeBusStateSensor(hass, entry, cfg))

    if entities:
        async_add_entities(entities)


class VeBusStateSensor(SensorEntity):
    """VE.Bus State from Victron dbus-flashmq MQTT notifications."""

    _attr_has_entity_name = True
    _attr_name = "VE.Bus State"
    _attr_icon = "mdi:transmission-tower"
    _attr_device_class = SensorDeviceClass.ENUM

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, cfg: VictronBaseConfig) -> None:
        self.hass = hass
        self.entry = entry
        self.cfg = cfg

        self._unsub_state: Callable[[], None] | None = None
        self._unsub_customname: Callable[[], None] | None = None

        self._state_code: int | None = None
        self._native_value: str | None = None

        self._device_instance: str | None = None
        self._custom_name: str | None = None

        self._last_state_topic: str | None = None
        self._last_customname_topic: str | None = None

        self._attr_unique_id = f"{entry.entry_id}_vebus_state"

        # One HA device per configured GX entry; we will rename it once CustomName arrives
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=f"Victron GX ({cfg.name})",
            manufacturer="Victron Energy",
            model="GX (Cerbo/Venus OS)",
        )

        # Advertise known enum options (helps UI)
        self._attr_options = sorted(set(VEBUS_STATE_TEXT.values()))

    @property
    def native_value(self) -> str | None:
        return self._native_value

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        attrs: dict[str, Any] = {
            "portal_id": self.cfg.portal_id,
            "topic_prefix": self.cfg.topic_prefix,
        }
        if self._device_instance is not None:
            attrs["device_instance"] = self._device_instance
        if self._state_code is not None:
            attrs["state_code"] = self._state_code
        if self._custom_name is not None:
            attrs["custom_name"] = self._custom_name
        if self._last_state_topic is not None:
            attrs["last_state_topic"] = self._last_state_topic
        if self._last_customname_topic is not None:
            attrs["last_customname_topic"] = self._last_customname_topic
        return attrs

    async def async_added_to_hass(self) -> None:
        base = self.cfg.topic_prefix
        portal = self.cfg.portal_id

        state_topic = f"{base}/N/{portal}/vebus/+/State"
        customname_topic = f"{base}/N/{portal}/vebus/+/CustomName"

        self._unsub_state = await mqtt.async_subscribe(self.hass, state_topic, self._on_state_msg, qos=0)
        self._unsub_customname = await mqtt.async_subscribe(
            self.hass, customname_topic, self._on_customname_msg, qos=0
        )

    async def async_will_remove_from_hass(self) -> None:
        if self._unsub_state is not None:
            self._unsub_state()
            self._unsub_state = None
        if self._unsub_customname is not None:
            self._unsub_customname()
            self._unsub_customname = None

    @callback
    def _on_state_msg(self, msg: mqtt.ReceiveMessage) -> None:
        self._last_state_topic = msg.topic

        try:
            payload = json.loads(msg.payload)
        except Exception:
            return

        if not isinstance(payload, dict) or "value" not in payload:
            return

        value = payload.get("value")
        if not isinstance(value, (int, float)):
            return

        m = _VEBUS_STATE_TOPIC_RE.match(msg.topic)
        if m:
            self._device_instance = m.group(3)

        self._state_code = int(value)
        self._native_value = VEBUS_STATE_TEXT.get(self._state_code, f"Unknown ({self._state_code})")
        self.async_write_ha_state()

    @callback
    def _on_customname_msg(self, msg: mqtt.ReceiveMessage) -> None:
        self._last_customname_topic = msg.topic

        try:
            payload = json.loads(msg.payload)
        except Exception:
            return

        if not isinstance(payload, dict) or "value" not in payload:
            return

        name_val = payload.get("value")
        if not isinstance(name_val, str) or not name_val.strip():
            return

        m = _VEBUS_CUSTOMNAME_TOPIC_RE.match(msg.topic)
        if not m:
            return

        instance = m.group(3)

        # If we already have an instance from State, only accept matching CustomName
        if self._device_instance is not None and instance != self._device_instance:
            return

        self._device_instance = instance
        self._custom_name = name_val.strip()

        # Update device name in registry to CustomName
        device_reg = dr.async_get(self.hass)
        device = device_reg.async_get_device(identifiers={(DOMAIN, self.entry.entry_id)})
        if device is not None:
            device_reg.async_update_device(
                device.id,
                name=self._custom_name,
                manufacturer="Victron Energy",
            )

        self.async_write_ha_state()
