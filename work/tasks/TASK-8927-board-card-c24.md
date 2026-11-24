---
id: TASK-8927
title: "F-08-T21: BoardCard C-24, column headers, swimlane bands, DoneCount, four overlays and the 280 navigator"
spec: SPEC-000
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: green
status: in-review
branch: s53-f08t21
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-23
updated: 2026-11-23
plan_key: F-08-T21
---

## Objective
Row acceptance: "Cards show owner chip <= 20, metrics, AgentProgress and P/R slots, the four overlays differ without colour fills, and the navigator collapses to a 44 rail."

## Done
- board/BoardCard.tsx: BoardCard (variants, looks, overlays), BoardColumnHeader, BoardLane, BoardNavigator, C-26 AgentProgress; exported from the board kit
- kit gallery specimen c24-board-card
- tests: board-card.test.tsx (10) + canvas tests green

## Progress log
- `2026-11-23` — Built; parity in the end pass.
