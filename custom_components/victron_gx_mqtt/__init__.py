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
    """Best-effort migration to the **global** entity_id scheme.

    Global rule (verbindlich):
        <entity_domain>.<cfg_slug>_ve_bus_<object_id_suffix>

    Notes:
    - Home Assistant persists entity_ids in the Entity Registry; changing
      `_attr_suggested_object_id` alone does not rename existing entities.
    - This migration is intentionally conservative: it only renames when the
      target entity_id is free (no collision).
    """

    ent_reg = er.async_get(hass)
    entries = er.async_entries_for_config_entry(ent_reg, entry.entry_id)

    cfg_name: str = (entry.title or entry.data.get(CONF_NAME) or "home")
    cfg_slug: str = _slug(cfg_name)

    # Historical patterns we may encounter:
    # 1) <domain>.ve_bus_<rest>
    p_no_cfg = re.compile(r"^(?P<domain>sensor|select|switch|number)\.ve_bus_(?P<rest>.+)$")
    # 2) <domain>.ve_bus_<instance>_<rest>
    p_inst = re.compile(r"^(?P<domain>sensor|select|switch|number)\.ve_bus_(?P<inst>\d+)_(?P<rest>.+)$")
    # 3) <domain>.<oldcfg>_ve_bus_<rest>
    p_old_cfg = re.compile(
        r"^(?P<domain>sensor|select|switch|number)\.(?P<oldcfg>[a-z0-9_]+)_ve_bus_(?P<rest>.+)$"
    )
    # 4) Early switch names without ve_bus prefix at all
    p_switch_short = re.compile(r"^switch\.(?P<rest>grid_active)$")
    # 5) Early switch names with ve_bus but missing cfg
    p_switch_ve_bus = re.compile(r"^switch\.(?P<rest>ve_bus_(?:grid_active|emergency_shutdown))$")

    for e in entries:
        new_entity_id: str | None = None

        m = p_inst.match(e.entity_id)
        if m:
            new_entity_id = f"{m.group('domain')}.{cfg_slug}_ve_bus_{m.group('rest')}"

        if new_entity_id is None:
            m = p_old_cfg.match(e.entity_id)
            if m:
                new_entity_id = f"{m.group('domain')}.{cfg_slug}_ve_bus_{m.group('rest')}"

        if new_entity_id is None:
            m = p_no_cfg.match(e.entity_id)
            if m:
                new_entity_id = f"{m.group('domain')}.{cfg_slug}_ve_bus_{m.group('rest')}"

        if new_entity_id is None:
            m = p_switch_short.match(e.entity_id)
            if m:
                new_entity_id = f"switch.{cfg_slug}_ve_bus_{m.group('rest')}"

        if new_entity_id is None:
            m = p_switch_ve_bus.match(e.entity_id)
            if m:
                rest = m.group("rest")[len("ve_bus_") :]
                new_entity_id = f"switch.{cfg_slug}_ve_bus_{rest}"

        if not new_entity_id or new_entity_id == e.entity_id:
            continue

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


