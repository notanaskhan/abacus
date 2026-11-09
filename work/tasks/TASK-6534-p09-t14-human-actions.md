---
id: TASK-6534
title: "P-09-T14: human-action intents on C6 v2"
spec: SPEC-648
screens: [SHL-13]
risk_zone: green
status: in-review
branch: s33-p09-t14
worktree: /Users/ayushkbhatia/Accrued/abacus-s33
created: 2026-11-09
updated: 2026-11-09
plan_key: P-09-T14
---

## Objective
Each control renders only when the server lists its action, Sign off run stays disabled before a
terminal state, refusals show the server's reason, and no control is offered in an agent context.

## Build
- `domain/agents/RunPane.tsx`: an acts context (`can` = `agent_runtime.v2` on and the action in
  the run view's `allowed_actions`; `refused` toasts the server's code or detail; `done` reads
  the view and feed again). Bound: Run (`agent_run.start`, `POST /v1/engagements/{id}/runs`),
  "yes, run it" (`approve_plan` with the plan's `expected_version`), the question card (typed
  answer on Enter, Esc skips, 1-9 picks a numbered option; `answer`/`skip`), Retry on a failed
  step (`control`), the composer steer (`redirect`, while the run is live), Sign off run (O3
  confirm listing open issues and decisions; disabled until terminal; `sign-off` with the
  acknowledged ids), thumbs (`agent_feedback.create`). Nothing optimistic. The disabled Rerun and
  Follow up stubs are gone.
- Backend: `RUN_ACTIONS` gains `agent_run.start` and `agent_feedback.create`; the run header gains
  `plan_version` (the plan's newest version) through `V2Facts`, `RunHeader`, `RunHeaderOut`.
- Fixtures: SHL-13's #4127 runs list Marcus's actions (`PERSON_RUN_ACTIONS`); the plan run
  carries `plan_version` 1. RunPane tests follow the new contract (controls only when listed and
  the flag is on; with it off none).
- Tests: `RunPane.test.tsx` (updated and new cases), `tests/unit/agents/test_p09t14_run_actions.py`.

## Progress log
- `2026-11-09` — Built; tests written, not run (end pass); `make generate` pending for
  `plan_version`. Partial: "Change order…" stays disabled (the plan's step editor needs the plan's
  steps, which the view does not carry yet); Notify (P-04) and Fix in Knowledge (KNW-03 anchor)
  wait on their targets' routes; the v2 command routes still answer 501, so the controls act only
  once P-10's services land.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-3134 | Dock controls render from the server's listed actions and the v2 flag; nothing optimistic | no |
