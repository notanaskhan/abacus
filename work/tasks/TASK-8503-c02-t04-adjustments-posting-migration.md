---
id: TASK-8503
title: "C-02-T04: Migration 0950 adjustments_posting"
spec: SPEC-700
acceptance_criteria: [AC-2, AC-15, AC-18, AC-19]
risk_zone: red
status: in-review
branch: c02-t04-adjustments-posting-migration
worktree: /Users/ayushkbhatia/Accrued/abacus-s49
created: 2026-11-17
updated: 2026-11-17
plan_key: C-02-T04
---

## Objective
Spec section: docs/plan/epics/C-02.md §4.2. Migration NNNN_adjustments_posting (expand-only): posting_batches, insert-only posting_results, closing_date_events, closing_date_conflicts; proposed_entries posting columns; posting CHECK widened NOT VALID then VALIDATE keeping A-09's elimination clause; decision codes approval_withdrawn, approval_undone, recorded_externally.

## Plan (red)
1. `backend/migrations/versions/0950_adjustments_posting.py` (on 0947): four tables with forced RLS and column grants; posting_results and closing_date_events insert-only with immutable triggers; posting_batches forward-only status trigger and an insert trigger binding the poster to the session's human actor (a column CHECK would refuse the workflow's later status moves); unique (work_item, batch_code) and idempotency key; one open conflict per entry.
2. proposed_entries: posting_batch_id (FK), external_txn_ref, txn_date, reverses_on, reversal_of_id, recorded_externally_* ; status + recorded_externally (evidence or match ref required); posting_target gains client_ledger (aje/rje/paje only); pe_posting_dormant widened, NOT VALID then VALIDATE, A-09's clause verbatim plus client_ledger AND NOT is_attest_client AND posting_batch_id IS NOT NULL; pe_tje_never_batched.
3. proposed_entry_decisions decision CHECK + approval_withdrawn, approval_undone, recorded_externally; approval_batches + approver_role, class_limits_snapshot.
4. adjustments/registry.py tables and column grants; schema_check IMMUTABLE_TABLES.
5. Tests: tests/integration/test_s49_migrations.py (all S49 migrations, written with the T-06 migrations) and the CHECK cases.
6. Rollback: downgrade restores 0896's constraints (client-ledger rows back to approved, target cleared) and drops the tables.

## Progress log
- `2026-11-17` — Built in the S49 sequential stack (DEC-5503). Ruff clean. Not applied yet: the up/down/up run is in the end pass. Gates and tests run once at the S49 end pass (build first, test last).
