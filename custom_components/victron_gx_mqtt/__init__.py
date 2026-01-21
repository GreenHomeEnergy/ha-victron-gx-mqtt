from __future__ import annotations

import json
import re
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.components import mqtt
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN, PLATFORMS, CONF_NAME, CONF_TOPIC_PREFIX, CONF_PORTAL_ID, MANUFACTURER, HUB_NAME, HUB_MODEL

SIGNAL_MQTT_MESSAGE = f"{DOMAIN}_mqtt_message"

# Topic pattern examples:
#   <prefix>/N/<portal_id>/vebus/276/State
#   <prefix>/N/<portal_id>/vebus/276/Mode
#   <prefix>/N/<portal_id>/vebus/276/CustomName
_TOPIC_RE = re.compile(r"^(?P<prefix>[^/]+)/N/(?P<portal>[^/]+)/(?P<rest>.+)$")


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


async def _async_migrate_entity_ids(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Best-effort migration to the **fixed** VE-Bus entity_id scheme.

    Project decision (repeatable naming): entity_ids are **not** prefixed with the
    config entry name (e.g. no "ve_base" / "ve_home"). Victron instance numbers
    (e.g. 276) must not appear in entity_ids either.

    Target patterns:
      sensor.ve_bus_state
      select.ve_bus_mode
      sensor.ve_bus_ac_out_l1_power

    Migration handles the common historical patterns:
      sensor.ve_bus_276_ac_out_l1_power -> sensor.ve_bus_ac_out_l1_power
      sensor.<oldcfg>_ve_bus_*          -> sensor.ve_bus_*
    """

    ent_reg = er.async_get(hass)
    entries = er.async_entries_for_config_entry(ent_reg, entry.entry_id)

    # 1) ve_bus_<instance>_<rest>
    p_inst = re.compile(r"^(?P<domain>sensor|select)\.ve_bus_(?P<inst>\d+)_(?P<rest>.+)$")
    # 2) <oldcfg>_ve_bus_<rest>
    p_cfg = re.compile(r"^(?P<domain>sensor|select)\.(?P<oldcfg>[a-z0-9_]+)_ve_bus_(?P<rest>.+)$")

    for e in entries:
        new_entity_id: str | None = None

        m = p_inst.match(e.entity_id)
        if m:
            new_entity_id = f"{m.group('domain')}.ve_bus_{m.group('rest')}"

        if new_entity_id is None:
            m = p_cfg.match(e.entity_id)
            if m:
                new_entity_id = f"{m.group('domain')}.ve_bus_{m.group('rest')}"

        if not new_entity_id or new_entity_id == e.entity_id:
            continue

        # Avoid collisions if something already exists.
        if ent_reg.async_get(new_entity_id) is not None:
            continue

        ent_reg.async_update_entity(e.entity_id, new_entity_id=new_entity_id)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN].setdefault(entry.entry_id, {})

    prefix: str = entry.data[CONF_TOPIC_PREFIX]
    portal: str = entry.data[CONF_PORTAL_ID]

    # Create a single HA device representing the Victron GX (Cerbo GX / Venus OS).
    # All VE-Bus entities are attached to this device (no separate VE-Bus device).
    dev_reg = dr.async_get(hass)
    hub_ident = f"{portal}_cerbo_gx"
    dev_reg.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, hub_ident)},
        manufacturer=MANUFACTURER,
        model=HUB_MODEL,
        name=HUB_NAME,
    )

    subscribe_topic = f"{prefix}/N/{portal}/#"

    # Best-effort entity_id migration (enforces ve_bus_* naming)
    await _async_migrate_entity_ids(hass, entry)

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
