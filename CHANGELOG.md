# Changelog

## 0.1.7-pre-8

- Add: VE.Bus emergency shutdown switch (write-only to Mode=4).
- Add: VE.Bus grid active switch (write-only to Mode=3).
- Fix: enforce global entity-id naming convention for VE.Bus entities: `<entity_domain>.<cfg_slug>_ve_bus_<suffix>`.
- Fix: automatic entity-id migration on restart updated to migrate legacy entity_ids (including `switch.grid_active` and `switch.ve_bus_*`) to the global scheme (best-effort, collision-safe).

