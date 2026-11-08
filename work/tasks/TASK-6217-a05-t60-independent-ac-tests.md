---
id: TASK-6217
title: A-05-T60 independent AC tests for A-05-T41, T48, T55 and T56
spec: SPEC-640
acceptance_criteria: [AC-1]  # no agent path records a classification, conclusion or screen-out; sealed names stay in the database
risk_zone: red
status: in-review
epic: A-05
plan_key: A-05-T60
branch: s31-a05-t60
worktree: /Users/ayushkbhatia/Accrued/abacus-s31
created: 2026-11-08
updated: 2026-11-08
---

## Plan (red: written before building)
- Files, tests only (ADR-078: written from the rows and A-05 F9/F11, not the authors' tests):
  `tests/integration/test_a05t60_ebp_accounts_independent.py` (T41: eight tables with forced RLS
  and a policy; no plaintext SSN column; the balance and SDBA schedules seal like the census; the
  app role can't update the sealed columns or delete) and
  `tests/unit/assurance/test_a05t60_modes_independent.py` (T55/T56: the agent and system denied
  every recording act; the drafter has no tools; the mode modules only read; no read selects
  `name_sealed`; the related-parties read answers display refs; the mode hands no facts).
- T48 is not repeated: Q-03-T206 wrote its independent suite (`test_a05t48_estimates_rp_independent.py`).
- No migration, registry or flag edit. Rollback: delete the two files.

## Decisions made during this task
None (tests only).

## Progress log
- 2026-11-08: written; runs at the S31 end pass (the integration file needs the provisioned DB).
