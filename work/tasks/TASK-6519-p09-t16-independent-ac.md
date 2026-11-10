---
id: TASK-6519
title: "P-09-T16: independent AC tests for P-09's red work (personas, blocks, export)"
spec: SPEC-648
acceptance_criteria: [AC-1, AC-3, AC-6]
risk_zone: red
status: in-review
branch: s33-p09-t16
worktree: /Users/ayushkbhatia/Accrued/abacus-s33
created: 2026-11-09
updated: 2026-11-09
plan_key: P-09-T16
---

## Objective
Suites that fail under a mutation that removes the rule each covers.

## Plan
`tests/unit/agents/test_p09t16_independent_ac.py` (persona matrix for `agent_run.read`,
`run_content.read`, `run_trace.export`; fresh MFA, not-offshore, independence; AgentBlocks
refusals) beside `test_p09t11_trace_export.py` (export determinism and the audit event). The
ADR-078 split is void under the solo edition (AMENDMENT-solo item 3): written from SPEC-648.

## Progress log
- `2026-11-09` — Written, not run (end pass). Partial: the TRI-masking-offshore and 90-day-old-run
  export cases need a DB fixture; they join the end pass's integration suite if time allows.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-3119 | Which P-09 rules the independent suite pins | no |
