---
id: TASK-3347
title: A-05-T40 EBP-06's fund subtotal from code, and the lit cell
spec: SPEC-000  # row (A-05-T40)
acceptance_criteria: [AC-1]
risk_zone: green
status: in-review
epic: A-05
plan_key: A-05-T40
branch: s28r-a05-t40
worktree: /Users/ayushkbhatia/Accrued/abacus-s28
created: 2026-11-06
updated: 2026-11-06
---

## Objective
Close the parts of DEC-2319 that don't wait on another screen.

## Plan
- `trust_agreement.agree` computes `funds_eoy` and `funds_boy`; `InvestmentsOut` carries them.
- EBP-06: the group row, the subtotal, brokerage after it, and a lit cell on click.

## Progress log
- 2026-11-06: built. `EBP-06.test.tsx`: 8 passed; `test_a05t39_trust_agreement.py` and the A-05 contract suite: 102 passed. `tsc` clean for EBP-06.

## Decisions made during this task
DEC-2336
