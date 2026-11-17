---
id: TASK-8504
title: "C-02-T05: Migration 0951 integrations_write_operations"
spec: SPEC-700
acceptance_criteria: [AC-15, AC-17, AC-21, AC-23]
risk_zone: red
status: in-review
branch: c02-t05-write-operations-migration
worktree: /Users/ayushkbhatia/Accrued/abacus-s49
created: 2026-11-17
updated: 2026-11-17
plan_key: C-02-T05
---

## Objective
Spec section: docs/plan/epics/C-02.md §4.2. Migration NNNN_integrations_write_operations (expand-only): ledger_write_operations with a unique idempotency key, insert-only ledger_write_evidence, connection_write_grants with revocation rows, firm_write_capabilities history, posting_enabled per engagement and connection; forced RLS.

## Plan (red)
1. `backend/migrations/versions/0951_integrations_write_operations.py` (on 0950): ledger_write_operations unique (tenant, capability, idempotency_key), human actor, the seven statuses; ledger_write_evidence, connection_write_grants and firm_write_capabilities insert-only with immutable triggers; a SECURITY DEFINER insert trigger refuses a grant for an attest-flagged client (clients.is_attest_client); firm switch rows bound to the session's human actor; connection_engagement_settings (C-01 never added it) with posting_enabled.
2. integrations/registry.py tables and column grants; schema_check DEFINER_FUNCTIONS and IMMUTABLE_TABLES.
3. Tests: tests/integration/test_s49_migrations.py (duplicate idempotency key refused; ledger_write_evidence UPDATE and DELETE refused; attest grant refused).
4. Rollback: downgrade drops the five tables and their functions.

## Progress log
- `2026-11-17` — Built in the S49 sequential stack (DEC-5504). Ruff clean; applied at the end pass. Gates and tests run once at the S49 end pass (build first, test last).
- `2026-11-17` — T-06-T03 found `write_operations` already owned by tax (0561, T-01-T25's W2 writes): the W1 tables are `ledger_write_operations` and `ledger_write_evidence` (DEC-5511).
