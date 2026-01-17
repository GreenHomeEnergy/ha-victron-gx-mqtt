from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from homeassistant.const import Platform

DOMAIN: Final = "victron_gx_mqtt"

# ---- Config keys (ConfigFlow / entry.data) ----
CONF_NAME: Final = "name"
CONF_TOPIC_PREFIX: Final = "topic_prefix"
CONF_PORTAL_ID: Final = "portal_id"

# ---- Dispatcher signals ----
# IMPORTANT:
# Dein MQTT-Listener/Client muss bei jeder eingehenden Nachricht folgendes dispatchen:
# async_dispatcher_send(hass, SIGNAL_VICTRON_MQTT_MESSAGE, topic, payload_dict)
SIGNAL_VICTRON_MQTT_MESSAGE: Final = f"{DOMAIN}_mqtt_message"

# ---- Platforms ----
PLATFORMS: Final[list[Platform]] = [
    Platform.SENSOR,
    Platform.SELECT,  # v0.1.3-pre-4: VE.Bus Mode als SelectEntity
]

# ---- VE.Bus mappings ----
# Victron VE.Bus "Mode" ist typischerweise:
# 0 = Off
# 1 = Charger Only
# 2 = Inverter Only
# 3 = On
# (Falls dein System weitere Werte liefert, werden sie als "Unknown (<n>)" angezeigt.)
VE_BUS_MODE_MAP: Final[dict[int, str]] = {
    0: "Off",
    1: "Charger Only",
    2: "Inverter Only",
    3: "On",
}

VE_BUS_MODE_OPTIONS: Final[list[str]] = [
    VE_BUS_MODE_MAP[0],
    VE_BUS_MODE_MAP[1],
    VE_BUS_MODE_MAP[2],
    VE_BUS_MODE_MAP[3],
]

VE_BUS_MODE_MAP_INV: Final[dict[str, int]] = {v: k for k, v in VE_BUS_MODE_MAP.items()}


@dataclass(frozen=True)
class VictronConfig:
    name: str
    topic_prefix: str
    portal_id: str
