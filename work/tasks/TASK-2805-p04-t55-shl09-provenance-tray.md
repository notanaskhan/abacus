---
id: TASK-2805
title: P-04-T55 SHL-09 field provenance tray, frames a–f
spec: SPEC-000  # P-04-T55 row and docs/screens/SHL-09.md
acceptance_criteria: [AC-1]
risk_zone: green
status: in-review
epic: P-04
plan_key: P-04-T55
branch: s23-p04-t55
worktree: /Users/ayushkbhatia/Accrued/abacus-s23
created: 2026-11-01
updated: 2026-11-01
---

## Objective
- **[AC-1]** "SHL-09a-f match their artboards at Tier C, and SHL-09e keeps Sign off field
  disabled with Add a reference before signing off."

## Plan
Screen contract `docs/screens/SHL-09.md`; `screens/SHL-09/{index.tsx,copy.ts,scenarios.ts}` over
P-04-T35's C3 field routes; scenarios from P-04-T34's frames with stateful writes; gallery and
manifest (fixture). Tests `SHL-09.test.tsx` (a–f, e's disabled sign-off, add reference, edit note).
Rollback: revert.

## Progress log
- `2026-11-01` — built; tsc, eslint, prettier clean. Tests and Tier C parity at the S23 end review.

## Decisions made during this task
DEC-1854.
