---
id: TASK-7916
title: I-02-T18 Independent AC tests for practice.today (I-02-T10)
plan_key: I-02-T18
spec: SPEC-654
acceptance_criteria: [AC-3.1, AC-3.2, AC-3.4, AC-3.11]  # I-COUNT over random gate sets; footing; order; business day
risk_zone: amber
status: in-review
branch: i02-t18-independent
worktree: /Users/ayushkbhatia/Accrued/abacus-s42
created: 2026-11-13
updated: 2026-11-13
---

## Objective
ADR-078 suite for the Today read model: count equality with the gates (property test), group
footing, Needs-you-first and card order, the next business day across a holiday, no model text in
any count, the forced-build limit.

## Plan
- Test: `backend/tests/unit/practice/test_i02t18_independent.py`.

## Partial
- Solo edition (one session). Daniel/Margaret golden comparisons against HOME-01/02 on the live
  seed and the walls (Lena Park, Grace Holloway) stay in the journey suites (I-02-T21).

## Progress log
- 2026-11-13: written, not run (S42 end pass).
