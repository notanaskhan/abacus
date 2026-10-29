---
id: TASK-2302
title: Q-03-T114 load-test harness acceptance suite (catch-up lane 2027 Q2 part 2)
spec: SPEC-541
acceptance_criteria: [AC-1, AC-2, AC-3]
risk_zone: red
status: in-review
epic: Q-03
plan_key: Q-03-T114
branch: s18-q03-t114
worktree: /Users/ayushkbhatia/Accrued/abacus-s18
created: 2026-10-29
updated: 2026-10-29
---

## Objective
Acceptance tests for the load-test harness (Q-03-T035, T043) written from the plan rows and the
runbook: scenario loading, client-side percentiles, the x1 smoke's trend, and the deploy-lock and
no-hosted-build check.

## Plan
- Tests first: `backend/tests/unit/tools/test_q03t114_loadtest_independent.py` (no network, no
  database, no AWS; MockTransport API, stubbed deploy lock).
- Gap the suite found: the harness checked loopback targets and the environment but never the
  deploy lock or a hosted database setting (db_guard's docstring said `make loadtest` ran it; the
  Makefile target does not). Fix: `run.check_no_hosted_build()` applies `db_guard.violations()` and
  `db_guard.lock_holder()` in `main` before a run, not a dry run (dry runs send nothing, Q-03-T043).
  In-process rather than a Makefile prerequisite, so `python -m abacus_tools.loadtest.run` refuses
  too and `DRY_RUN=1` keeps working while a deploy runs.
- Docs: db_guard docstring corrected; runbook section 7 gains the refusal row.
- Second half of the row ("then N's red and amber work an epic deferred under its cut list"): under
  the solo amendment ADR-078's split is void and every red/amber task writes its AC suite first, so
  nothing is owed beyond this suite; recorded here, no further code.
- Rollback: revert the branch.

## Per AC
| AC | Evidence |
|---|---|
| AC-1 | `test_ac1_*`: profiles load by name and path, refusals, nearest-rank percentiles, smoke report per group (JSON + Markdown), Makefile wiring |
| AC-2 | `test_ac2_*`: held lock and hosted DB refuse before `_main`; dry run unaffected; free lock starts the run |
| AC-3 | `test_ac3_*`: x1 smoke reports → trend → quality report Ops row ok / breach with a results-only ticket |

## Progress log
- `2026-10-29` — suite written; guard added to `run.main`; db_guard docstring and runbook row. Tests not run yet: the S18 end review runs them (build first, test last).

## Handoff
- **Current state:** built, PR open, held for the S18 batch.
- **Exact next step:** end review: run `tests/unit/tools/test_q03t114_loadtest_independent.py`, `test_loadtest.py` and `test_q03t043_scenarios_and_trend.py`.
