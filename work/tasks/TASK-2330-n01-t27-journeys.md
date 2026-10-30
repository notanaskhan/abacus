---
id: TASK-2330
title: N-01-T27 inbox and files journey legs
spec: SPEC-380
acceptance_criteria: []
risk_zone: green
status: in-review
epic: N-01
plan_key: N-01-T27
branch: s18-n01-t27
worktree: /Users/ayushkbhatia/Accrued/abacus-s18
created: 2026-10-30
updated: 2026-10-30
---

## Objective
Journey legs for INB-01, INB-02 and FIL-01 in fixture and full-stack modes; independent seed footing
for N-01-T11.

## Plan
- `e2e/journeys/N01-inbox-files.spec.ts`; `src/fixtures/seed/__tests__/n01t27-inbox.foot.test.ts`;
  DEC-1376.

## Progress log
- `2026-10-30` — written; the footing test runs (2 pass); the Playwright legs run in `make e2e`
  (fixture) at the end review and on staging after the deploy. `[skip ci]`.

## Handoff
- **Current state:** written, PR open, held for the S18 batch.
- **Exact next step:** N-01-T28 parity and accessibility.
