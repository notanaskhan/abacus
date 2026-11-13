---
id: TASK-7723
title: P-02-T13 search load test, plan guard, query count and lag alarm
plan_key: P-02-T13
spec: SPEC-000  # docs/contracts/c15-search.md; ADR-241
acceptance_criteria: []
risk_zone: amber
status: in-review
branch: p02-t13-search-load
worktree: /Users/ayushkbhatia/Accrued/abacus-s41
created: 2026-11-13
updated: 2026-11-13
---

## Objective
`abacus_tools/loadtest/search.py` at 1M documents per tenant, the EXPLAIN plan guard and the
query-count assertion in CI, the indexer lag metric and its alarm. Targets: first-group p95
≤ 250 ms at 1M documents, relay lag p95 ≤ 5 s under the December profile.

## Plan (amber)
- `backend/src/abacus_tools/loadtest/search.py` (new: seed, check, clean) and
  `loadtest/scenarios/search_december.yaml` (new).
- `backend/src/abacus/modules/platform/search/indexer.py`: `record_lag` on the relay path only.
- `backend/src/abacus/modules/audit_trail/activity_reviewed.py`: `search_index.loadtest_seeded`.
- `infra/envs/staging/search.tf` (new), `variables.tf` (`search_index_lag_p95_ms`).
- Tests: `tests/integration/test_p02t13_search_plan_guard.py`,
  `tests/unit/tools/test_p02t13_search_load.py`, `infra/tests/test_search_index_lag.py`.
- Rollback: revert; the alarm and filter go with the next apply; the seeded rows are removed by
  `search clean`.

## Partial
- The 1M run itself is manual on a local stack (`seed`, `run --profile search_december`,
  `check`); its numbers are recorded in RB-31 when run. Not run in this session.
- The plan guard proves index capability (sequential scans priced out), not the planner's choice
  on a 1M table; the load run is that proof.
- The relay lag needs writes during the run to have samples; `search_december` carries request
  reads only, so lag samples come from the scenario loader or the firm's own work in the window.

## Progress log
- 2026-11-13: built; ruff, pyright, terraform fmt clean; tests written, not run.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-4726 | measurement design, plan guard semantics, relay-only lag metric and alarm | no |
