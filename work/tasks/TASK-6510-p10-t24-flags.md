---
id: TASK-6510
title: "P-10-T24: flags agent_runtime.v2, realtime.sse, engagement_run.enabled"
spec: SPEC-647
acceptance_criteria: [AC-G1]  # the row's acceptance (AC-flags)
risk_zone: red
status: in-review
branch: s33-p10-t24
worktree: /Users/ayushkbhatia/Accrued/abacus-s33
created: 2026-11-09
updated: 2026-11-09
plan_key: P-10-T24
---

## Objective
P-10's three flags exist, boolean and default off, and the C6 v2 stubs answer 404 while off.

## Plan (red)
1. `feature-flags/agents.yaml`: the three flags (DEC-137 override; the plan's Thu Jan 27, 2028
   train and Apr 26, 2028 expiry map to the build clock, renewal calendared before expiry).
2. `agents/runs_v2_contract.py`: every route checks its flag first (`realtime.sse` for the run
   stream, `engagement_run.enabled` for the engagement run, `agent_runtime.v2` for the rest),
   then 501 until its task.
Rollback: revert.

## Progress log
- `2026-11-09` — Built; not run (end pass). P-10-T26 and T27 read `realtime.sse` for their streams.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-3110 | P-10's flags and which routes each gates | no |
