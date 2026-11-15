---
id: TASK-8065
title: "W-02-T26: J11 b1–b3, b3-undo and the Workbench sessions suite on staging"
spec: W-02
acceptance_criteria: [W-02 §10 item 1]
risk_zone: green
status: in-review
branch: w02-t26-staging-journeys
worktree: /Users/ayushkbhatia/Accrued/abacus-s45
created: 2026-11-15
updated: 2026-11-15
plan_key: W-02-T26
---

## Objective
The W-02 §10 staging walk as Playwright: J11 b1, b2, b3 and b3-undo, and sessions 1–7 (filters
and search, the locked Copperleaf thread, Margaret's Running 3, a wall closing the stream, the
partial-failure retry, the DF-04 boundary, the grounded Northwind answer), every step through the
journey harness (axe plus INV-1 to INV-5).

## Files
- `apps/web/e2e/journeys/J11-workbench.spec.ts` (the existing file keeps its case; the plan row
  writes it lower-case) — a3 unchanged; a new `J11 b (staging)` block.
- `apps/web/e2e/workbench/sessions.spec.ts` — new.

## Progress log
- `2026-11-15` — Written (DEC-5050). Lint and type-check clean.
- **Partial:** the specs run on the `staging` and `fullstack` projects and are fixme on
  `fixture`. The staging project waits on P-10-T50, so the first green run is the S45/S46 staging
  walk (W-02-T28). The selectors follow the WB-01/02/03 screen contracts and are tuned on that
  first run; any change there is to the selector, never to the asserted copy or figure.
