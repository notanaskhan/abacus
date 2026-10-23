---
id: TASK-952
title: Binders index read model behind GET /v1/binders (P-06-T11)
spec: SPEC-319
acceptance_criteria: [AC-10]
risk_zone: amber
status: done
epic: P-06
plan_key: P-06-T11
branch: TASK-952-binders-index
created: 2026-10-23
updated: 2026-10-23
---

## Objective
"A walled user's rows, tiles and totals exclude walled binders and no response field reveals a hidden count."

## Plan (amber: written before the code)
- **Files:**
  - `requests/binder_index.py` (new): filters, tiles, facets, sort, cursor and row facts.
  - `requests/repository.py`: `binder_index` (the one statement under `visible(binder.read)`), `binder_progress`, `touch_client_activity`.
  - `requests/models.py`: `BinderActivity`.
  - `requests/contract.py`: the live route and the additive `BinderRowOut` fields.
  - `requests/binders.py`: the mark-done projection touch and the public `unpublish_reason`.
  - `engagements/index_facts.py` (new): `work_item_index()`.
  - `organisations/repository.py`: `client_name_column`, `office_name_column`.
- **Migrations:** none. `binder_activity` (0100) already grants the projection columns. The activity summary needs columns: see *Deferred*.
- **Registry and flags:** none new. The route stays behind `binders.engine`.
- **Tests:**
  - `tests/integration/test_binders_index.py`: walls, team, tenant, flag, tiles, silence, filters, facets, row facts, tags, cursor, projection.
  - `tests/integration/test_binders_index_e0.py`: the E0 tiles foot to 241.
  - The C5 stub test lists the route as implemented. The A-01 consumer test names the new confidential field.
- **Rollback:** revert the commit. The route goes back to the 501 stub, and no schema changed.

## Decisions
DEC-151: service codes, the season rule, silence, sort, facets, and the last-activity gap.

## Deferred
- **Schema change, main session:** the BND-01 last-activity summary ("Claire emailed 2 files (Inbox) · uploading 2 now") and its INB-04 thread link. They need these `binder_activity` columns:
  - `last_client_activity_kind text NULL CHECK (last_client_activity_kind IN ('upload','answer','sign','email','mark_done'))`;
  - `last_client_actor_id uuid NULL`;
  - `last_client_file_count integer NULL CHECK (last_client_file_count >= 0)`;
  - `last_inbox_thread_id uuid NULL`.
  
  Each needs an `UPDATE` grant and an `INSERT` column in the registry. Then subscribers keep the projection on portal upload, answer, sign and `inbox_file.added`; today only the client's mark-done keeps it.
- The internal-draft line ("K-1 from Ridgeline · Draft K-1 · pre-release") has no source fact yet (K-1 packages, T-*).
- The named binders' "n of m" stay declared scenario data, except Feld (DEC-146), so live rows read their real counts.

## Progress log
- 2026-10-23: built.
  - 10 index tests and the E0 footing test pass against Postgres, as do the binder lifecycle suite, the unit, contract and route-introspection suites, `banned_patterns`, `lint-imports`, pyright, ruff and `make check-generated`.
  - No new `abacus__` schema names.
