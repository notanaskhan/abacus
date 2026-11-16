---
id: TASK-8325
title: "T-07-T26: TXT-04 states in fixture mode"
spec: SPEC-656
acceptance_criteria: [AC-0, AC-12, AC-13, AC-14]
risk_zone: green
status: in-review
branch: t07-t26-txt04-states
worktree: /Users/ayushkbhatia/Accrued/abacus-s47g04
created: 2026-11-16
updated: 2026-11-16
plan_key: T-07-T26
---

## Objective
Spec section: handoff TXT-04.
TXT-04 states in fixture mode.

## Plan (green)
1. `apps/web/src/screens/TXT-04/`: `EstateWorkpapers` (A inventory, B deductions, C computation with the Without DSUE and Illinois cards, D gifts, E extended), `data.ts` (the handoff's rows; totals computed, formatted through `@abacus/ui`'s `count`), tests.
2. Registered in the gallery; `routes/manifest/txt.ts` marks TXT-04 `fixture`.

## Progress log
- `2026-11-16` — Built in the S47 sequential stack. Prettier, eslint, tsc and the screen tests (8) clean while building. Partial: the staging wiring behind `tax.estate_workpapers`, the composed c1 Approve values (L4), the shadow tie-out label, the derivation popovers and the parity tier are not built. Gates and
  tests run once at the S47 end pass (build first, test last).
