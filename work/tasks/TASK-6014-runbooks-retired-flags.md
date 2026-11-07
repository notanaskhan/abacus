---
id: TASK-6014
title: "T-03-T18 Runbooks read the retired flags as retired: RB-62, RB-61 and the responder shadow plan"
spec: SPEC-000  # row (T-03-T18)
acceptance_criteria: [AC-1]
risk_zone: green
status: in-review
epic: T-03
plan_key: T-03-T18
branch: s29m-runbooks-flags
worktree: /Users/ayushkbhatia/Accrued/abacus-s29
created: 2026-11-08
updated: 2026-11-08
---

## Objective
The flag retirements (#1384, #1387) merged on 2026-11-08, ahead of the Dec 16 batch the runbooks named. RB-62 and RB-61 still told the operator to turn retired flags off for a rollback.

## Plan
RB-62: kill switch and section 5 read the tax_returns entitlement (DEC-2605). RB-61: kill switches, the agent-off row, Contain and the flip rollback read the responder stage (DEC-2602) and a revert of #1384. Shadow plan: the opt-in row drops the flag. Docs only; rollback: revert.

## Progress log
- 2026-11-08: built. Docs only; no tests touched.

## Decisions made during this task
None.
