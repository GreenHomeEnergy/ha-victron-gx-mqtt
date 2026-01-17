from __future__ import annotations

import json
import re
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
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


def _slug(text: str) -> str:
    """Slugify text for stable Home Assistant entity_id parts."""
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
    return s or "gx"


async def _async_migrate_entity_ids(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Rename previously created entity_ids to the new naming convention.

    Old pattern (example):
      sensor.ve_bus_276_ve_bus_state
      select.ve_bus_276_ve_bus_mode

    New pattern (example):
      sensor.ve_base_ve_bus_state
      select.ve_base_ve_bus_mode

    Notes:
    - We keep unique_id stable (it includes the instance).
    - We only rename entity_id (registry) when it matches the old pattern.
    """

    cfg_name: str = entry.data.get(CONF_NAME, "")
    slug_cfg = _slug(cfg_name)

    ent_reg = er.async_get(hass)
    entries = er.async_entries_for_config_entry(ent_reg, entry.entry_id)

    for e in entries:
        # Only touch our own entities.
        if e.platform != DOMAIN:
            continue

        # Mode
        if e.domain == "select" and e.entity_id.startswith("select.ve_bus_") and e.entity_id.endswith("_ve_bus_mode"):
            desired = f"select.{slug_cfg}_ve_bus_mode"
        # State
        elif e.domain == "sensor" and e.entity_id.startswith("sensor.ve_bus_") and e.entity_id.endswith("_ve_bus_state"):
            desired = f"sensor.{slug_cfg}_ve_bus_state"
        else:
            continue

        if e.entity_id == desired:
            continue

        # Avoid collisions if a user already renamed something.
        if ent_reg.async_get(desired) is not None:
            continue

        ent_reg.async_update_entity(e.entity_id, new_entity_id=desired)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN].setdefault(entry.entry_id, {})

    cfg_name: str = entry.data[CONF_NAME]
    prefix: str = entry.data[CONF_TOPIC_PREFIX]
    portal: str = entry.data[CONF_PORTAL_ID]

    subscribe_topic = f"{prefix}/N/{portal}/#"

    # Best-effort entity_id migration (renames old ve_bus_<instance>_* entity_ids).
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

    # ---------------------------------------------------------------------
    # Entity-ID migration / Bereinigung
    # ---------------------------------------------------------------------
    # Earlier pre-releases generated entity_id patterns like:
    #   sensor.ve_bus_276_ve_bus_state
    #   select.ve_bus_276_ve_bus_mode
    # Starting with v0.1.5-pre-6 we want:
    #   sensor.<cfg>_ve_bus_state
    #   select.<cfg>_ve_bus_mode
    # HA keeps entity_id in the entity registry, so we proactively rename
    # existing entries (idempotent, best-effort).
    await _async_migrate_entity_ids(hass, entry)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


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
    return s or "gx"


async def _async_migrate_entity_ids(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Rename legacy entity_ids to the new object_id convention.

    This is best-effort: if an entity does not exist or the target already
    exists, we leave it untouched.
    """

    cfg_name: str = entry.data.get(CONF_NAME, "")
    slug_cfg = _slug(cfg_name)

    desired: dict[str, str] = {
        "sensor": f"sensor.{slug_cfg}_ve_bus_state",
        "select": f"select.{slug_cfg}_ve_bus_mode",
    }

    ent_reg = er.async_get(hass)
    for entity in list(ent_reg.entities.values()):
        if entity.config_entry_id != entry.entry_id:
            continue
        if entity.domain not in desired:
            continue

        # Only rename the known legacy patterns (instance encoded in entity_id).
        # Example: sensor.ve_bus_276_ve_bus_state -> sensor.<cfg>_ve_bus_state
        if entity.entity_id in desired.values():
            continue

        if entity.domain == "sensor" and entity.entity_id.endswith("_ve_bus_state"):
            target = desired["sensor"]
        elif entity.domain == "select" and entity.entity_id.endswith("_ve_bus_mode"):
            target = desired["select"]
        else:
            continue

        # Avoid collisions.
        if ent_reg.async_get(target) is not None:
            continue

        ent_reg.async_update_entity(entity.entity_id, new_entity_id=target)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    data = hass.data.get(DOMAIN, {}).get(entry.entry_id, {})
    unsub = data.get("unsub")
    if unsub:
        unsub()

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    return unload_ok
