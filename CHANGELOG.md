# Changelog

Full change history for the **Victron GX MQTT** Home Assistant integration.
This project uses pre-release versions in the format: `0.x.y-pre-n`.

## 0.1.6-pre-7
### Added
- VE.Bus **AC Out** sensors for inverter output (house consumption):
  - Total: Power (`Ac/Out/P`)
  - Per phase **L1/L2/L3**: Power (`P`), Current (`I`), Voltage (`V`), Frequency (`F`)
- Robust value parsing for MQTT payloads:
  - Supports numeric JSON values (float/int) and string values with `.` or `,` decimal separators.

### Changed
- Deterministic VE.Bus naming behavior:
  - Device name fixed to **`VE-Bus`**.
  - Entity IDs are deterministic and do not include the Victron instance number (e.g., `276`).
  - Entity IDs are prefixed by the **integration instance name** (Config Entry title), slugified.
  - Entity UI names are explicitly set (prefixed with `VE-Bus …`) to prevent Home Assistant auto-prefixing.

### Fixed
- Correct units, device classes, and state classes for AC Out sensors:
  - Power → `W` (`device_class=power`, `state_class=measurement`)
  - Current → `A` (`device_class=current`, `state_class=measurement`)
  - Voltage → `V` (`device_class=voltage`, `state_class=measurement`)
  - Frequency → `Hz` (`device_class=frequency`, `state_class=measurement`)

---

## 0.1.5-pre-6
### Added
- Stabilized the project foundation for deterministic naming and device mapping aligned with Victron DBus/MQTT structure.
- Consolidated VE.Bus identity rules and clean separation of `entity_id` vs `unique_id`.

### Changed
- UI names standardized to single-language (English); multilingual information is provided via attributes where applicable.
- Removed instance numbers from entity IDs by design (entity IDs are stable; unique IDs remain instance-based).

---

## 0.1.3-pre-4
### Added
- Initial VE.Bus topic discovery via Home Assistant Core MQTT (`homeassistant.components.mqtt`).
- VE.Bus **State** sensor.
- VE.Bus **Mode** select (writeable via MQTT).
- Asynchronous handling of `CustomName` (often arrives later than State/Mode).

---

## Earlier internal iterations
- Earlier iterations existed prior to 0.1.3-pre-4; detailed notes were not captured in a structured changelog.
