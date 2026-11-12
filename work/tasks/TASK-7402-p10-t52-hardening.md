---
id: TASK-7402
title: "P-10-T52: Hardening: mutation floors (ADR-079) for the new agents, ai_gateway and kernel/realtime files with survivor triage; p95 budgets (plan approve <= 400 ms, stream first byte <= 500 ms); query-count assertions on run reads"
spec: SPEC-647
acceptance_criteria: [AC-1]  # mutation-thresholds.yaml records the floors; p95 budgets hold under x25
risk_zone: red
status: in-review
branch: s38-p10-t52
worktree: /Users/ayushkbhatia/Accrued/abacus-s38
created: 2026-11-12
updated: 2026-11-12
plan_key: P-10-T52
---

## Objective
`backend/mutation-thresholds.yaml` records the floors and the p95 budgets hold under the x25
profile.

## Plan (red)
- Scopes (`abacus_tools.quality.mutation.SCOPES`): `agents/runtime` (run_plan, run_workflow,
  run_activities, run_waits, run_commands, commands, approved_writes, approved_write_workflow,
  proposal_undo, session_turns, harness, tools/runtime) and `kernel/realtime`; `ai_gateway` was a
  scope already. `[tool.mutmut] only_mutate`, `mutation-thresholds.yaml` and
  `coverage-thresholds.yaml` (line and branch) gain both at 0, raised to the first weekly baseline
  after survivor triage (the DEC-2065 rule, DEC-4402).
- Budgets: `abacus_tools/loadtest/p10_budgets.py` (`plan_approve` 400 ms, `stream_first_byte`
  500 ms, `breaches`), checked on staging by the load job.
- Survivor triage (pure rules first): `tests/unit/agents/test_p10t52_hardening.py`: every
  `validate_plan` code and boundary (approval steps, approver holds, level order, cycle, de-dup),
  `cap`, `ready`, `blocked_by_failure`, `aggregate` in its order, the schedule's limit, retry,
  redirect and stop, and the SSE frame at and over 64 KB.
- Query counts: `tests/integration/agent_tests/test_p10t52_run_read_queries.py`: the run, items,
  trace and list reads take the same statements for a 3-step and a 14-step run, within a budget.
- No migration, no flag. Rollback: revert.

## Partial
- The floors are 0 until the first weekly run of the two scopes (mutation-weekly), then raised to
  its baseline with the survivors triaged; the p95 budgets are checked on staging (the x25 load
  job), not here. The statement budgets are set from the first measured run at the end pass.

## Progress log
- `2026-11-12` — Built (S38). Pure triage tests pass (58); lint and types clean; integration
  query counts run at the end pass.
