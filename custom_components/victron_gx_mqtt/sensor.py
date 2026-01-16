from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Callable

from homeassistant.components import mqtt
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
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

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, cfg: VictronBaseConfig) -> None:
        self.hass = hass
        self.entry = entry
        self.cfg = cfg

        self._unsub: Callable[[], None] | None = None
        self._native_value: int | None = None
        self._device_instance: str | None = None
        self._last_topic: str | None = None

        self._attr_unique_id = f"{entry.entry_id}_vebus_state"

        # This drives Victron branding (manufacturer-based)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=f"Victron GX ({cfg.name})",
            manufacturer="Victron Energy",
            model="GX (Cerbo/Venus OS)",
        )

    @property
    def native_value(self) -> int | None:
        return self._native_value

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        attrs: dict[str, Any] = {
            "portal_id": self.cfg.portal_id,
            "topic_prefix": self.cfg.topic_prefix,
        }
        if self._device_instance is not None:
            attrs["device_instance"] = self._device_instance
        if self._last_topic is not None:
            attrs["last_topic"] = self._last_topic
        return attrs

    async def async_added_to_hass(self) -> None:
        topic = f"{self.cfg.topic_prefix}/N/{self.cfg.portal_id}/vebus/+/State"
        self._unsub = await mqtt.async_subscribe(self.hass, topic, self._message_received, qos=0)

    async def async_will_remove_from_hass(self) -> None:
        if self._unsub is not None:
            self._unsub()
            self._unsub = None

    @callback
    def _message_received(self, msg: mqtt.ReceiveMessage) -> None:
        self._last_topic = msg.topic

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

        self._native_value = int(value)
        self.async_write_ha_state()
