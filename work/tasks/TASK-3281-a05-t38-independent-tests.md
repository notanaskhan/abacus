---
id: TASK-3281
title: A-05-T38 independent AC tests for the P-58 ledger path and the EBP migrations
spec: SPEC-000  # row (SPEC-640 F6, F7)
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
epic: A-05
plan_key: A-05-T38
branch: s27-a05-t38
worktree: /Users/ayushkbhatia/Accrued/abacus-s27
created: 2026-11-04
updated: 2026-11-04
---

## Objective
ADR-078 tests for A-05-T26, T27, T28, T35 and T36.

## Plan (amber)
- `backend/tests/unit/assurance/test_a05t38_independent.py`: P-58 refuses a footing difference
  (no amount in the error), a line without a citation and a citation C4 does not verify; the
  snapshot names its document and extraction run and is never adopted in the ledger path; the agent
  is denied `trial_balance.adopt`; 0659's provenance CHECK; 0658 and 0665 tables tenant-scoped,
  the correction human-only CHECK and insert-only events, the certification evaluation bound to the
  session's actor.
- No production changes; rollback is deleting the file.

## Progress log
- 2026-11-04: written; ruff clean; run at the end pass. T27's mode `ebp_reconcile` eval case (line
  4a never includes the match) is A-05-T33's suite; the provenance on AUD-06 is asserted through the
  snapshot columns here and AUD-06's own tests.
