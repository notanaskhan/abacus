---
id: TASK-8615
title: "Q-04-T352: Tue Sep 19, 2028 dark train: Q-05 flags created default off (record)"
spec: SPEC-711
acceptance_criteria: [AC-29]
risk_zone: amber
status: in-review
branch: q04-t352-dark-train
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-18
updated: 2026-11-18
plan_key: Q-04-T352
---

## Objective
Spec section: docs/plan/epics/Q-04.md (T352 row). The four Q-05 flags exist default-off with no firm flipped inside the window; every later flag event recorded.

## Plan (amber)
1. docs/plan/status/S50-dark-trains.md: the clause table for Q-04-T352, covering T-08-T03's six flags too.

## Progress log
- `2026-11-18` — Built in the S50 sequential stack (DEC-5615). The flags themselves landed in Q-05-T02 (#2287) and T-08-T03 (#2280). Partial: the train dates are calendar events. Gates and tests run once at the S50 end pass (build first, test last).
