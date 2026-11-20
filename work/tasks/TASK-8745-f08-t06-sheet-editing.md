---
id: TASK-8745
title: "F-08-T06: Sheet cell editing, keyboard grid model (role=grid) and signed-off row locks"
spec: SPEC-000
acceptance_criteria: []
risk_zone: amber
status: in-review
branch: s51-f08t06
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-19
updated: 2026-11-19
plan_key: F-08-T06
---

## Objective
Enter/F2, Esc, Tab/Enter and arrow keys work under role=grid, and locked rows refuse typing, paste, fill and Delete with the final tooltip copy (T18; TPL-20).

## Plan (amber)
1. `packages/ui/src/sheet/types.ts`: column options, cell raw value, row version, `SheetCellEdit`, `SheetEditConflict`, `onCellEdit`.
2. `SheetGrid.tsx`: roving focus (arrows, Home/End, PageUp/PageDown by 10, one tabbable cell); Enter/F2/typing edits, Esc cancels, Enter/Tab commit through `onCellEdit` with the row version; Delete/Backspace clear; Ctrl/Cmd+D fills down; locked rows are aria-readonly with `LOCKED_TOOLTIP` and refuse typing, paste, fill, Delete and Backspace, announced in a polite live region; a 409/412 rejection shows `Changed by <name> — reload`.
3. Tests: `SheetGrid.editing.test.tsx` (7). `SheetGrid.test.tsx`: `afterEach(cleanup)` (jsdom, no globals) and a 560 px clientHeight stub for the virtualised band test (jsdom has no layout); no assertion changed.
4. Rollback: revert the PR; no backend, no migration.

## Progress log
- `2026-11-19` — Built; sheet tests 12 passed, tsc and eslint clean. Gates and tests run once at the S51 end pass (build first, test last).
