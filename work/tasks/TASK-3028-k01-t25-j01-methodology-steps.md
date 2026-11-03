---
id: TASK-3028
title: K-01-T25 J01 methodology steps and KNW-02 journey
spec: SPEC-000  # K-01-T25 row; K-01 §3.3, §3.5 (KNW-02, KNW-03)
acceptance_criteria: [AC-1]
risk_zone: green
status: in-review
epic: K-01
plan_key: K-01-T25
branch: s25-k01-t25 (stacked on s25-a04-t21)
worktree: /Users/ayushkbhatia/Accrued/abacus-s25
created: 2026-11-02
updated: 2026-11-02
---

## Objective
"j01 steps 5 and 6 pass full-stack with INV-1 to INV-5 asserted, and KNW-02a-f are locked at
Tier C."

## Built
- `apps/web/e2e/journeys/knw-02-import-review.spec.ts` (a–f); J01 5w replaced its fixme with the
  KNW-02 walk; `docs/screens/KNW-02.md` with the parity locks.

## Progress log
- 2026-11-02: built; runs in the end pass (fixture project). Full stack waits for the methodology
  slice in E0 (`test.fixme` names it).

## Decisions made during this task
DEC-2075.
