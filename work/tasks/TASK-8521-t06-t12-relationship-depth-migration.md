---
id: TASK-8521
title: "T-06-T12: Migration 0954 relationship_depth and the S49 migration test"
spec: SPEC-702
acceptance_criteria: [AC-34, AC-35]
risk_zone: red
status: in-review
branch: t06-t12-relationship-depth-migration
worktree: /Users/ayushkbhatia/Accrued/abacus-s49
created: 2026-11-17
updated: 2026-11-17
plan_key: T-06-T12
---

## Objective
Spec section: docs/plan/epics/T-06.md §4.2. Migration NNNN_relationship_depth (organisations, expand-only): external_parties, entity_relationships additive columns with one-of CHECKs, insert-only entity_relationship_events, relationship_graph_layouts (per user, never audited), deferred trigger capping ownership at 100 percent.

## Plan (red)
1. `backend/migrations/versions/0954_relationship_depth.py` (on 0953): external_parties; entity_relationships gains external parties on either side (entity columns now nullable; exactly one of each side), source, note, end fields (ended with a reason), version; existing P-07 rows unchanged; a DEFERRABLE INITIALLY DEFERRED constraint trigger caps owner_of/gp_of/lp_of into one entity at 100 on every date an edge is in force; insert-only events bound to the human actor; per-user layouts bound to app.actor_id.
2. organisations/registry.py and schema_check.
3. `backend/tests/integration/test_s49_migrations.py`: 0950–0954 down to 0947 and up, forced RLS on 30 tables, insert-only grants and immutable triggers on 14, the posting, TJE, crossfoot, footing and one-of CHECKs, the guard triggers, single head 0954.
4. Rollback: downgrade drops the new tables and columns (external-party rows first).

## Progress log
- `2026-11-17` — Built in the S49 sequential stack (DEC-5521). Ruff clean; single head 0954. The ORM model's entity columns become optional with the service (T-06-T21). All migration tests run at the end pass. Gates and tests run once at the S49 end pass (build first, test last).
