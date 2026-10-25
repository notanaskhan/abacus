---
id: TASK-1253
title: S8 back-fill defect fixes for connections, ledger and GL suites (Q-03-T025)
spec: SPEC-034
acceptance_criteria: []
risk_zone: red
status: done
epic: Q-03
plan_key: Q-03-T025
branch: q03-t025-backfill-fixes
created: 2026-10-26
updated: 2026-10-26
---

## Objective
"No S8 back-fill failure is open at the S9 Contract Monday."

## Plan (red zone)
Triage only: run every S8 back-fill suite (Q-03-T021 to T024, TASK-1232) on `main` and fix what
fails; check `docs/quality/escaped-defects.md` for an open row from those suites. No production
change unless a suite fails. **Rollback:** nothing to revert.

## Results
- On `main` at `278152f6` (after the S8 leftovers batch, migrations to 0160), files passed to
  pytest sorted: `backfill/test_classification_board.py`, `test_firm_level_reads.py`,
  `test_gl_detail.py`, `test_ledger_formats.py`, `test_q03t021_scope_kinds.py`,
  `test_q03t022_connections_and_ledger_import.py`, `test_roll_forward.py`: **195 passed**, no
  xfail, no skip. Vitest `legacy/q03ledgerstates.test.tsx` and `legacy/spec025states.test.tsx`:
  **18 passed**.
- The suites' three defects (ED-047, ED-052, ED-055) were fixed in TASK-1232 itself. The open
  rows in `escaped-defects.md` (ED-007, ED-008, ED-010, ED-015, ED-016) come from earlier suites
  (Q-03-T007, T008; P-01-T14), not S8's.
- Not failures, left as TASK-1232 recorded them: the spec gaps the tests accept either way, and
  SPEC-034 AC-6 ("same snapshot, same bytes", not reachable over HTTP).

## Progress log
- 2026-10-26: verified on `main`; nothing open. CI's integration shards had not yet run on
  `278152f6` when this was written (queued behind earlier runs).
