from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from homeassistant.const import (
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfFrequency,
    UnitOfPower,
)

from .const import (
    DOMAIN,
    CONF_NAME,
    CONF_TOPIC_PREFIX,
    CONF_PORTAL_ID,
    MANUFACTURER,
    HUB_NAME,
    HUB_MODEL,
    VE_BUS_STATE_MAP,
    VE_BUS_STATE_MAP_DE,
    VE_BUS_STATE_MAP_EN,
)

_VEBUS_STATE_RE = re.compile(
    r"^(?P<prefix>[^/]+)/N/(?P<portal>[^/]+)/vebus/(?P<instance>\d+)/State$"
)
_VEBUS_CUSTOMNAME_RE = re.compile(
    r"^(?P<prefix>[^/]+)/N/(?P<portal>[^/]+)/vebus/(?P<instance>\d+)/CustomName$"
)

_VEBUS_AC_OUT_RE = re.compile(
    r"^(?P<prefix>[^/]+)/N/(?P<portal>[^/]+)/vebus/(?P<instance>\d+)/Ac/Out(?:/(?P<phase>L[123]))?/(?P<metric>[PIVF])$"
)


@dataclass(frozen=True)
class _SensorDef:
    key: str
    entity_name: str
    object_id_suffix: str
    device_class: SensorDeviceClass
    unit: str
    state_class: SensorStateClass


def _ac_out_sensor_defs() -> dict[str, "_SensorDef"]:
    """Definitions for VE.Bus AC Out sensors (topic -> entity metadata)."""

    defs: dict[str, _SensorDef] = {
        # Total
        "ac_out_power_total": _SensorDef(
            key="ac_out_power_total",
            entity_name="AC Out Power Total",
            object_id_suffix="ac_out_power_total",
            device_class=SensorDeviceClass.POWER,
            unit=UnitOfPower.WATT,
            state_class=SensorStateClass.MEASUREMENT,
        ),
    }

    metric_map: dict[str, tuple[str, str, SensorDeviceClass, str]] = {
        "P": ("power", "Power", SensorDeviceClass.POWER, UnitOfPower.WATT),
        "I": ("current", "Current", SensorDeviceClass.CURRENT, UnitOfElectricCurrent.AMPERE),
        "V": ("voltage", "Voltage", SensorDeviceClass.VOLTAGE, UnitOfElectricPotential.VOLT),
        "F": ("frequency", "Frequency", SensorDeviceClass.FREQUENCY, UnitOfFrequency.HERTZ),
    }

    for phase in ("L1", "L2", "L3"):
        for metric, (suffix, label, dev_class, unit) in metric_map.items():
            key = f"ac_out_{phase.lower()}_{suffix}"
            defs[key] = _SensorDef(
                key=key,
                entity_name=f"AC Out {phase} {label}",
                object_id_suffix=key,
                device_class=dev_class,
                unit=unit,
                state_class=SensorStateClass.MEASUREMENT,
            )

    return defs


_AC_OUT_DEFS: dict[str, _SensorDef] = _ac_out_sensor_defs()


@dataclass
class _Runtime:
    state_entities: dict[str, "VictronVeBusStateSensor"]
    ac_out_entities: dict[str, "VictronVeBusAcOutSensor"]
    customname_by_instance: dict[str, str]


