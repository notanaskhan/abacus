---
id: TASK-6538
title: "A-07-T32 finish: letters name their drafting run; #4231 after a burst"
spec: SPEC-644  # A-07 §6 and §4.5 (docs/plan/epics/A-07.md)
acceptance_criteria: [AC-1]  # every Agent draft is attributed and traceable to its run
risk_zone: red
status: in-review
branch: s33r-a07-t32
worktree: /Users/ayushkbhatia/Accrued/abacus-s33
created: 2026-11-10
updated: 2026-11-10
plan_key: A-07-T32
---

## Objective
A draft the Agent composed names its run (`drafted_by_run_id`, A-07 §6), and the readiness check
(#4231) runs 60 s after a burst of checklist changes (A-07 §4.5).

## Plan (red)
- `agents/code_runs.py`: `begin_code_run`, `finish_code_run`, `fail_code_run` (record_code_run is
  now begin + finish in one unit of work); exported from `agents.api`.
- `assurance/rep_letters.py` and `governance_comms.py`: `start_letter` / `regenerate` take an
  optional `drafted_by_run_id`, written on the version row (0668's column, already granted).
- `assurance/agent_capabilities.py`: `letter_compose` opens its run first, drafts under it, then
  finishes it; a refused draft ends it failed with the refusal's code. `completion_readiness`'s
  body is shared with `record_readiness_as_partner` (as the EP via Agent).
- `assurance/completion_readiness_workflow.py`: `CompletionReadinessWorkflow` (`interactive`):
  60 s wait, then the readiness activity. The checklist projector starts it when a burst changes
  rows (`USE_EXISTING` while it waits; `ALLOW_DUPLICATE` after).
- Recorder `abacus_tools/workflows/record_completion_readiness.py` (history recorded in the end
  pass); tests `tests/unit/assurance/test_s33r_a07t32_runs.py` and the replay test.
Rollback: revert; the column stays null, no readiness run starts by itself.

## Progress log
- `2026-11-10` — Built; tests written, not run (end pass). The burst window counts from its first
  change (Temporal has no "restart the timer" without a signal; a second change inside the window
  attaches).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-3138 | Code runs open before their drafts; #4231 debounces by workflow id | no (ADR-090) |
