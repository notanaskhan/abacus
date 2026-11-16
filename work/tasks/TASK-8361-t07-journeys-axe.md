---
id: TASK-8361
title: "T-07-T30: J07 and J19 step 4 green in the fixture project; axe on every TXT artboard (T-07-T31)"
spec: SPEC-656
acceptance_criteria: [AC-1]
risk_zone: green
status: in-review
branch: t07-journeys-axe
worktree: /Users/ayushkbhatia/Accrued/abacus-s47g04
created: 2026-11-16
updated: 2026-11-16
plan_key: T-07-T30
---

## Objective
Spec section: T-07-T30 J07/J19; T-07-T31 axe on every TXT artboard. J07 and J19 step 4 green in the fixture project; axe on every TXT artboard (T-07-T31).

## Plan (green)
1. Register TXT-01 (a–d, d1–d3) and TXT-02 (a–e, f1) in the gallery on their fixture scenarios (the TXP-12 way); J07 steps 1–3 had nothing to open.
2. J19: step 4 on TXT-04 a and c; 5–8 stay fixme with owners (no L4 artboard).
3. `e2e/journeys/T07-txt-artboards.spec.ts`: every TXT-01 to TXT-04 artboard as a harness step (axe incl. forced colours, INV-1 to INV-5).
4. Fix the axe findings: TXT-01's highlight swatch gets `role=img`; TXT-02's struck prior values and the f1 placeholder move from ink-4 to ink-3 (the AA ladder, DEC-11).

## Progress log
- `2026-11-16` — Built in the S47 sequential stack. Playwright fixture project: J07 3/3, J19 4 passed + 4 fixme (owners), TXT artboards 4/4 (11 passed, under the test lock); TXT vitest 18 passed; tsc and eslint clean. Not done: Tier C parity (no TXT crops in the 2026-10-21 baselines), Tier D geometry, keyboard suites for clause chips, calc tree and release confirm, reduced-motion runs; staging and full-stack J07 (fixme, T-07 live swaps). Gates and
  tests run once at the S47 end pass (build first, test last).
