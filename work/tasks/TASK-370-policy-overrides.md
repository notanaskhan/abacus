---
id: TASK-370
title: Firm setting values, stricter-only firm policy overrides and DEC-38 (F-03-T24, part 2 of 2)
spec: SPEC-025
acceptance_criteria: [AC-7]
risk_zone: red
status: done
epic: F-03
plan_key: F-03-T24
branch: f03-t24-overrides
created: 2026-10-22
updated: 2026-10-22
---

## Objective
"…and a property test proves no firm override widens the matrix ceiling." Part 1 (TASK-369)
shipped the conditions. This part: generic `firm_setting(<key>)` for people, stricter-only
`firm_policy_overrides`, and DEC-38 recorded.

## Plan (red)
- Migration 0081: `firm_setting_values(tenant_id, key, value, version, set_by, set_at)` with a
  CHECK on the registered keys; `firm_policy_overrides(tenant_id, action, role, decision = 'deny',
  reason, set_by, set_at)`, insert-only. RLS on both; identity registry.
- `authz/matrix.py`: `FIRM_SETTING_KEYS`; a person's cell naming any other key, or an agent's
  naming anything but `autonomy_policy`, is an import error.
- `authz/overrides.py` (pure): `apply_override` (deny or the ceiling), `refusal` (unknown
  action, read, `firm.manage_settings`, platform role, empty cell, widens).
- `authorise` layer 3: the firm's policy (overrides and settings on) read once per request
  (`recording_checks`); overrides applied to every cell first; a person's `firm_setting(<key>)`
  allows while <key> is on.
- Writers in `firm_settings.py` (`firm.manage_settings`, fresh MFA): `set_firm_setting`
  (`firm_setting.set`), `set_policy_override` (`firm_policy_override.set`). No routes yet: ADM-02
  (G-01) builds the screen.
- `tests/unit/conftest.py` stubs the policy read (unit tests have no database, as for walls).
- DEC-38 decided; DEC-127 records what an override may do. Rollback: revert, downgrade 0081.

## Definition of done
- [x] `tests/unit/identity/test_policy_overrides.py`: hypothesis property tests (one cell, a
  whole firm's policy, the writer's acceptance) prove no override widens the ceiling; refusal
  reasons; registered keys (parser, matrix, migration CHECK); through `authorise`: override
  denies, allow override grants nothing, setting on/off, override beats setting, read once
- [x] `tests/integration/test_firm_policy.py`: CHECKs and tenant-scoped read on Postgres
- [x] Backend unit suite (7,010)
- [x] `make check-fast`

## Not modelled (DEC-38 cells land with their actions)
Binder publish and the published-binder condition (P-06); a firm-level staff relationship for
`engagement.create` `level_in(partner, manager)` (F-03-T30, G-01); pinned-step
`methodology.read` (K-01); TAX-12 (EP-09). Override removal and `visible()` support: G-01.

## Progress log
- 2026-10-22: built and merged in one session.
