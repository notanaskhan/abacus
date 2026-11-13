---
id: TASK-7727
title: F-07-T12 TPL-13 fixtures and specimen
plan_key: F-07-T12
spec: SPEC-652
acceptance_criteria: [AC-6]  # Sep 15 = 8 × 1065 + 3 × 1120-S + 2 envelopes = 13; Copperleaf the only overdue; seven artboards render, risk from data
risk_zone: green
status: in-review
branch: f07-t12-tpl13-specimen
worktree: /Users/ayushkbhatia/Accrued/abacus-s41
created: 2026-11-13
updated: 2026-11-13
---

## Objective
TPL-13 fixtures and specimen a, a2 (a′), b–f for Grace Holloway: September 2026 cells exact,
Sep 15 = 13 items, Denver filter, Calloway Trust postponed to Nov 2, empty filter.

## Plan
- `packages/ui/src/specimens/tpl13-data.ts`, `tpl13.tsx`, `tpl13.test.tsx` (new);
  `specimens/index.ts` registration.
- Rollback: revert.

## Partial
- The postponed item's relief-notice citation is C21 data (T-08); its popover shows no rule here.
- Tier B lock and visual parity are F-07-T22's.

## Progress log
- 2026-11-13: built; eslint and tsc clean; tests written, not run.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-4730 | unnamed 1065s, Denver set, empty filter, rule text only where given | no |
