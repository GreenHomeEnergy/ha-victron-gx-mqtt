from __future__ import annotations

import json
import re
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.components import mqtt

from .const import DOMAIN, PLATFORMS, CONF_NAME, CONF_TOPIC_PREFIX, CONF_PORTAL_ID

SIGNAL_MQTT_MESSAGE = f"{DOMAIN}_mqtt_message"

# Topic pattern examples:
#   <prefix>/N/<portal_id>/vebus/276/State
#   <prefix>/N/<portal_id>/vebus/276/Mode
#   <prefix>/N/<portal_id>/vebus/276/CustomName
_TOPIC_RE = re.compile(r"^(?P<prefix>[^/]+)/N/(?P<portal>[^/]+)/(?P<rest>.+)$")


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN].setdefault(entry.entry_id, {})

    cfg_name: str = entry.data[CONF_NAME]
    prefix: str = entry.data[CONF_TOPIC_PREFIX]
    portal: str = entry.data[CONF_PORTAL_ID]

    subscribe_topic = f"{prefix}/N/{portal}/#"

    @callback
    def _message_received(msg: mqtt.ReceiveMessage) -> None:
        topic = msg.topic
        payload_raw = msg.payload

        m = _TOPIC_RE.match(topic)
        if not m:
            return
        if m.group("prefix") != prefix or m.group("portal") != portal:
            return

        payload_dict: dict[str, Any] | None = None
        try:
            if isinstance(payload_raw, (bytes, bytearray)):
                payload_raw = payload_raw.decode("utf-8", errors="ignore")
            if isinstance(payload_raw, str) and payload_raw.strip():
                payload_dict = json.loads(payload_raw)
        except Exception:
            payload_dict = None

        if not isinstance(payload_dict, dict):
            return

        async_dispatcher_send(hass, SIGNAL_MQTT_MESSAGE, topic, payload_dict)

    unsub = await mqtt.async_subscribe(hass, subscribe_topic, _message_received, qos=0)
    hass.data[DOMAIN][entry.entry_id]["unsub"] = unsub
    hass.data[DOMAIN][entry.entry_id]["signal"] = SIGNAL_MQTT_MESSAGE

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    data = hass.data.get(DOMAIN, {}).get(entry.entry_id, {})
    unsub = data.get("unsub")
    if unsub:
        unsub()

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    return unload_ok
