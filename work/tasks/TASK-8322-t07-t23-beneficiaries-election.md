---
id: TASK-8322
title: "T-07-T23: Beneficiaries, K-1 (1041) packages and the 65-day election"
spec: SPEC-656
acceptance_criteria: [AC-9, AC-11]
risk_zone: amber
status: in-review
branch: t07-t23-beneficiaries-election
worktree: /Users/ayushkbhatia/Accrued/abacus-s47g04
created: 2026-11-16
updated: 2026-11-16
plan_key: T-07-T23
---

## Objective
Spec section: docs/plan/epics/T-07.md F9 to F11.
Beneficiaries, K-1 (1041) packages and the 65-day election.

## Plan (amber)
1. `tax/fiduciary_beneficiaries.py`: `allocate` (shares by class, the last takes the rounding), `window_end` (65th day after year-end), `record_election` (a person with `fiduciary_election.record` on an engagement of the entity; a new row each time; the elected amount paid inside the window).
2. `tax/fiduciary_contract.py`: the election route calls the service.
3. Audit kind reviewed. Tests: `tests/unit/tax/test_t07t23_beneficiaries.py`.

## Progress log
- `2026-11-16` — Built in the S47 sequential stack (DEC-5317). The app imports; the unit file ran green (4 tests). Partial: the TXT-03 beneficiaries read model (allocation statement, TIE-OUT and DELIVERY rows, release steps), the draft K-1 (1041) packages through T-02's package service with the DEC-88 hand-off, and the trustee question draft still answer 501. Gates and
  tests run once at the S47 end pass (build first, test last).
