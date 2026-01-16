from __future__ import annotations

from homeassistant.const import Platform

DOMAIN = "victron_gx_mqtt"

PLATFORMS: list[Platform] = [Platform.SENSOR]

CONF_NAME = "name"
CONF_TOPIC_PREFIX = "topic_prefix"
CONF_PORTAL_ID = "portal_id"

CONF_SELECTED_SERVICES = "selected_services"

SERVICE_VEBUS = "vebus"
SERVICE_SYSTEM = "system"
SERVICE_SOLARCHARGER = "solarcharger"
SERVICE_BATTERY = "battery"
