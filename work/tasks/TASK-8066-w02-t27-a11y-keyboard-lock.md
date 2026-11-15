---
id: TASK-8066
title: "W-02-T27: Workbench accessibility and keyboard lock"
spec: W-02
acceptance_criteria: [W-02 §10]
risk_zone: green
status: in-review
branch: w02-t27-a11y-keyboard
worktree: /Users/ayushkbhatia/Accrued/abacus-s45
created: 2026-11-15
updated: 2026-11-15
plan_key: W-02-T27
---

## Objective
Lock the built Workbench for accessibility: axe under forced colors and reduced motion on the
built routes and every T4/TPL-04 gallery state, and the keyboard suite for QuestionCard, the
context picker, JumpFab and Undo.

## Files
- `apps/web/e2e/workbench/a11y.spec.ts` — the two Workbench routes and the 11 T4/TPL-04 boards:
  axe with `forcedColors: true`, reduced motion with zero running animations.
- `packages/ui/src/agent/chat/w02-keyboard.test.tsx` — QuestionCard Next/Previous across
  "1 of 2"/"2 of 2", one Skip only, Esc without an answer, native-button tab order; ContextPicker
  rows as native `menuitemcheckbox` buttons with `aria-checked`, attach and detach; the Undo toast
  (UNDO_MS = 10 000, DEC-24): Undo calls only the compensating command, and the deferred commit
  runs once at the window's end. JumpFab stays in F-07-T09's `t4-keyboard.test.tsx`.

## Progress log
- `2026-11-15` — Written (DEC-5051). Lint and type-check clean.
- **Partial:** the Tier C parity report for the 22 artboards, with its masks, and moving WB-01,
  WB-02 and WB-03 to `locked` in the manifest need the parity run (CI, `e2e/parity`). That run is
  the S45 end pass; the manifest flip follows it. The Space key on a picker row is a platform
  guarantee of the native button, so the unit suite asserts the element, not the key.
