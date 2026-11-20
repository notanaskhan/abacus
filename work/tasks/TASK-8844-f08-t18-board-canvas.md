---
id: TASK-8844
title: "F-08-T18: BoardCanvas engine on dnd-kit"
spec: SPEC-660
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: amber
status: in-review
branch: s52-f08t18
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-20
updated: 2026-11-20
plan_key: F-08-T18
---

## Objective
A guarded result springs back in 240 ms with 'Moving to Complete needs a reviewer sign-off. Open sign-off...', and every drag has a keyboard and menu equivalent.

## Done
- packages/ui/src/board (types, BoardCanvas, index) exported from @abacus/ui
- board-canvas.test.tsx
- DEC-5843

## Progress log
- `2026-11-20` — Plan (amber): L2 kit only; no backend; rollback = revert. vitest at the end pass.
