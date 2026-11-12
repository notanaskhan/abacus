---
id: TASK-7615
title: P-02-T06 SearchIndexer, SearchReindexWorkflow, reindex CLI, drift check, recents purge, offboarding
plan_key: P-02-T06
spec: SPEC-000  # C15 v1, docs/contracts/c15-search.md; ADR-241
acceptance_criteria: [AC-1]  # a client rename reindexes dependants within 5 s p95; full reindex idempotent under replay; offboarding leaves no rows
risk_zone: red
status: in-review
branch: p02-t06-indexer
worktree: /Users/ayushkbhatia/Accrued/abacus-s40
created: 2026-11-12
updated: 2026-11-12
---

## Objective
The index's write side: an outbox consumer composed from the registered projections' triggers,
the batch-class reindex workflow with replay histories, the operator CLI, the nightly drift check,
the recents purge on deactivation and the offboarding purge.

## Plan
- `platform/search/store.py` (new, protected): upsert with `tsv` (A title · B identifiers · C
  related · D context, `simple`), delete, id pages, client pages, sample, count, stored hash,
  recents purge, tenant purge. Operational writes on `tenant_connection`, no audit (ADR-241
  decisions 3 and 8); UOW-001 and UOW-002 exempt this file only (`banned_patterns.py`).
- `platform/search/indexer.py` (new): `index_object` (build → scrub → check → upsert; None
  deletes; a refused document deletes the stale row), `SearchSubscriptions` (lazy, the
  `reporting.api` precedent), fan-out above 200 ids → `request_reindex` (audited
  `search_index.reindex_requested`, then the workflow), `membership.deactivated` → recents purge.
- `platform/search/scrub.py` (new): control and bidi characters removed, whitespace collapsed
  (P-02-T07 adds the PII detector).
- `platform/search/workflows.py`, `activities.py` (new): `SearchReindexWorkflow` (batch; pages of
  500; `search_index.reindex_completed`), `SearchDriftCheckWorkflow` (batch; 1 % per type, 1 to
  200 ids, mismatches reindexed, `abacus.search.drift`).
- `platform/search/spec.py`: optional `list_ids` lister on `SearchProjection` (additive).
- `platform/api.py`: subscriptions composed (`_Composed`), both workflows `batch`, the activities,
  the daily `search_drift:platform` schedule, `purge_search_index`, `search_index_object`,
  `search_request_reindex`.
- `abacus_tools/search.py` (CLI: reindex, index, drift, purge);
  `abacus_tools/workflows/record_search_reindex.py` (histories `search-reindex-v1-all`, `-ids`).
- Tests: `tests/unit/platform/test_p02t06_indexer.py`, `tests/integration/test_p02t06_search_store.py`,
  `tests/workflows/test_p02t06_search_reindex_replay.py`.
- Rollback: revert; the routes stay 501 and nothing reads the index until P-02-T08.

## Deviations (DEC-4612)
- The drift check is one platform Schedule over every firm (daily interval), not a Schedule per
  tenant at 02:30 CT: `PlatformSchedule` supports an interval or a weekly calendar only.
- The epic's `membership.revoked` is the audit action; the outbox event is `membership.deactivated`.
- Offboarding has no in-app event: `platform.api.purge_search_index` and `abacus_tools.search purge`
  are the hook the firm-exit runbook calls.

## Partial
- The replay histories are recorded at the end pass (`record_search_reindex`, needs the stack);
  the replay test fails until they are committed.
- The 5 s p95 rename acceptance needs P-02-T07's client builder and trigger; measured at the end pass.

## Progress log
- `2026-11-12` — Indexer, workflows, CLI and tests built (DEC-4612).
