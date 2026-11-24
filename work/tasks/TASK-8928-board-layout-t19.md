---
id: TASK-8928
title: "F-08-T22: BoardLayout T19: toolbar, filters, policy-bound Run agent on move, variants, Binder and Sheet views; T19a-T19l"
spec: SPEC-000
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: amber
status: in-review
branch: s53-f08t22
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-23
updated: 2026-11-23
plan_key: F-08-T22
---

## Objective
Row acceptance: "T19a to T19l render, the toggle is disabled with 'Not allowed for this engagement type by AI policy' when policy forbids it, and column counts sum to the tiles."

## Done
- board/BoardLayout.tsx (toolbar, filters with Clear, policy-bound run-on-move toggle, navigator, sticky headers, lanes of BoardCanvas, Binder tree table, Sheet slot, empty and loading)
- BoardCanvas: columnWidth, headers, bareCards, onOver
- specimens/t19-board.tsx (a-l placeholder content) registered as t19-board
- tests: board-layout.test.tsx (20) + canvas/card tests green

## Progress log
- `2026-11-23` — Built; parity in the end pass. Amber: the run-on-move gate (ADR P-49) is enforced in the kit; consumers pass the policy.
