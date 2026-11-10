---
id: TASK-6505
title: "P-05-T04: expand-only migration 0760 — comment threads, events, thread comments, mentions, redactions, reads, to-dos, checklist items"
spec: SPEC-650
acceptance_criteria: [AC-1, AC-9, AC-10, AC-11, AC-13, AC-18, AC-22, AC-23, AC-26]
risk_zone: amber
status: in-review
branch: s33-p05-t04
worktree: /Users/ayushkbhatia/Accrued/abacus-s33
created: 2026-11-09
updated: 2026-11-09
plan_key: P-05-T04
---

## Objective
P-05 §4.2's eight tables, expand-only, so the S34 services have a schema.

## Plan (amber)
1. `migrations/versions/0760_collaboration_v2.py` on 0751: eight tables through `tenant_table()`
   (forced RLS, `tenant_isolation`, `archived_guard` where a table has `engagement_id`), insert
   column grants, column-level update grants, `collaboration_rows_immutable()` on the four
   insert-only tables (UPDATE, DELETE, TRUNCATE), `thread_comments_client_shared()` (a client
   author only on a shared thread), `actor_kind = 'human'` on thread events, no DELETE on threads,
   reads and to-dos (soft delete). One thread per anchor and locator key (`NULLS NOT DISTINCT`,
   per version only under `pin`).
2. `collaboration/registry.py`: TABLES, INSERT_ONLY, INSERT_COLUMNS, UPDATE_COLUMNS.
3. `tests/security/test_tenant_isolation.py`: the eight tables.
Rollback: downgrade drops the eight tables and two functions; nothing else changed. Re-chain onto
main's head at merge (migration-heads rule).

## Progress log
- `2026-11-09` — Written; up/down/up and the app-role refusals run at the S33 end pass.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-3105 | Migration shape choices the epic left open | no |
