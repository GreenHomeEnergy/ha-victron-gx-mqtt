from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from homeassistant.const import Platform

DOMAIN: Final = "victron_gx_mqtt"

CONF_NAME: Final = "name"
CONF_TOPIC_PREFIX: Final = "topic_prefix"
CONF_PORTAL_ID: Final = "portal_id"

PLATFORMS: Final[list[Platform]] = [Platform.SENSOR, Platform.SELECT]

# ----------------------------
# VE.Bus State mapping (Sensor)
# ----------------------------

VE_BUS_STATE_MAP_EN: Final[dict[int, str]] = {
    0: "Off",
    1: "Low Power",
    2: "Fault",
    3: "Bulk",
    4: "Absorption",
    5: "Float",
    6: "Storage",
    7: "Equalize",
    8: "Passthru",
    9: "Inverting",
    10: "Power assist",
    11: "Power supply",
    244: "Sustain",
    252: "External control",
}

VE_BUS_STATE_MAP_DE: Final[dict[int, str]] = {
    0: "Aus",
    1: "Geringe Leistung",
    2: "Fehler",
    3: "Bulk",
    4: "Absorption",
    5: "Erhaltung",
    6: "Storage",
    7: "Ausgleichsladung",
    8: "Durchleitung",
    9: "Wechselrichterbetrieb",
    10: "Power Assist",
    11: "Netzteilbetrieb",
    244: "Sustain",
    252: "Externe Steuerung",
}

# Backward-compatible default (English) used as primary state value
VE_BUS_STATE_MAP: Final[dict[int, str]] = VE_BUS_STATE_MAP_EN

# ----------------------------
# VE.Bus Mode mapping (Select)
# ----------------------------
# Vorgabe: 1=Charger Only; 2=Inverter Only; 3=On; 4=Off

VE_BUS_MODE_MAP_EN: Final[dict[int, str]] = {
    1: "Charger Only",
    2: "Inverter Only",
    3: "On",
    4: "Off",
}

VE_BUS_MODE_MAP_DE: Final[dict[int, str]] = {
    1: "Nur Laden",
    2: "Nur Wechselrichter",
    3: "Ein",
    4: "Aus",
}

# Primary (automation-safe) options remain English
VE_BUS_MODE_MAP: Final[dict[int, str]] = VE_BUS_MODE_MAP_EN

VE_BUS_MODE_OPTIONS: Final[list[str]] = [
    VE_BUS_MODE_MAP_EN[1],
    VE_BUS_MODE_MAP_EN[2],
    VE_BUS_MODE_MAP_EN[3],
    VE_BUS_MODE_MAP_EN[4],
]

VE_BUS_MODE_MAP_INV: Final[dict[str, int]] = {v: k for k, v in VE_BUS_MODE_MAP_EN.items()}


@dataclass(frozen=True)
class VictronConfig:
    name: str
    topic_prefix: str
    portal_id: str
