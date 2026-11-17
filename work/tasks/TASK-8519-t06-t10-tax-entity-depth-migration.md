---
id: TASK-8519
title: "T-06-T10: Migration 0952 tax_entity_depth"
spec: SPEC-702
acceptance_criteria: [AC-1, AC-7, AC-12, AC-16]
risk_zone: amber
status: in-review
branch: t06-t10-tax-entity-depth-migration
worktree: /Users/ayushkbhatia/Accrued/abacus-s49
created: 2026-11-17
updated: 2026-11-17
plan_key: T-06-T10
---

## Objective
Spec section: docs/plan/epics/T-06.md §4.2. Migration NNNN_tax_entity_depth (expand-only): tax_properties, fixed_assets with insert-only fixed_asset_versions and fixed_asset_dispositions, book_tax_items, basis_schedules, liability_shares, state_apportionments, sourcing_positions, ptet_elections, insert-only ptet_payments, ptet_partner_credits, nexus_facts; forced RLS, TRI, crossfoot and (a)+(b)+(c)=(d) CHECKs.

## Plan (amber)
1. `backend/migrations/versions/0952_tax_entity_depth.py` (on 0951): thirteen tables on the return's work item (FKs to work_items and tax_returns), forced RLS, column grants derived from the table bodies, immutable triggers on the three insert-only tables.
2. CHECKs: fixed_assets_crossfoot (accum_eop = accum_bop + current_year), real property SL/MM, book_tax_items_foot ((a)+(b)+(c)=(d)), basis difference = outside − inside and status matching it, share 0–100, a half-up credit needs its override reason; engine fields on engine outputs.
3. tax/registry.py tables and grants; schema_check IMMUTABLE_TABLES.
4. Tests in tests/integration/test_s49_migrations.py (up/down/up, a non-crossfooting asset and a non-footing M-3 row refused).
5. Rollback: downgrade drops the tables.

## Progress log
- `2026-11-17` — Built in the S49 sequential stack (DEC-5519). Ruff clean; applied at the end pass. Gates and tests run once at the S49 end pass (build first, test last).
