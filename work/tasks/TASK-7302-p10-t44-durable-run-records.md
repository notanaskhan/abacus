---
id: TASK-7302
title: "P-10-T44: Durable run records: frozen trace v2 exports behind P-09's handlers, retention class, run_events prune at 30 days, hash-chain coverage, A-07 archive hook"
spec: SPEC-647
acceptance_criteria: [AC-T1, AC-H4]  # the spec's section ids (validate_docs reads AC-<n>)
risk_zone: red
status: in-review
branch: s37-p10-t44
worktree: /Users/ayushkbhatia/Accrued/abacus-s37
created: 2026-11-12
updated: 2026-11-12
plan_key: P-10-T44
---

## Objective
A run adopted 90 days earlier still exports with its tool calls through P-09's export route after
`run_events` are pruned, and the export re-renders byte-identical.

## Plan (red)
- Migration 0820 `agent_run_traces` (insert-only, forced RLS, column grants; record class
  `agent_run_records`): the frozen export body per run, projection and version, with
  `source_sha256` (the durable rows' fingerprint).
- `agents/trace_records.py` (PROTECTED): `source_fingerprint`, `frozen_body` (P-09-T11's
  `export_trace` answers the frozen bytes while the rows hold still, else freezes a new version),
  `adopted_run_traces` (A-07's archive hook), `prune_firm` and `agents.run_events.prune`.
- `agents/run_events_prune_workflow.py`: `RunEventsPruneWorkflow`, daily Schedule
  `run_events_prune:platform` (`agents.api.SCHEDULES`), batch class.
- No new route (exports stay `POST /v1/agent-runs/{id}/trace-exports`, `run_trace.export`, fresh
  MFA). Audit `agent_run.trace_frozen` (`Ref(sha256, version)`: the hash chain covers each
  version), `run_events.pruned`.
- Tests: `tests/unit/agents/test_p10t44_run_records.py`,
  `tests/integration/agent_tests/test_p10t44_run_records.py`; the P-09-T11 unit test gains a
  double for the new dependency. History `run-events-prune-v1.json`.
- Rollback: revert and drop 0820 (nothing reads it but the export).

## Partial
- The PDF export waits on C11's `run_trace_v1` template (P-09-T11 still answers JSON only); the
  frozen record keeps the JSON body byte-identical.
- A-07's binder and seal do not call `adopted_run_traces` yet: adding run-trace leaves to
  `seal_leaves` would change the seal of an archive verified after a later freeze. The hook is
  ready; wiring it is A-07's packaging change.

## Progress log
- `2026-11-12` — Built (S37). Import smoke and ruff clean; tests written, not run (end pass).
