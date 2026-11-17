---
id: TASK-8520
title: "T-06-T11: Migration 0953 ledger_tb_handoffs"
spec: SPEC-702
acceptance_criteria: [AC-29, AC-30]
risk_zone: red
status: in-review
branch: t06-t11-tb-handoffs-migration
worktree: /Users/ayushkbhatia/Accrued/abacus-s49
created: 2026-11-17
updated: 2026-11-17
plan_key: T-06-T11
---

## Objective
Spec section: docs/plan/epics/T-06.md §4.2. Migration NNNN_ledger_tb_handoffs (expand-only): insert-only tb_handoffs, tb_handoff_supersessions, tb_handoff_account_choices, tb_handoff_schedules and tb_handoff_tax_items; human-only CHECK bound to the app.actor GUCs; one current version per target.

## Plan (red)
1. `backend/migrations/versions/0953_ledger_tb_handoffs.py` (on 0952): tb_handoffs (source kind, source engagement/work item, FK to ledger_snapshots, target tax return, version_no unique per target, preview hash, book income and counts, handed_off_by bound to app.actor_id, actor_kind human bound to app.actor_kind); four insert-only children (one supersession per version; blank choices carry no code, suggested choices name their suggestion; schedules once per kind).
2. Every table insert-only with an immutable trigger; ledger/registry.py and schema_check.
3. Tests in tests/integration/test_s49_migrations.py: UPDATE and DELETE raise on each table; an insert as agent or system is refused.
4. Rollback: downgrade drops the five tables.

## Progress log
- `2026-11-17` — Built in the S49 sequential stack (DEC-5520). Ruff clean; applied at the end pass. Gates and tests run once at the S49 end pass (build first, test last).
