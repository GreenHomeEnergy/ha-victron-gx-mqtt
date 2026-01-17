from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from homeassistant.const import Platform

DOMAIN: Final = "victron_gx_mqtt"

CONF_NAME: Final = "name"
CONF_TOPIC_PREFIX: Final = "topic_prefix"
CONF_PORTAL_ID: Final = "portal_id"

PLATFORMS: Final[list[Platform]] = [Platform.SENSOR, Platform.SELECT]

# -----------------------------------------------------------------------------
# VE.Bus State (Sensor)
# -----------------------------------------------------------------------------
# 0=Off;1=Low Power;2=Fault;3=Bulk;4=Absorption;5=Float;6=Storage;7=Equalize;
# 8=Passthru;9=Inverting;10=Power assist;11=Power supply;244=Sustain;
# 252=External control

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

# Sensor primary value remains English (stable for automations). German is exposed via attributes.
VE_BUS_STATE_MAP: Final[dict[int, str]] = VE_BUS_STATE_MAP_EN

# -----------------------------------------------------------------------------
# VE.Bus Mode (Select)
# -----------------------------------------------------------------------------
# 1=Charger Only;2=Inverter Only;3=On;4=Off

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

# Select primary option value remains English (stable for automations). German is shown in UI via bilingual labels.
VE_BUS_MODE_MAP: Final[dict[int, str]] = VE_BUS_MODE_MAP_EN

# UI options: bilingual, to satisfy "everything visible is bilingual" starting with v0.1.5-pre-6.
VE_BUS_MODE_OPTIONS_BILINGUAL: Final[list[str]] = [
    f"{VE_BUS_MODE_MAP_DE[1]} / {VE_BUS_MODE_MAP_EN[1]}",
    f"{VE_BUS_MODE_MAP_DE[2]} / {VE_BUS_MODE_MAP_EN[2]}",
    f"{VE_BUS_MODE_MAP_DE[3]} / {VE_BUS_MODE_MAP_EN[3]}",
    f"{VE_BUS_MODE_MAP_DE[4]} / {VE_BUS_MODE_MAP_EN[4]}",
]

# For service calls / automations we keep accepting the EN labels as well.
VE_BUS_MODE_MAP_INV_EN: Final[dict[str, int]] = {v: k for k, v in VE_BUS_MODE_MAP_EN.items()}

# Bilingual option -> code mapping
VE_BUS_MODE_MAP_INV_BILINGUAL: Final[dict[str, int]] = {
    VE_BUS_MODE_OPTIONS_BILINGUAL[0]: 1,
    VE_BUS_MODE_OPTIONS_BILINGUAL[1]: 2,
    VE_BUS_MODE_OPTIONS_BILINGUAL[2]: 3,
    VE_BUS_MODE_OPTIONS_BILINGUAL[3]: 4,
}


@dataclass(frozen=True)
class VictronConfig:
    name: str
    topic_prefix: str
    portal_id: str
