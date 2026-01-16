# ha-victron-gx-mqtt

Home Assistant integration (HACS) for **Victron GX / Cerbo GX / Venus OS** using **MQTT**.  
This project assumes you already forward Victron MQTT traffic to your Home Assistant MQTT broker via a **Mosquitto bridge** and keep the publishing alive via a **keepalive automation**.

---

## Deutsch – Kurzbeschreibung

Diese Integration nutzt die MQTT-Daten deines Victron GX Systems (Cerbo GX / Venus OS).  
**Wichtig:** Die MQTT Topics aus dem Cerbo müssen per **Mosquitto Bridge** in deinen Home Assistant MQTT Broker gespiegelt werden – und per **Keepalive-Automation** dauerhaft aktiv gehalten werden.  
Ohne Bridge und Keepalive erscheinen Topics oft nur kurz oder verschwinden nach einigen Sekunden.

---

## English – Short description

This integration consumes MQTT data from a Victron GX system (Cerbo GX / Venus OS).  
**Important:** You must mirror Victron topics into your Home Assistant MQTT broker using a **Mosquitto bridge** and keep the Cerbo publishing enabled via a **keepalive automation**.  
Without bridge + keepalive, topics may only appear briefly and then disappear.

---

## Prerequisites (required)

- Home Assistant (recommended: HA OS / Supervised)
- MQTT broker available to Home Assistant (commonly **Mosquitto broker add-on**)
- Home Assistant MQTT integration configured and connected
- Victron GX device (Cerbo GX / Venus OS) reachable in your network

---

## Step 1 (required) — Create Mosquitto bridge config

Create a bridge configuration file in Home Assistant under:

`/share/mosquitto/bridge-venus.conf`

> Tip: If you use the HA File Editor add-on, you can edit files in `/share/…`.  
> Your existing example file name is **bridge-venus.conf** (recommended to keep).

### Example bridge configuration (template)

Replace the placeholders:

- `MQTT_BRIDGE_NAME` → e.g. `venus-home`
- `CERBO_IP` → Cerbo GX / Venus OS IP address (e.g. `192.168.XXX.XXX`)
- `MQTT_TOPIC_PREFIX` → prefix used locally inside your HA broker (e.g. `venus-home/`)

```conf
# MQTT Bridge Configuration under \\<HA_IP>\share\mosquitto

connection MQTT_BRIDGE_NAME
address CERBO_IP:1883

topic N/# in 0 MQTT_TOPIC_PREFIX
topic R/# out 0 MQTT_TOPIC_PREFIX
topic W/# out 0 MQTT_TOPIC_PREFIX
```

### Concrete example

```conf
# MQTT Bridge Configuration unter \\<HA_IP>\share\mosquitto

connection venus-home
address <CERBO_IP>:1883
topic N/# in 0 venus-home/
topic R/# out 0 venus-home/
topic W/# out 0 venus-home/
```

Restart the Mosquitto broker add-on after saving.

---

## Step 2 (required) — Keepalive automation

Create a Home Assistant automation to keep the Cerbo publishing MQTT data.

### Template

```yaml
alias: KeepAlive MQTT Victron
description: Request the data on the MQTT server
mode: single
trigger:
  - platform: time_pattern
    seconds: "/20"
action:
  - service: mqtt.publish
    data:
      topic: <MQTT_TOPIC_PREFIX>/R/<VRM_PORTAL_ID>/keepalive
      payload: "{}"
      qos: 0
      retain: false
```

### Concrete example

```yaml
alias: KeepAlive MQTT Victron
description: Request the data on the MQTT server
mode: single
trigger:
  - platform: time_pattern
    seconds: "/20"
action:
  - service: mqtt.publish
    data:
      topic: venus-home/R/<VRM_PORTAL_ID>/keepalive
```

---

## Where to find the VRM Portal ID

- Cerbo GX UI: **Settings → VRM online portal**
- VRM Portal website: system details page

---

## License

MIT License

