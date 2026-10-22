---
id: TASK-375
title: Python Brightwater Hale scenario package skeleton (F-04-T10)
spec: SPEC-307
acceptance_criteria: [AC-1, AC-2, AC-3, AC-4]
risk_zone: amber
status: done
epic: F-04
plan_key: F-04-T10
branch: f04-t10-scenario
created: 2026-10-22
updated: 2026-10-22
---

## Objective
"Deterministic package with a SCENARIO_VERSION golden hash yields 184 clients with no suffix and
only reserved identifier ranges."

## Plan (amber)
- `abacus_tools/synthetic/scenarios/brightwater_hale/` (path per F-04 R-6): `prng` (the TS seed's
  label-keyed draws, bit for bit), `people` (46 seats, offices, firm roles), `clients` (16 named,
  66 roster, 102 filler), `epochs` (E0/E1/E2 view epochs, 11 named snapshots), `holdouts`
  (`fairhaven_ebp`, `copperleaf`), `slices` (registry; F-04 registers `audit_core`), `timeline`
  (events with stable ids and `scenario:<version>:<id>` trace ids), `scenario` (`build`,
  `canonical`, `fingerprint`, `SCENARIO_VERSION` + `SCENARIO_HASH`).
- The canonical rows were extracted from the TS seed by running it (no hand copying); the
  draws are the TS seed's, not `synthetic.rng`'s, so the F-04-T05 fixtures stay identical until
  F-04.21 exports them from here. The 27 audits and the portal minimum land with the loader
  (F-04-T13).
- A shared golden (`tests/golden/scenario/brightwater_hale/clients.json`) is checked from both
  sides: pytest for Python, vitest for TS.

## Definition of done
- [x] `tests/unit/scenarios/test_brightwater_hale.py` (counts, seats, no suffix, filler words,
  parity, hash pinned to version, snapshots, holdouts, reserved ranges, mailbox domain)
- [x] `apps/web/src/fixtures/scenario-parity.test.ts`
- [x] `make check-fast`

## Progress log
- 2026-10-22: built in one session.
