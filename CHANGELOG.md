# Changelog

All notable changes to this project will be documented in this file.

## 0.1.6-pre-7
- Fix: deterministic Entity IDs using the config name (slug) as prefix (e.g. `sensor.<cfg>_ve_bus_...`).
- Fix: enforce "VE-Bus" prefix in all entity display names.
- Fix: unify device metadata (manufacturer/model/name) so all entities belong to the same device.
- Add: set manufacturer to "Victron Energy" for the device.
- Add: include repository-level files for HACS (logos) and Home Assistant changelog visibility.

## 0.1.5-pre-6
- Add: VE-Bus sensors & select entities (initial usable VE-Bus feature set).
- Add: basic config flow (MQTT connection parameters).

## 0.1.4-pre-5
- Improvements and internal refactoring.

## 0.1.3-pre-4
- Improvements and internal refactoring.

## 0.1.2-pre-3
- Improvements and internal refactoring.

## 0.1.1-pre-2
- Initial pre-release iterations.

## 0.1.0-pre-1
- Initial pre-release.
