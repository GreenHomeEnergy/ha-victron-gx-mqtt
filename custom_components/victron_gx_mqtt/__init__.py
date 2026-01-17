from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import dispatcher

from .const import DOMAIN, PLATFORMS, SIGNAL_VICTRON_MQTT_MESSAGE

# Wenn du bereits eine api.py / mqtt-client hast, importiere sie hier:
# from .api import VictronMqttClient


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN].setdefault(entry.entry_id, {})

    # 1) MQTT Client starten (falls vorhanden)
    # client = VictronMqttClient(hass, entry)
    # await client.async_start()
    # hass.data[DOMAIN][entry.entry_id]["client"] = client
    #
    # WICHTIG: Der Client sollte eingehende MQTT Messages wie folgt dispatchen:
    # dispatcher.async_dispatcher_send(hass, SIGNAL_VICTRON_MQTT_MESSAGE, topic, payload_dict)

    # 2) Platforms laden
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    # client = hass.data.get(DOMAIN, {}).get(entry.entry_id, {}).get("client")
    # if client is not None:
    #     await client.async_stop()

    hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    return unload_ok
