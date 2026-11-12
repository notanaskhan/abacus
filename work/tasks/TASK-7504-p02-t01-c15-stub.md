---
id: TASK-7504
title: P-02-T01 C15 v1 contract stub (search)
plan_key: P-02-T01
spec: SPEC-000  # contract C15 v1, docs/contracts/c15-search.md; ADR-241
acceptance_criteria: [AC-1]  # stub merges dark with generated types, both flags off, no hidden_by_wall field
risk_zone: red
status: in-review
branch: p02-t01-c15-stub
worktree: /Users/ayushkbhatia/Accrued/abacus-s39
created: 2026-11-12
updated: 2026-11-12
---

## Objective
C15 v1 as a contract stub: the `SearchProjection` registration on the F-03 slot, Pydantic models
with classification tags, 501 stubs for `POST /v1/search` and `GET`/`POST /v1/search/recents`,
the two matrix actions, the two flags (default off), the contract doc.

## Plan
- `backend/src/abacus/modules/platform/search/` (new): `spec.py` (groups, scope kinds, data
  classes, `SearchProjection`, `SearchIndexDocument`, `RelatedParty`, fail-closed `register`,
  `check_document`, the v0 adapter `register_search_projection`), `contract.py` (models,
  `clean_query`), `errors.py` (`q_invalid`, `rate_limited`, `search_unavailable`), `routes.py`
  (three stubs: matrix 403, flag 404, then 501).
- `platform/api.py`: exports and `search_router` in `ROUTERS`. The v0 `register_search_projection`
  export now points at the adapter, so methodology's and notices' v0 calls are unchanged.
- `identity/routing.py`: `/v1/search` stays writable in read-only mode (a read sent as POST).
- Matrix `permission-matrix/platform.yaml`: `search.read`, `search_recent.record`; flags
  `feature-flags/platform.yaml`: `search.palette`, `search.agent_mode` (default false, expire
  2027-05-07 under DEC-137 like the P-10 flags). Regenerated `_matrix.py`, `actions.gen.ts`,
  `_flags.py` and the generated security tests.
- `docs/contracts/c15-search.md`.
- Test `backend/tests/unit/platform/test_p02t01_search_stub.py`.
- Rollback: revert the PR; nothing reads the routes and both flags are off.

## Deviations (DEC-4504)
- `search.recent.record` → `search_recent.record`: the matrix requires `entity.verb`.
- Flag off answers 404 named after the flag, the repository's answer on every route, not the
  epic's 403 `flag_off`.
- `POST /v1/search/recents` answers 200 `SearchRecentRecordedOut` (identifiers), not 204: every
  `AbacusRouter` route declares a response model and no route on `main` answers 204.
- The v1 document type is `SearchIndexDocument`, so the v0 `SearchDocument` keeps its name for the
  adapter sprint.

## Partial
- ADR-241 is proposed; the epic wants it accepted before this merges. Ayush's call at the batch.
- `make generate` (the API client) runs once at the end pass for every S39 contract change.

## Progress log
- `2026-11-12` — Stub built (DEC-4504). Tests run at the S39 end pass.
