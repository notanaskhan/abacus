---
id: TASK-7808
title: "P-09-T08 rest: a run step records its sample records, and engagements, request items and documents resolve them"
spec: SPEC-000  # row (P-09-T08; docs/contracts/agent-runs.md)
acceptance_criteria: [AC-20]  # the row's acceptance, below
risk_zone: red
status: in-review
branch: lo38-p09-t08-samples
worktree: /Users/ayushkbhatia/Accrued/abacus-lo38
created: 2026-11-12
updated: 2026-11-12
plan_key: P-09-T08
---

## Objective
Close P-09-T08's open clause: the step detail's samples were always empty, because the step never recorded its sample records and no module resolved them.

## Plan (red)
- `agents/trace.py`: `step_sample_refs`, the first five row ids from the tool's declared type and rows. The C17 ToolOutcome is unchanged (frozen).
- `agents/run_activities.py`: `StepOutcome.sample_refs`; the step end writes `sample_refs` and `source_ref = accrued` (0751's column grant).
- New `visible()` reads in engagements, requests and evidence (`trace_samples.py`, exported in each api).
- `agents/trace_samples.py` registers the resolvers at `agents.api` import.
- Tests: `tests/unit/agents/test_p09t08_step_sample_refs.py` (4, pass) and `tests/integration/test_p09t08_trace_samples.py` (3, pass: the reader, an outsider, the limit).
- DEC-4806. No migration, no flag, no route. Rollback: revert the commit (the step then writes no samples again).

## Security review (inline, red diff)
- Each read filters `visible()` with the module's own read action, so walls apply. An outsider gets nothing (tested).
- Labels are titles and names the reader can already see; `samples_for` still scrubs TINs.
- A withdrawn version never resolves (ADR-162 §4). That predicate is not covered by a test here.
- `sample_refs` hold ids only. Nothing is logged.

## Progress log
- 2026-11-12: built and tested.
