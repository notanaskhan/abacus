---
id: TASK-6607
title: "P-10-T29: AgentRunWorkflow part 1 (run_workflow.py): create, plan, code validation, plan approval wait, DAG dispatch capped at 3, aggregate state, run events, pause and kill switch"
spec: SPEC-647
acceptance_criteria: [AC-W1, AC-W3, AC-W8]
risk_zone: red
status: in-review
branch: s34-p10-t29
worktree: /Users/ayushkbhatia/Accrued/abacus-s34
created: 2026-11-10
updated: 2026-11-10
plan_key: P-10-T29
---

## Objective
A 14-step plan over 5 levels runs at most 3 steps at once, a failing branch leaves the others
running, and a plan with a reserved action is refused before approval.

## Plan (red)
1. `agents/run_plan.py` (new): `PlanStep`, `validate_plan` (reserved action, undeclared write,
   approver lacking the action, read outside `client_scope`, unknown dependency, level order,
   cycle), `cap`, `ready`, `blocked_by_failure`, `aggregate`, `Schedule` (pure, replayable).
2. `agents/run_activities.py` (new): load, record_plan, plan_state, set_state (state, run_events
   on the run's `event_seq`, outbox `agent_run.state_changed`, audit), paused (firm pause,
   engagement pause, `agent_runtime.v2` kill switch), execute_step (one step row, one C17 call for
   tool and compute steps), complete.
3. `agents/run_workflow.py` (new): `AgentRunWorkflow` with `plan_decided`, continue-as-new while
   waiting, DAG dispatch, pause boundary, terminal state. Registered in WORKFLOWS (interactive)
   and ACTIVITIES.
4. GET `/v1/agent-runs/{id}`: the header gains `state` and `state_reason` (no new route).
5. Tests: `tests/unit/agents/test_p10t29_run_plan.py`.
Rollback: nothing starts the workflow until P-10-T33's start route; revert.

## Progress log
- `2026-11-10` — Built; ruff, pyright clean; the app imports and 33 activities register. Tests not
  run (end pass). Partial: a run with no deterministic plan (`inputs.plan`) fails
  `plan_unavailable` — model planning through the harness's `plan_proposed` needs a v2
  capability spec with a prompt and output schema, the first being P-10-T40's
  `runtime.conformance`; model, question, decision and approval steps fail `step_kind_pending`
  until P-10-T32. Replay histories (`agent-run-v1-approved`, `-cancelled-at-plan`) need the
  throwaway Temporal containers of `record_*.py`; recorded at the end pass if Docker is up.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-3205 | Part 1's boundaries: deterministic plans only; pause polling; stalled runs end | no |

- 2026-11-10 (partial closed): the replay history is recorded (`record_agent_run`,
  `agent-run-v1-succeeded.json`, `tests/workflows/test_p10t29_agent_run_replay.py`). Recording it
  found a real defect: Temporal's converter decodes `Any`, not `object`, so `RunFacts.plan`,
  `PlanState.steps` and the `dict[str, object]` activity parameters failed with "Failed decoding
  arguments" and every v2 run would have died at its first activity. They are `JsonObject`
  (`dict[str, Any]`) now; `tests/unit/agents/test_p10t29_payloads.py` round-trips each payload and
  refuses an `object` dict on any run v2 activity. Status: done.
