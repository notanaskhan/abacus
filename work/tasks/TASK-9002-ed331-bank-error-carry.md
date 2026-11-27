---
id: TASK-9002
title: "Q-03-T379: CV-3 ED-331 fix and the 2028 Q4 escaped-defect fix-forward"
spec: SPEC-000
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: amber
status: in-review
branch: s54-cv3-ed331-bank-error-carry
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-26
updated: 2026-11-26
plan_key: Q-03-T379
---

## Objective
DEC-6003 CV-3 under Q-03-T379: Every escaped defect of the period has a fix and a recurrence test, and the log names the layer that missed it.

## Done
- closes/compute/reconciliation.py: engine version 2 carries a prior bank-side bank_error (ED-331)
- tests/unit/closes/test_cv3_ed331_bank_error_carry.py: 5 cases
- re-pinned the reconciliation engine stamp and three hashes to version 2 (proved: with the stamp set back to 1 the new code reproduces every pinned result, 125 passed)
- docs/quality/sweeps/2026-11-26-q03-t379-fix-forward.md: ED-331 and ED-340 to ED-347 with fix, recurrence test and layer
- DEC-6008

## Progress log
- `2026-11-26` — Built; closes unit and golden suites 361 passed.
