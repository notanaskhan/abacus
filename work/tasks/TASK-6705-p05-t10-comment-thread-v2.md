---
id: TASK-6705
title: "P-05-T10: C-29 CommentThread v2 (popover 420, dock tab 360, drawer tab 480), Composer and MentionPicker; SHL-18 on AUD-09 rows; scenarios a, b, b2, c, d, e, f"
spec: SPEC-650
acceptance_criteria: [AC-1, AC-5, AC-6, AC-11, AC-15, AC-16]
risk_zone: green
status: in-review
branch: s35-p05-t10
worktree: /Users/ayushkbhatia/Accrued/abacus-s35
created: 2026-11-10
updated: 2026-11-10
plan_key: P-05-T10
---

## Objective
SHL-18 a, b, b2, c and e render from live data, d and f render in the gallery from fixtures, the menu offers Correct… and Redact… and never Edit or Delete, and axe is clean in every state.

## Plan
1. `apps/web/src/domain/collaboration/` (new L3): `CommentThread.tsx` (`CommentThreadView` in the
   three variants, `LiveCommentThread` on the generated client), `CommentComposer.tsx`,
   `MentionPicker.tsx` (combobox + listbox, aria-activedescendant, greyed `aria-disabled` rows),
   `CommentChip.tsx` (row chip opening the O1 popover), `mentions.ts`, `copy.ts` (P-05 §5.5).
2. `screens/SHL-18/` and `fixtures/scenarios/SHL-18.ts`: the seven artboards; fixture thread writes
   answer the state's thread.
3. AUD-09: a comment chip on each Exceptions row behind `collaboration.v2`, anchored to the paper
   (`workpaper`, `{sheet: "Exceptions", row}`, P-05-T09's provider).
4. Tests: `screens/SHL-18/SHL-18.test.tsx`. axe runs in the visual project at the end pass.

## Partial
- The AUD-09 chip shows no count yet (counts come from `POST /v1/comment-threads/counts`; wiring the
  batch read into the grid is left with P-05-T12's seed check).
- The thread's "Convert to to-do…" opens the host's SHL-17 (no SHL-17 front end is built yet: the
  to-do drawer is not an S35 row).

## Progress log
- `2026-11-10` — Built; tests written, not run (end pass).
