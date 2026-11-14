---
id: TASK-7935
title: "W-02-T19: session plans and partial failure in agents (plan card fields, edit re-validation, failure ledger, failed_items retry, identity.list_offices, files.list_folders)"
plan_key: W-02-T19
spec: W-02 §3.6, §3.7, §4.2, §4.4
acceptance_criteria: [AC-P1, AC-P3, AC-G3, AC-G4]
risk_zone: red
status: in-review
branch: w02-t19-session-plans
worktree: /Users/ayushkbhatia/Accrued/abacus-s43
created: 2026-11-14
updated: 2026-11-14
---

## Objective
Gathering starts only after the owner approves the plan (P-10, unchanged), an edited plan is
re-validated, and "Retry those 3" reads only the 3 failed binders.

## Plan (red)
- Migration `0872_agent_step_failed_items`: `agent_run_steps.failed_items jsonb NOT NULL DEFAULT
  '[]'` (array, ≤1000) and `retry_scope text` (`all`·`failed_items`); INSERT grant on
  `retry_scope`, UPDATE grant on `failed_items`. Expand-only, RLS unchanged.
- Kernel: `kernel.agent_tools.FailedItem` (references and codes only) and `ONLY_REFS`.
- C17 runtime (additive): `ToolOutcome.failed_items` lifted from an output's `failed_items`;
  `row_fields` skips it.
- Activities: `StepOutcome.failed_items` stored at step end; `execute_step` takes `retry_scope`
  and, for `failed_items`, passes the retried row's ledger to the tool as `only_refs`.
  `plan_rules` factors the plan context so an edit validates like a load.
- Workflow: signal `items_retry` behind `workflow.patched("w02-failed-items")`; a failed step
  re-queues with the scope, a step that succeeded with gaps re-reads beside the plan.
- Commands/routes: `retry_step(..., scope)` (409 `no_failed_items`), retry body
  `RunStepRetryIn`; edit takes `labels` and re-validates (422 with `problems`); `PlanView.reads`
  and `writes` (code's words, approver names); `RunPlanOut.reads/writes`,
  `RunStepV2Out.failed_items/retry_scope`, `RunCountersOut.gaps/failed_items`.
- Tools: `identity.list_offices` (new `identity/agent_tools.py`, `org_structure.list`, new matrix
  row) and `files.list_folders` (`agents/file_tools.py`, `file.propose`, writable by the
  approver); `binders.read` takes `only_refs` and names unreachable binders in its ledger.
  Description prompts `tool.identity.list_offices@v1`, `tool.files.list_folders@v1`;
  `workbench.assistant` allow-list and task scope; `_specs_v2.py`, matrix and client regenerated.
- Tests: `backend/tests/unit/agents/test_w02t19_session_plans.py`.
- Rollback: revert the PR; 0872 downgrade drops the two columns (no reader outside this PR).

## Partial
- Firm-level runs (no engagement) have no Files folders to save to: `files.list_folders` answers
  `firm_folders: unavailable`. "Files › Firm reports › TY2025 season" needs a firm-wide document
  store, which no epic row has built yet.
- The replay history `agent-run-v1-failed-items-retry.json` is recorded at the S43 end pass
  (needs Docker: `abacus_tools.workflows`).

## Progress log
- 2026-11-14: built; tests written, not run (S43 builds first; tests, gates and the security
  review run at the S43 end pass).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-4930 | ledger on the step row, retry scope, items retry beside the plan for a gapped step, plan card fields from declared reads, label-only edits re-validated, `org_structure.list` | no |
