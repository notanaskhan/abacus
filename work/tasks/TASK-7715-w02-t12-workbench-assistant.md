---
id: TASK-7715
title: W-02-T12 Capability workbench.assistant v1 (spec v2, prompt, AssistantTurn, trajectories)
plan_key: W-02-T12
spec: SPEC-653
acceptance_criteria: [AC-A1, AC-A2, AC-A3]
risk_zone: red
status: in-review
branch: w02-t12-workbench-assistant
worktree: /Users/ayushkbhatia/Accrued/abacus-s41
created: 2026-11-13
updated: 2026-11-13
---

## Objective
The Workbench's assistant capability: spec v2, prompt, turn schema and code's turn check, with
its frozen suite registered.

## Plan (red)
- `agents/specs/v2/workbench.assistant.yaml` + regenerated `_specs_v2.py`; prompt
  `ai_gateway/prompts/workbench.assistant/v1.txt`; `workbench/assistant.py`; `_eval_suites.py`
  regenerated; W-02-T11's two tool files renamed to `agent_tools.py` (codegen discovery).
- Tests: `backend/tests/unit/workbench/test_w02t12_workbench_assistant.py`; the fast subset of
  `evals/workbench_assistant` on the fake model in the end pass.
- Rollback: revert; no session names the capability until the session binding (W-02-T15+).

## Partial
- The session turn loop that runs this capability for a Workbench session (posting a message on
  a firm-level session, trajectories recorded by P-10's runtime) is P-10-T43's `post_message`
  with a capability ref; blank Workbench sessions name no capability yet (binding the assistant
  to blank sessions is W-02-T15's).
- `identity.list_offices` and `files.list_folders` are not registered tools: they are W-02-T19's
  red tools (with the writable-by-approver filter), a later row; left out of the spec.

## Progress log
- 2026-11-13: spec compiled; suites regenerated; tests written, not run.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-4718 | the spec, turn schema and check | no |
