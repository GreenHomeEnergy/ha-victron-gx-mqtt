# Victron GX MQTT – Home Assistant Integration

➡️ **Deutsch:** [Zur deutschen Beschreibung springen](#deutsche-beschreibung)

---

## Overview

This Home Assistant custom integration connects a **Victron GX system**
(e.g. Cerbo GX with MultiPlus / MultiPlus-II) to Home Assistant via **MQTT**.

It is designed for **stable, long-running monitoring and control** of
**VE-Bus based Victron systems** using **Venus OS MQTT topics**.

All entities are created **dynamically from MQTT data**.
No manual YAML sensor configuration is required.

---

## ⚠️ Prerequisites (Important)

This integration **does not connect directly** to the Victron GX device.  
It relies entirely on **MQTT topics published by Venus OS**.

Before installing this integration, **all prerequisites below must be met**.

---

## Required Victron Setup

### Victron GX / Venus OS
- Cerbo GX (or compatible GX device)
- **Venus OS with MQTT enabled**
- MQTT publishing must be **permanently active**
- Keepalive publishing is strongly recommended

---

## Required Home Assistant Components

### Home Assistant Core
- Home Assistant with MQTT integration enabled

### Required Add-ons / Services
- Mosquitto Broker (Home Assistant Add-on) or any external MQTT broker

---

## 🔁 MQTT Bridge (Critical Requirement)

In most installations, the Victron GX device and Home Assistant
**do not use the same MQTT broker**.

In this case, an **MQTT bridge is mandatory**.

The bridge must forward all Victron MQTT topics unchanged and keep
retained messages intact.

---

## Installation (HACS – Recommended)

1. Open **HACS**
2. Go to **Integrations**
3. Click **Explore & Download Repositories**
4. Search for **Victron GX MQTT**
5. Install the integration
6. Restart Home Assistant

---

<a id="deutsche-beschreibung"></a>

## Deutsche Beschreibung

Diese Home Assistant Integration bindet ein **Victron GX System**
(z. B. Cerbo GX mit MultiPlus / MultiPlus-II) über **MQTT** an Home Assistant an.

Die Integration nutzt ausschließlich die von **Venus OS veröffentlichten MQTT Topics**
und verbindet sich **nicht direkt** mit dem GX-Gerät.

### Voraussetzungen (zwingend)

- Venus OS mit aktiviertem MQTT
- MQTT Broker (z. B. Mosquitto Add-on)
- In den meisten Installationen: **MQTT Bridge zwischen GX und Home Assistant**
