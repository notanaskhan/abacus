---
id: TASK-7301
title: "P-10-T43: WorkbenchSessionWorkflow core: user_message and answer signals, inline read-only turns, one child run per write-proposing turn, side queue, client_scope, GET session and POST messages; replay histories"
spec: SPEC-647
acceptance_criteria: [AC-S1, AC-S2, AC-S3, AC-S4, AC-S5]
risk_zone: red
status: in-review
branch: s37-p10-t43
worktree: /Users/ayushkbhatia/Accrued/abacus-s37
created: 2026-11-12
updated: 2026-11-12
plan_key: P-10-T43
---

## Objective
A message typed while a question is open is answered first, a write-proposing turn starts exactly
one child run, and a session that read a walled client is locked for that viewer (omitted when
walled, `locked` when the viewer may not open a client).

## Plan (red)
- **agents** `session_turns.py` (PROTECTED): `open_turn_run` (the person's turn run, `session_id`
  set, `engagement.read` through `get_ref`), `ReadOnlyPorts` (ConversePorts offering only `read`
  and `compute` tools, refusing anything else `not_offered`), `run_session_turn` (queued →
  running → harness → succeeded / needs_input / failed), `plan_steps` (a proposed plan as the
  deterministic plan, the owner as each write's approver), `open_plan_child_run` (exactly one
  child per turn, idempotent). Exported from `agents.api`.
- **workbench**: `session_queue.py` (pure side queue), `session_workflow.py`
  (`WorkbenchSessionWorkflow`, signals `user_message`, `answer`, `close`; child
  `AgentRunWorkflow` abandoned on close), `session_activities.py` (`workbench.session.turn`),
  `sessions.py` (snapshot, post, `open_session`), routes in `sessions_contract.py`; `api.py` gains
  `WORKFLOWS`, `ACTIVITIES`, `SUBSCRIPTIONS`.
- Contract: `SessionMessageIn.answers_seq` (additive); `docs/contracts/agent-runs.md` §9.
- Registries: audit fallback (`session.created`, `session.message_posted`,
  `session.turn_recorded`, `agent_run.turn_recorded`); error `session_locked` (catalogue at the
  end pass).
- No migration (0682's tables and grants suffice), no new flag (`agent_runtime.v2` gates posts).
- Histories: `workbench-session-v1-{read-only, child-run, side-queue}.json` via
  `abacus_tools.workflows.record_s37_runs` (end pass).
- Tests: `tests/unit/workbench/test_p10t43_sessions_core.py`,
  `tests/integration/agent_tests/test_p10t43_sessions.py`, `tests/workflows/test_s37_runs_replay.py`.
- Rollback: revert; the routes go back to 501 and no row changes shape.

## Partial
- A real firm's session needs a capability: until W-03 definitions or T-04-T37's
  `tax.assistant`, a session with no named capability answers a `capability_unavailable` notice
  (synthetic firms talk to `runtime.conformance`).
- The session stream (`…/events`) stays T26's 501.
- Session list, create, rename and delete routes are W-02's; `open_session` is the service.

- End pass (DEC-4317): a turn's plan steps carry the model's arguments, validated against each
  tool's input model before the child run is written (`PlanInvalid`: `invalid_arguments`,
  `tool_not_in_spec`); AgentRunWorkflow's executor then calls each step through C17 after the
  person approves the plan. A propose step declares no approver write (SHL-10 decides it).
- The child run starts through `kernel.dispatch` from the `workbench.session.start_child`
  activity (end pass, DISPATCH-001), not as a Temporal child workflow.

## Progress log
- `2026-11-12` — Built (S37). Import smoke and ruff clean; tests written, not run (end pass);
  histories to record at the end pass.
