---
id: TASK-6306
title: P-09-T09 SHL-13 run pane in the T2 dock
spec: SPEC-648  # Stories 1.1 to 1.3; handoff SHL-13
acceptance_criteria: [AC-1]
risk_zone: green
status: in-progress
epic: P-09
plan_key: P-09-T09
branch: s32-p09-t09
worktree: /Users/ayushkbhatia/Accrued/abacus-s32
created: 2026-11-09
updated: 2026-11-09
---

## Objective
SHL-13: one run in the 330 dock, behind `agent_dock.enabled`, opened with `?dock=agent&run=`.

## Plan
- New `domain/agents/RunPane.tsx`: header (live dot, "Agent", "Sign off run" disabled until the
  run ends and the viewer holds `agent_run.sign_off`), projection strip from `levels`, thread by
  `session_kind` (bubble, narration through AgentBlocks, tool cards in six states, level row,
  decision card with "Open decision", ask/plan cards, failed card with Retry, run card),
  composer (disabled until P-09-T14 binds P-10's run commands), not-allowed state.
- `AgentDock`: the pane when the flag is on and a run is open; "Open run" on each card; flag off
  stays the v1 run list (DF-04 below it).
- `?run=` through `routes/firm/audits.tsx` and AUD-02.
- Fixtures: #4127 at 9:41 with five levels and the frame 3/4 thread; frames 6 (9:58 failed) and 7
  (completed) in `fixtures/seed/agent-dock.ts`; handlers serve them.
- Tests: `domain/agents/RunPane.test.tsx`.

## Progress log
- `2026-11-09` — Built; not type-checked or run (no node_modules in the worktree; the API client
  regenerates at the end pass, which the widened `RunItemOut.kind` needs).
- Partial: frames 1 (idle "Run"), 2 (plan proposed chips), 5 (ask card answering), 8 (close
  RunCard picker "Run 2 ⌄"), 9 and 10 (R2 sheet strip, thumbs-down reason picker) are not drawn
  as fixtures; every human action (Sign off, answers, Retry, composer) waits for P-09-T14; rail
  sync takes a `selectedRef`/`onSelectRef` but AUD-02 does not pass the DockSelectionStore yet
  (P-09-T13). Narration figures are text, not `{fact}` tokens: C6 items carry no fact registry.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-3006 | Human actions render disabled until T14; level labels; tool item fields | no |
- `2026-11-09` — S32 end pass: gates, unit, contract, S32 integration and web suites run; fixes folded into the end-pass PR. Status partial.
- `2026-11-09` — Partials round (branch s32p-p09-t09, DEC-3023): frames 1 (idle "Run"), 2 (plan
  proposed, chips), 5 (question card with options) and 8 (CLS-02 close run card, task rows,
  "Run 2 ⌄") drawn from new fixture runs; the collapsed agents strip (revision 1) from the dock's
  run list; finished tool cards get Rerun/Follow up (disabled until P-09-T14) and thumbs with the
  reason picker (revision 4). The dock's run-list query moved above its early return. Tests added
  in `RunPane.test.tsx`. Still open: frame 9's trigger line and step card, frame 10 submit
  (feedback route 501), human actions (P-09-T14), rail sync (P-09-T13), fact tokens.
