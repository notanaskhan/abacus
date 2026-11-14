---
id: TASK-8027
title: "T-05-T73 part 1: the M18 entity returns flip plan (RB-84)"
spec: SPEC-651
acceptance_criteria: []
risk_zone: green
status: in-review
branch: t05-t73-flip-plan
worktree: /Users/ayushkbhatia/Accrued/abacus-s44
created: 2026-11-14
updated: 2026-11-14
plan_key: T-05-T73
---

## Objective
`docs/runbooks/entity-returns-flip.md`: shadow with CCH reconciliation on every return, rollback by flags (workbooks persist), both founders' approvals, flag renewals for T-05's and T-04's three flags, the capacity ledger and the hand-off notes.

## Progress log
- `2026-11-14` — Part 1 written as RB-84.
- **Partial.** Row acceptance ("Both founders approve the flip plan and no T-05 or T-04 flag expires inside the window") is human:
  - the approvals;
  - the renewals themselves (protected flag edits, with the solo-calendar dates chosen when the flip is scheduled).
  - The gate's CPA sign-off (T-05-T70) is a vendor row that never started. The delta pen test (T-05-T72) is deferred (DEC-1389). The J08 e2e (T-05-T68) waits on T-05-T66's remaining screens.
