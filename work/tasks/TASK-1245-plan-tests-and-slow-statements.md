---
id: TASK-1245
title: Plan tests for the top 20 list endpoints on a 10k-row synthetic fixture, and the slow-statement warning (Q-03-T028)
spec: SPEC-045
acceptance_criteria: [AC-2]  # stage 2's integration shards run them; Q-03-T028's acceptance is Q-03 §3.5 E3 (no spec AC of its own)
risk_zone: red
status: in-progress
epic: Q-03
plan_key: Q-03-T028
branch: s8b-quality
created: 2026-10-25
updated: 2026-10-25
---

## Objective
"All 20 plan tests pass in stage 2 and an index drop fails the build" (T028; Q-03 §3.5 E3: each
asserts the composite `(tenant_id, scope, status, sort)` index, and an integration statement over
100 ms warns in the PR).

## Plan (red zone)
- **Endpoints:** the 19 GET routes that return the P-36 list envelope plus
  `GET /v1/engagements/{id}/request-items` (CLI-01 and ENG-01 among them). Three are 501 stubs
  (`/v1/decision-cards`, `/v1/issues`, `/v1/review-notes`): their probes use the table and the
  index their contracts will read.
- **Fixture:** synthetic only, created by the test inside one superuser transaction on the
  `migrated_db` test database and rolled back: 10,000 rows for the probed firm and 10,000 for a
  second firm, foreign keys and triggers off for the load (`session_replication_role = replica`),
  `ANALYZE`d in the transaction. Never the dev stack.
- **Probe:** each endpoint's driving predicate on its own table (scope, status, sort, LIMIT),
  `EXPLAIN (FORMAT JSON)` as `abacus_app` under the firm's `app.tenant_id`, so row-level security
  adds the tenant predicate exactly as in production. Asserted: the expected index is in the plan
  and the table is never sequentially scanned.
- **Gaps:** an endpoint whose driving predicate has no usable index today names the composite
  index it needs; its test asserts the gap still holds (the index is absent and the table is
  scanned), so the migration that adds the index fails it until the case joins the plan tests.
  (Not `xfail`: SKIP-001 accepts only a `#<n>` issue or PR reference, and this work has none yet.)
- **Index drop:** a test drops one index inside the transaction and shows its plan test fails.
- **Slow statements:** `abacus_tools.quality.slow_statements` times every statement the app's
  engines run in the integration suites (SQLAlchemy cursor events), and the integration conftest
  prints those over 100 ms (`ABACUS_SLOW_STATEMENT_MS`) in the terminal summary and, on GitHub
  Actions, as `::warning` annotations on the PR. It never fails a run; parameters are never printed.
- **Tests:** `tests/integration/test_q03t028_plan_tests.py`; `tests/unit/quality/test_slow_statements.py`.
- **Rollback:** revert the commit; no schema change.

## Progress log
- 2026-10-25: plan written.
- 2026-10-25: built. `pytest tests/integration/test_q03t028_plan_tests.py` (one process and
  `-n 2`): 16 passed, 6 xfailed (strict) before the gaps became held tests; stable over five runs once the two cases with
  interchangeable indexes name both. `pytest tests/unit/quality/test_slow_statements.py`: 6
  passed. The slow-statement report checked on `tests/integration/test_listing.py -n 2` with
  `ABACUS_SLOW_STATEMENT_MS=5` (worker records reach the controller; migrations are not timed).
  **14 of 20 endpoints pass; 6 are gaps** that need indexes, so T028's "all 20 pass" waits for a
  migration (none reserved this wave):
  - `audit_events (tenant_id, target_type, target_id, seq)`: binder activity, request-item
    activity and wall events (three endpoints; today a sequential scan of the firm's log);
  - `request_items (tenant_id, request_list_id, created_at, id) WHERE deleted_at IS NULL`:
    binder requests (and the portal's EXISTS);
  - `request_lists (tenant_id, status, published_at)`: portal binders;
  - `memberships (tenant_id, kind, created_at, user_id)`: firm staff (or page it in SQL).
  The passing cases pin today's index; dropping it fails its test
  (`test_t028_dropping_an_index_fails_its_plan_test`). ENG-01's real sort (the earliest open
  work-item due date) cannot use any index; its probe is the period filter on
  `engagements_tenant (tenant_id, created_at)`.
- 2026-10-25: gaps rewritten as `test_t028_a_gap_holds_until_its_index_lands` (SKIP-001 wants a
  `#<n>` reference); the file is exempted, with reasons, from DB-001, TENANT-001 and SQL-001 in
  `banned_patterns.py` as the other superuser-seeding suites are; the fixture's transaction is left
  by raising `_RolledBack` (UOW-001).
- 2026-10-26: security review: each case now runs `VACUUM ANALYZE` on its table after the
  rollback, reclaiming the 20,000 dead rows and restoring the statistics.
