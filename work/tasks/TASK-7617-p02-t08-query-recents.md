---
id: TASK-7617
title: P-02-T08 query and recents services live
plan_key: P-02-T08
spec: SPEC-000  # C15 v1, docs/contracts/c15-search.md; ADR-241
acceptance_criteria: [AC-1]  # SHL-02 a, d, e, f return the designed groups from the seed, p95 ≤ 250 ms locally, no field reflects a walled row
risk_zone: red
status: in-review
branch: p02-t08-query
worktree: /Users/ayushkbhatia/Accrued/abacus-s40
created: 2026-11-12
updated: 2026-11-12
---

## Objective
`POST /v1/search` and the recents routes served: per-group `visible()` by scope kind, the
`authorise()` post-filter for `tri` rows, ranking, match ranges, related-party context, the
visible-only suggestion, the capped `total_visible`, agent-mode browse, the rate limit, the 1 s
timeout, no search text in logs, traces or errors.

## Plan
- `platform/search/query.py` (new): the per-group statement (match: `simple` tsquery, trigram on
  title and related names, identifier prefix; 1–2 characters prefix only), rank, `SET LOCAL
  statement_timeout = '1s'` and the trigram threshold, the per-projection predicate
  (`visible_scope` for engagement, work item, client and entity kinds; the firm role minus walled
  clients for `firm`; the owner for `own`; anything else `false`), `tri` candidates
  (4 × limit) re-checked by `authorise()`, capped visible counts, the suggestion over visible
  non-`tri` documents only, the in-process budget (10 a second, burst 20; 429).
- `platform/search/recents.py` (new): read (re-filtered at read, `tri` re-authorised) and record
  (re-authorised, else 404; trimmed to 20 through `store.record_recent`).
- `platform/search/routes.py`: the three routes call the services (no 501); agent mode follows
  `search.agent_mode`.
- `tests/contracts/c15_search/test_c15_consumer.py`: `UNBUILT` empty (the routes are served).
- `docs/contracts/c15-search.md` status: live. `make generate`.
- Test `backend/tests/unit/platform/test_p02t08_query.py`; the AC suite is P-02-T09.
- Rollback: revert; `search.palette` is off.

## Deviations (DEC-4614)
- The rate limit is in-process per API worker (no shared limiter exists); the per-person bound is
  per worker, so a firm's actual budget is the worker count times 10 a second.
- The suggestion skips `tri` documents: a per-row consent check over a fuzzy candidate set would
  be unbounded.
- Agent mode browse answers no rows until an `agent_definition` projection registers (W-03).

## Partial
- p95 ≤ 250 ms on the seed is measured at the end pass (P-02-T13 owns the load test).

## Progress log
- `2026-11-12` — Query and recents built (DEC-4614). Tests run at the S40 end pass.
