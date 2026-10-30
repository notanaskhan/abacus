---
id: TASK-2331
title: N-01-T28 parity and accessibility for INB-01, INB-02, FIL-01
spec: SPEC-380
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: green
status: in-review
epic: N-01
plan_key: N-01-T28
branch: s18-n01-t28
worktree: /Users/ayushkbhatia/Accrued/abacus-s18
created: 2026-10-30
updated: 2026-10-30
---

## Objective
Parity tiers for the 25 artboards of INB-01, INB-02 and FIL-01, axe on every artboard, and keyboard
suites for the inbox list, the INB-02 sheet, the FIL-01 tree and the reveal control.

## Plan
- `## Parity` tables in `docs/screens/INB-01.md`, `INB-02.md`, `FIL-01.md`.
- `e2e/screens/INB-01.spec.ts`, `INB-02.spec.ts`, `FIL-01.spec.ts` (BND-02 pattern); DEC-1377.

## Progress log
- `2026-10-30` — written; prettier and eslint clean; the Playwright specs run in the fixture project
  at the end review; the parity report run is a human/end-review step. `[skip ci]`.

## Handoff
- **Current state:** written, PR open, held for the S18 batch.
- **Exact next step:** S18 end review (security, tests, gates).
