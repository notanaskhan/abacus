---
id: TASK-6712
title: "A-07-T45: hardening: mutation floors (ADR-079, target 75%) for release, the archive gate, the lock and the seal, with survivor triage; p95 budgets under the x25 profile"
spec: SPEC-644
acceptance_criteria: [AC-37]
risk_zone: red
status: in-review
branch: s35-a07-t45
worktree: /Users/ayushkbhatia/Accrued/abacus-s35
created: 2026-11-10
updated: 2026-11-10
plan_key: A-07-T45
---

## Objective
`backend/mutation-thresholds.yaml` records the floors and the p95 budgets hold on staging.

## Plan (red)
1. `abacus_tools/quality/mutation.py`: red scope `assurance/release_archive` (release.py,
   archive_gate.py, archive_lock.py, archive_seal.py, archive_additions.py); `evidence/archive.py`
   stays in `evidence`, `archived_guard()`'s registry in `kernel/db`.
2. `mutation-thresholds.yaml` and `coverage-thresholds.yaml`: the scope at 0 (raised to its first
   run, as every new scope; a floor above the first run fails it before triage), target 75; the
   p95 budgets recorded beside it.
3. `abacus_tools/loadtest/a07_budgets.py`: the four budgets and `breaches`.
4. Survivor triage tests: `tests/unit/assurance/test_a07t45_hardening.py` (grant digest parts,
   workflow ids, Merkle root odd node and empty binder, canonical form).

## Partial
- The first mutation run of the new scope (and raising its floor to 75 with survivor triage) runs
  in the weekly mutation job or at the end pass if time allows; until then the floor is 0.
- The p95 budgets are checked on staging's x25 load run (no staging in this session).

## Progress log
- `2026-11-10` — Built; tests written, not run (end pass).
