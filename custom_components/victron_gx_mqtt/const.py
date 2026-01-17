from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from homeassistant.const import Platform

DOMAIN: Final = "victron_gx_mqtt"

CONF_NAME: Final = "name"
CONF_TOPIC_PREFIX: Final = "topic_prefix"
CONF_PORTAL_ID: Final = "portal_id"

PLATFORMS: Final[list[Platform]] = [Platform.SENSOR, Platform.SELECT]

# VE.Bus State mapping (Ausbau möglich; hier die üblichen Zustände)
VE_BUS_STATE_MAP: Final[dict[int, str]] = {
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
    10: "Power Assist",
}

# VE.Bus Mode mapping (writeable)
# Vorgabe: 1=Charger Only; 2=Inverter Only; 3=On; 4=Off
VE_BUS_MODE_MAP: Final[dict[int, str]] = {
    1: "Charger Only",
    2: "Inverter Only",
    3: "On",
    4: "Off",
}

VE_BUS_MODE_OPTIONS: Final[list[str]] = [
    VE_BUS_MODE_MAP[1],
    VE_BUS_MODE_MAP[2],
    VE_BUS_MODE_MAP[3],
    VE_BUS_MODE_MAP[4],
]

VE_BUS_MODE_MAP_INV: Final[dict[str, int]] = {v: k for k, v in VE_BUS_MODE_MAP.items()}


@dataclass(frozen=True)
class VictronConfig:
    name: str
    topic_prefix: str
    portal_id: str
