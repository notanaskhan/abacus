---
id: TASK-8446
title: W-01-T07 rest — the per-integration kill switch, per firm or platform-wide (AC-4; OQ-9; ADR-157)
spec: SPEC-659
acceptance_criteria: [AC-4]
risk_zone: red
status: in-review
branch: s48r-w01-t07-kill-switch
created: 2026-11-17
updated: 2026-11-17
plan_key: W-01-T07
---

## Objective
W-01-T07 (TASK-8098) left out "a platform-wide per-integration kill switch (ADR-157 proposed)":
"Paused" read from the install's status only. ADR-157 was accepted on 2026-11-15 (44ec41134), so
the switch is built on its registry, `platform_controls`. Decided as DEC-5433.

## Plan (red: kernel controls, a migration on a global table)
1. **Migration 0948** (on 0947): `integration_pause` joins the `control` CHECK of
   `platform_controls` and `platform_control_changes`, and the keyed-column CHECK becomes
   `(control IN ('model_route_block', 'integration_pause')) = (route IS NOT NULL)`: the key
   (`route`) is the catalogue key. Expand-only; downgrade removes `integration_pause` rows from
   `platform_controls` and narrows its CHECKs (the history is insert-only and keeps the name,
   0156's precedent).
2. **Kernel.** `kernel/controls.py`: `ControlName` gains `integration_pause`; keyed controls
   (`model_route_block`, `integration_pause`) match their key. Unknown state keeps the last known
   value (a pause is not fail-closed: an outage must not take every integration down).
3. **Integrations.** `integration_paused(tenant_id, key)` (platform scope or this firm):
   - the catalogue (WB-10) and the drawer (WB-11): an installed integration reads `paused`
     ("Paused") with Reconnect and Enable hidden; an uninstalled one is `coming_soon` (AC-4:
     `available` only while the kill switch is clear);
   - connect starts refuse 409 `integration_paused` (firm, personal and POR-16's client start);
   - the health pass skips a paused integration's connections (no adapter call).
4. **Operator path.** `set_platform_control('integration_pause', scope, tenant, <key>, ...)`
   through the existing ops command; `docs/contracts/platform-ops.md` §3.7 gains the row; the
   game-day list gains the switch.
- **Tests:** unit for the kernel's keyed match; integration
  `tests/integration/test_w01t07_kill_switch.py` (platform and firm scope, the catalogue words,
  the connect refusal, the migration round trip).
- **Rollback:** downgrade 0948 (no row carries the value afterwards), revert.

## Progress log
- 2026-11-17: planned (DEC-5433). S49's stack also chains 0950 on 0947: the second to merge
  re-chains.
- 2026-11-17: built. Migration 0948 (both CHECKs on both tables; the unnamed keyed CHECK found by
  its definition and replaced with `<table>_route_check`), `kernel.controls` keyed match,
  `integrations.kill_switch`, the catalogue/drawer words, the connect refusals (firm, personal,
  completion, POR-16), the health-sweep skip, the ops command's `--integration`, platform-ops
  §3.7 rows (also the missing `confirmation_links` row) and RB-04's command.
- Tests: integration `test_w01t07_kill_switch.py` 3 green; W-01 integration and kill-switch
  neighbours 325 green (one parallel-run flake in `test_w01t07_catalogue_import.py` AC-32, green
  alone and in two parallel reruns). `schema_check`'s up/down/up round trip runs through 0948;
  its one reported problem (`component_deliverables.went_late_at` grant) and
  `test_p01t14_notifications` are main's (S48), not this change.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-5433 | `integration_pause`, keyed by catalogue key, per firm or platform; Paused for an install, coming soon otherwise; adapter calls refused; not fail-closed | no |
