---
id: TASK-377
title: Platform tenancy migration - region, tenant keys, kill-switch controls, operator provisioning (Q-01-T19)
spec: SPEC-000
acceptance_criteria: [AC-21]
risk_zone: red
status: done
epic: Q-01
plan_key: Q-01-T19
branch: q01-t19-platform-tenancy
created: 2026-10-22
updated: 2026-10-22
---

## Objective
"The app role reads controls only through the definer, cannot set synthetic or region, and
schema_check passes up, down and up." (ADR-157 proposed, built per the solo amendment; ADR-156)

## Plan (red)
- Migration 0086: `firms.region` ('us' only), `kms_key_arn`, `kms_key_status`,
  `kms_replica_verified_at` (app: read all, update the key columns); global `platform_controls`
  (the CHECK is the kill-switch registry), insert-only `platform_control_changes` (trigger),
  `firm_provisioning_requests`; no app privileges on any. Definers `platform_control_state()`
  (app), `set_platform_control(...)` and `provision_firm(...)` (`abacus_ops` only).
- `bootstrap.sql`: `abacus_ops` (LOGIN, NOINHERIT, no table privileges); local password.
- `schema_check`: the three definers reviewed; `OPS_ONLY_FUNCTIONS` (ops must, app must not
  execute); the global tables; platform registry and identity's firms update columns.
- Deviations: `provision_firm` takes no slug (firms has none; the portal slug arrives with
  P-08); the `platform_control.changed` outbox event lands with its consumer and
  `platform.api.control_active`, so only the audit event is written now.
- Rollback: revert, downgrade 0086 (the role stays; it holds nothing).

## Definition of done
- [x] `tests/integration/test_platform_tenancy.py`: no app or ops table privileges on the global
  tables, controls read only through the definer, synthetic and region not settable by the app,
  idempotent US-only provisioning by ops (refused for the app), versioned, logged and audited
  firm controls, insert-only change log
- [x] `tests/integration/test_schema_check_db.py` (up, down, up; reviewed definers)
- [x] `make check-fast`

## Progress log
- 2026-10-22: built in one session.
