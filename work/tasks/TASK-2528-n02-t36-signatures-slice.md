---
id: TASK-2528
title: N-02-T36 Brightwater Hale signatures slice
spec: SPEC-381  # N-02 §9; SIG-01, SIG-02, POR-06, ENG-04
acceptance_criteria: [AC-11]  # and N-02 §9 (N-02-T36)
risk_zone: amber
status: done
epic: N-02
plan_key: N-02-T36
branch: s20c-n02-t36
worktree: /Users/ayushkbhatia/Accrued/abacus-s20b
created: 2026-10-31
updated: 2026-10-31
---

## Objective
The signatures slice of the Python scenario: E1–E17 to E0, E18, the Kowal KBA failures, the Rao
expiry, Copperleaf's letter, the Ridgeline E13 and Fairhaven E11 letters, the Feld consents; ERSD
disclosure v1 as database content; fixtures export equivalence with N-02-T10.

Acceptance (backlog row): "make seed-demo reproduces the SIG-01 counts at E0 and the fixtures
export matches the TypeScript scenarios."

## Plan (amber)
- `brightwater_hale/signatures.py` (rows, counts, slice), loader handlers
  `signatures.disclosure_imported` and `signatures.envelope_recorded`, SLICE_NEEDS.
- `fixture_export.scenario_files()` → `seed/scenario.signatures-hub.json`; vitest equivalence.
- `signatures/hub.py`: the Completed window in business time.
- Tests: unit footing and export currency; loaded-DB SIG-01 counts.
- Rollback: drop the slice registration and handlers; the hub line reverts to `system_now()`.

## Progress log
- `2026-10-31` — Built on `s20c-n02-t36` off main. Unit 5 passed, loaded test 1 passed, N-02-T13
  hub tests green, vitest equivalence 2 passed.
