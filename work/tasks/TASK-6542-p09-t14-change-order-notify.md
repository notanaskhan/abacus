---
id: TASK-6542
title: "P-09-T14 finish: Change order… and Notify in the run pane"
spec: P-09
acceptance_criteria: [server-listed-controls]
risk_zone: green
status: in-review
branch: s33r-p09-t14
worktree: /Users/ayushkbhatia/Accrued/abacus-s33
created: 2026-11-10
updated: 2026-11-10
plan_key: P-09-T14
---

## Objective
Finish the two SHL-13 intents left from TASK-6534 that their targets now allow.

## Build
- Backend: the run header carries the newest plan version's steps (`plan_steps`: key and label;
  none for a metadata reader) through `V2Facts`, `RunHeader`, `RunHeaderOut` (`PlanStepRefOut`).
- `RunPane.tsx`: "Change order…" opens a dialog of the plan's steps in the server's words, each
  moved up or down, confirmed with "yes, run it" (`POST …/plan/edit` with the keys and the
  version seen; an edited plan is a decided one). "Notify ‹first name›" on the blocked decision
  card, only when the card lists `decision.notify` for this person (SHL-11's action, P-04).
- Fixture: run #4127's proposed plan lists frame 3's five workpapers as its steps.
- `make generate` for `plan_steps`.
- Tests: `RunPane.test.tsx` (two cases), `tests/unit/agents/test_s33r_p09t14_plan_steps.py`.

## Left partial
- "Fix in Knowledge →" (KNW-03 at the pack step): a failed run step records no knowledge anchor
  (program and step); the runtime has to store one first (P-10).
- The plan command routes (`…/plan/approve|edit|cancel`) still answer 501 until P-10-T33's
  commands land; the controls refuse with the server's reason meanwhile.

## Progress log
- `2026-11-10` — Built; RunPane tests (18) and the backend test pass. Gates at the end.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-3142 | Change order… edits and runs in one act; the header carries the steps; Notify follows the card | no |
