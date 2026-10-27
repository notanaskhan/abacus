---
id: TASK-1423
title: "C6 v1 stub: the run summary of ADR-169 §4 and the v1 freeze (Q-02-T45)"
spec: SPEC-318
acceptance_criteria: [AC-1, AC-2, AC-7]
risk_zone: red
status: in-review
epic: Q-02
plan_key: Q-02-T45
branch: s11-q02-t45
created: 2026-10-27
updated: 2026-10-27
---

## Objective
Q-02-T45 is conditional on the C6 v1 owner change. Ayush approved it on 2026-10-27; it is recorded
as DEC-595. C6 v1's routes were already live (TASK-5000, TASK-5001, TASK-5002, TASK-1287), so the
"stub" here is the remaining v1 shape of ADR-169 §4 on the live run summary, then the v1 freeze.

## Plan
- `agents/runs.py`: `RunSummary` gains `state_reason`, `outcome`, `stage`, `record_sha256` and
  `record_persisted_at` (defaults keep the old constructor shape). The list and the view read the
  run records and the proposals' states in two RLS-scoped queries. The trace-v1 export drops these
  fields, so its canonical bytes and digests do not change.
- `agents/runs_routes.py`: `AgentRunOut` gains the same fields, all `internal`.
- Contract: `docs/contracts/agent-runs.md` and the register row record v1 frozen; the snapshot is
  `backend/tests/contracts/c06_agent_runs/v1.json` (`abacus_tools.contracts`).
- Consumer tests for G-02 and A-01: `backend/tests/contracts/c06_agent_runs/test_c06_consumers.py`.
- The Q-02-T46 strict xfail on the C6 v1 summary is removed.
- Decisions: DEC-595 (owner change), DEC-596 (the summary as frozen).
- No migration, no route, no matrix change. Rollback: revert the commit (the fields are additive).

## Progress log
- 2026-10-27: built in line at Ayush's request (build first, one check at the end).