async def _migrate_entity_registry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Best-effort migration for the **repeatable** VE-Bus entity_id scheme.

    Project decision (repeatable naming): entity_ids MUST be prefixed with the
    *config entry name slug* (e.g. "ve_base") and MUST NOT contain Victron
    instance numbers (e.g. 276).

    Target patterns:
      - sensor.<cfg_slug>_ve_bus_state
      - select.<cfg_slug>_ve_bus_mode
      - sensor.<cfg_slug>_ve_bus_ac_out_l1_power

    We migrate historical patterns like:
      - sensor.ve_bus_276_ac_out_l1_power   -> sensor.<cfg_slug>_ve_bus_ac_out_l1_power
      - sensor.ve_bus_ac_out_l1_power       -> sensor.<cfg_slug>_ve_bus_ac_out_l1_power
      - sensor.<oldcfg>_ve_bus_ac_out_l1_*  -> sensor.<cfg_slug>_ve_bus_ac_out_l1_*

    We also clear any registry name override so our explicit `_attr_name` is shown.
    """
    try:
        from homeassistant.helpers import entity_registry as er
    except Exception:
        return

    reg = er.async_get(hass)

    cfg_name = (entry.title or "").strip() or (entry.data.get(CONF_NAME) if hasattr(entry, "data") else None) or "ve"
    cfg_slug = re.sub(r"[^a-z0-9_]+", "_", cfg_name.lower()).strip("_")
    if not cfg_slug:
        cfg_slug = "ve"

    # IMPORTANT:
    # We purposely migrate **all** entities owned by this integration platform
    # (platform == DOMAIN), not only those bound to the current config_entry_id.
    # Reason: when a config entry is removed and later re-created, Home Assistant
    # may re-use existing registry entries by unique_id. In that case those
    # entries might still carry an older config_entry_id, and the repeatable
    # naming migration would be skipped if we filtered by entry.entry_id.
    entries = [
        e
        for e in reg.entities.values()
        if getattr(e, "platform", None) == DOMAIN and e.domain in ("sensor", "select")
    ]

    # Historical patterns
    p_inst = re.compile(r"^(?P<domain>sensor|select)\.ve_bus_(?P<inst>\d+)_(?P<rest>.+)$")
    p_plain = re.compile(r"^(?P<domain>sensor|select)\.ve_bus_(?P<rest>.+)$")
    p_cfg = re.compile(r"^(?P<domain>sensor|select)\.(?P<cfg>[a-z0-9_]+)_ve_bus_(?P<rest>.+)$")

    for e in entries:
        if not e.entity_id:
            continue

        # Clear name override (lets entity's _attr_name show).
        if e.name is not None:
            try:
                reg.async_update_entity(e.entity_id, name=None)
            except Exception:
                pass

        new_eid: str | None = None

        m = p_inst.match(e.entity_id)
        if m:
            new_eid = f"{m.group('domain')}.{cfg_slug}_ve_bus_{m.group('rest')}"

        if new_eid is None:
            m = p_plain.match(e.entity_id)
            if m:
                new_eid = f"{m.group('domain')}.{cfg_slug}_ve_bus_{m.group('rest')}"

        if new_eid is None:
            m = p_cfg.match(e.entity_id)
            if m:
                new_eid = f"{m.group('domain')}.{cfg_slug}_ve_bus_{m.group('rest')}"

        if new_eid is None:
            continue

        if new_eid == e.entity_id:
            continue

        # Avoid collisions.
        if reg.async_get(new_eid) is not None:
            continue

        try:
            reg.async_update_entity(e.entity_id, new_entity_id=new_eid)
        except Exception:
            pass



async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    cfg_name: str = (entry.title or entry.data.get(CONF_NAME) or 'home')
    cfg_slug: str = _slug(cfg_name)
    # Entity IDs are prefixed with the config entry name slug for repeatable naming
    # across installations (e.g. sensor.ve_base_ve_bus_state).
    await _migrate_entity_registry(hass, entry)
    prefix: str = entry.data[CONF_TOPIC_PREFIX]
    portal: str = entry.data[CONF_PORTAL_ID]

    runtime: _Runtime = hass.data[DOMAIN][entry.entry_id].setdefault(
        "sensor_runtime",
        _Runtime(state_entities={}, ac_out_entities={}, customname_by_instance={}),
    )

    signal: str = hass.data[DOMAIN][entry.entry_id]["signal"]

    @callback
    def _on_message(topic: str, payload: dict[str, Any]) -> None:
        # CustomName
        m_cn = _VEBUS_CUSTOMNAME_RE.match(topic)
        if m_cn and m_cn.group("prefix") == prefix and m_cn.group("portal") == portal:
            inst = m_cn.group("instance")
            v = payload.get("value")
            if isinstance(v, str) and v.strip():
                custom_name = v.strip()
                runtime.customname_by_instance[inst] = custom_name

                ent = runtime.state_entities.get(inst)
                if ent:
                    ent.set_custom_name(custom_name)

                # Update all AC Out sensors for that instance.
                for aent in list(runtime.ac_out_entities.values()):
                    if aent.vebus_instance == inst:
                        aent.set_custom_name(custom_name)
            return

        # AC Out sensors (Total and per phase)
        m_ac = _VEBUS_AC_OUT_RE.match(topic)
        if m_ac and m_ac.group("prefix") == prefix and m_ac.group("portal") == portal:
            inst = m_ac.group("instance")
            phase = m_ac.group("phase")
            metric = m_ac.group("metric")

            key = _ac_out_key(phase, metric)
            if key is None:
                return

            ent_key = f"{inst}:{key}"
            ent = runtime.ac_out_entities.get(ent_key)
            if ent is None:
                sdef = _AC_OUT_DEFS[key]
                ent = VictronVeBusAcOutSensor(
                    hass=hass,
                    entry=entry,
                    cfg_name=cfg_name,
                    cfg_slug=cfg_slug,
                    portal_id=portal,
                    vebus_instance=inst,
                    custom_name=runtime.customname_by_instance.get(inst),
                    sdef=sdef,
                )
                runtime.ac_out_entities[ent_key] = ent
                async_add_entities([ent])

            ent.handle_value(payload)
            return

        # State
        m = _VEBUS_STATE_RE.match(topic)
        if not m:
            return
        if m.group("prefix") != prefix or m.group("portal") != portal:
            return

        inst = m.group("instance")
        ent = runtime.state_entities.get(inst)
        if ent is None:
            ent = VictronVeBusStateSensor(
                hass=hass,
                entry=entry,
                cfg_name=cfg_name,
                cfg_slug=cfg_slug,
                portal_id=portal,
                vebus_instance=inst,
                custom_name=runtime.customname_by_instance.get(inst),
            )
            runtime.state_entities[inst] = ent
            async_add_entities([ent])

        ent.handle_state(payload)

    async_dispatcher_connect(hass, signal, _on_message)


class VictronVeBusStateSensor(SensorEntity):
    """VE.Bus State sensor."""

    # Use explicit entity names (not "device name + entity name") to keep naming
    # stable and predictable across installations.
    _attr_has_entity_name = False

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        cfg_name: str,
        cfg_slug: str,
        portal_id: str,
        vebus_instance: str,
        custom_name: str | None,
    ) -> None:
        self.hass = hass
        self._entry = entry
        self._cfg_name = cfg_name
        self._cfg_slug = cfg_slug
        self._portal = portal_id
        self._instance = vebus_instance
        self._custom_name = custom_name
        self._state_code: int | None = None

        # Attach all VE-Bus entities to the single Victron GX (Cerbo GX) HA device.
        # We intentionally do NOT create a separate "VE-Bus" device.
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{portal_id}_cerbo_gx")},
            name=HUB_NAME,
            manufacturer=MANUFACTURER,
            model=HUB_MODEL,
        )

        # Entity name (UI). Keep single-language; DE/EN mappings are exposed via attributes.
        self._attr_name = "VE-Bus State"
        self._attr_unique_id = f"{entry.entry_id}_vebus_{vebus_instance}_state"

        # Suggested entity_id (object_id). Must include config slug, but must NOT
        # include the Victron instance number.
        self._attr_suggested_object_id = f"{cfg_slug}_ve_bus_state"

        self._attr_native_value = None

    def set_custom_name(self, custom_name: str) -> None:
        self._custom_name = custom_name
        # Ensure device name is persisted.
        self.async_write_ha_state()

    @callback
    def handle_state(self, payload: dict[str, Any]) -> None:
        value = payload.get("value")
        if isinstance(value, float) and value.is_integer():
            value = int(value)
        if not isinstance(value, int):
            return

        self._state_code = value
        self._attr_native_value = VE_BUS_STATE_MAP.get(value, f"Unknown ({value})")
        self.async_write_ha_state()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        if self._state_code is None:
            return {}
        code = self._state_code
        return {
            "code": code,
            "state_en": VE_BUS_STATE_MAP_EN.get(code, f"Unknown ({code})"),
            "state_de": VE_BUS_STATE_MAP_DE.get(code, f"Unbekannt ({code})"),
        }


def _parse_numeric_value(payload: dict[str, Any]) -> float | None:
    """Parse Victron MQTT JSON payloads into a numeric float.

    Accepts:
    - numbers (int/float)
    - strings with '.' or ',' decimal separators
    """

    v = payload.get("value")
    if v is None:
        return None

    if isinstance(v, bool):
        return None

    if isinstance(v, (int, float)):
        return float(v)

    if isinstance(v, str):
        s = v.strip()
        if not s:
            return None
        s = s.replace(",", ".")
        try:
            return float(s)
        except ValueError:
            return None

    return None


def _ac_out_key(phase: str | None, metric: str) -> str | None:
    """Map regex match groups to our canonical sensor key."""

    if phase is None:
        # Total values: only /Ac/Out/P is relevant for now.
        return "ac_out_power_total" if metric == "P" else None

    metric_map = {
        "P": "power",
        "I": "current",
        "V": "voltage",
        "F": "frequency",
    }
    suffix = metric_map.get(metric)
    if suffix is None:
        return None
    return f"ac_out_{phase.lower()}_{suffix}"


class VictronVeBusAcOutSensor(SensorEntity):
    """VE.Bus AC Out sensors (Total and per phase)."""

    # Use explicit entity names (not "device name + entity name") to keep naming
    # stable and predictable across installations.
    _attr_has_entity_name = False

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        cfg_name: str,
        cfg_slug: str,
        portal_id: str,
        vebus_instance: str,
        custom_name: str | None,
        sdef: _SensorDef,
    ) -> None:
        self.hass = hass
        self._entry = entry
        self._cfg_name = cfg_name
        self._cfg_slug = cfg_slug
        self._portal = portal_id
        self._instance = vebus_instance
        self._custom_name = custom_name
        self._sdef = sdef

        # Attach all VE-Bus entities to the single Victron GX (Cerbo GX) HA device.
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{portal_id}_cerbo_gx")},
            name=HUB_NAME,
            manufacturer=MANUFACTURER,
            model=HUB_MODEL,
        )

        # UI name (explicit) - always prefixed with "VE-Bus".
        self._attr_name = f"VE-Bus {sdef.entity_name}"

        # Keep unique_id instance-based and stable.
        self._attr_unique_id = f"{entry.entry_id}_vebus_{vebus_instance}_{sdef.key}"

        # Suggested entity_id (object_id). Includes config slug, but no instance number.
        self._attr_suggested_object_id = f"{cfg_slug}_ve_bus_{sdef.object_id_suffix}"

        self._attr_device_class = sdef.device_class
        self._attr_state_class = sdef.state_class
        self._attr_native_unit_of_measurement = sdef.unit

        self._attr_native_value = None

    @property
    def vebus_instance(self) -> str:
        return self._instance

    def set_custom_name(self, custom_name: str) -> None:
        self._custom_name = custom_name
        self.async_write_ha_state()

    @callback
    def handle_value(self, payload: dict[str, Any]) -> None:
        val = _parse_numeric_value(payload)
        if val is None:
            return
        self._attr_native_value = val
        self.async_write_ha_state()


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
