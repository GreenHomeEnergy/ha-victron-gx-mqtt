# Changelog  

Dieses Changelog ist **kumulativ und global** gemäß GLOBAL_RULES.md.
Es enthält alle Änderungen aller Versionen.

---

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog  
and this project uses pre-release versioning.

---

## [0.1.8-pre-9] – Finaler Stand für Release

### Added
- VE-Bus Battery Sensoren unter Device **Cerbo GX**:
  - VE-Bus Battery SOC (`.../vebus/<n>/Soc`)
  - VE-Bus Battery Power (`.../vebus/<n>/Dc/0/Power`)
  - VE-Bus Battery Current (`.../vebus/<n>/Dc/0/Current`)
  - VE-Bus Battery Voltage (`.../vebus/<n>/Dc/0/Voltage`)
- Schreibbare VE-Bus Battery DVCC Settings (Settings/SystemSetup):
  - VE-Bus Battery DVCC Max Charge Voltage (`.../settings/0/Settings/SystemSetup/MaxChargeVoltage`) – **2 Nachkommastellen**
  - VE-Bus Battery DVCC Max Charge Current (`.../settings/0/Settings/SystemSetup/MaxChargeCurrent`)

### Changed
- VE-Bus **AC Out Frequency**: Anzeige mit **2 Nachkommastellen**.
- VE-Bus **Battery SOC**: Anzeige mit **2 Nachkommastellen**.
- VE-Bus **Battery Voltage**: Anzeige mit **2 Nachkommastellen**.

### Fixed
- Sensor-Plattform stabilisiert (Import-/Runtime-Probleme behoben).
- Number-Plattform stabilisiert (korrekte Topic-Matches/Regex, robustes Parsing von `{"min":...,"max":...,"value":...}`).
- Entity-ID Migrationen gemäß GLOBAL_RULES.md:
  - `number.<cfg>_ve_bus_ac_in_current_limit`
  - `number.<cfg>_ve_bus_battery_dvcc_max_charge_voltage`
  - `number.<cfg>_ve_bus_battery_dvcc_max_charge_current`

---

## [0.1.7-pre-8] - 2026-01-23

### Added
- VE-Bus AC In sensor set:
  - Total Power
  - L1/L2/L3: Power, Voltage, Current, Frequency
- VE-Bus AC In Current Limit as NumberEntity (writeable configuration)
- Automatic migration for:
  - number.ac_in_current_limit
  - number.ve_bus_ac_in_current_limit
  ? number.<cfg>_ve_bus_ac_in_current_limit

### Changed
- Frequency sensors now show 2 decimal places (e.g. 49.95 Hz)
- Consistent entity naming according to global rules:
  - domain.<cfg>_ve_bus_<subsystem>_<object>
- Grid Active switch renamed to:
  - VE-Bus Grid Active

### Fixed
- AC Out entity handling restored after regression
- Correct parsing of JSON payloads with {"value": ...}
- Config Flow import errors due to indentation fixed
- Device assignment for NumberEntity corrected (no extra device created)
- Restored AC Out topic key mapping

---

## [0.1.7-pre-7] - 2026-01-20

### Added
- VE-Bus Emergency Shutdown switch
- Grid Active control switch
- Automatic entity ID migration framework

### Changed
- Unified naming schema introduced:
  - domain.<cfg>_ve_bus_<subsystem>_<object_id_suffix>

---

## [0.1.7-pre-6] - 2026-01-18

### Added
- VE-Bus Mode sensor
- VE-Bus State sensor

### Fixed
- MQTT reconnect handling improved
- Initial device grouping logic refined

---

## [0.1.7-pre-5] - 2026-01-16

### Added
- Basic VE-Bus AC Out sensors:
  - L1/L2/L3 Power
  - L1/L2/L3 Voltage
  - L1/L2/L3 Current
  - L1/L2/L3 Frequency
  - Total Power

---

## [0.1.7-pre-4] - 2026-01-14

### Added
- VE-Bus Grid Active read sensor
- Initial switch support for VE-Bus control topics

---

## [0.1.7-pre-3] - 2026-01-12

### Added
- Device auto-discovery via MQTT
- Dynamic entity creation based on received topics

---

## [0.1.7-pre-2] - 2026-01-10

### Added
- First VE-Bus sensor mappings
- Base MQTT subscription framework

---

## [0.1.7-pre-1] - 2026-01-08

### Added
- Initial 0.1.7 development branch created
- Migration framework scaffold

---

## [0.1.6-pre-7] - 2025-12-28

### Added
- Stable VE-Bus AC Out sensor set
- Basic entity naming conventions introduced

### Fixed
- MQTT topic parsing for multi-phase systems
- Initial changelog structure created

---

## [0.1.6-pre-6] - 2025-12-22

### Added
- Multi-device support for multiple GX systems

---

## [0.1.6-pre-5] - 2025-12-18

### Added
- First functional Home Assistant integration
- Sensor platform base implementation

---

## [0.1.6-pre-4] - 2025-12-15

### Added
- MQTT connection management
- Config entry framework

---

## [0.1.6-pre-3] - 2025-12-12

### Added
- Project bootstrap
- Initial repository structure

---

## [0.1.6-pre-2] - 2025-12-10

### Added
- Prototype MQTT listener

---

## [0.1.6-pre-1] - 2025-12-08

### Added
- First experimental code