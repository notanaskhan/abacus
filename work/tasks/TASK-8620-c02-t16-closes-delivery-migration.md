---
id: TASK-8620
title: "C-02-T16: Migration 0965 closes_delivery"
spec: SPEC-701
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
branch: c02-t16-closes-delivery-migration
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-18
updated: 2026-11-18
plan_key: C-02-T16
---

## Objective
Spec section: docs/plan/epics/C-02.md §4.2 NNNN_closes_delivery. close_deliverables with insert-only versions, close_reopenings, insert-only tax_handoffs; closes/registry.py.

## Plan (amber)
1. migrations/versions/0965_closes_delivery.py on 0964: four closes tables with forced RLS; versions, reopenings and hand-offs insert-only; reopenings and hand-offs human-only; one deliverable per close.
2. tax_handoffs: a newer row names supersedes_id; the AFTER INSERT trigger tax_handoffs_supersede sets the older row's superseded_by_id once under a transaction-local flag, the only update the immutability trigger allows.
3. closes/registry.py and schema_check IMMUTABLE_TABLES.
4. Rollback: downgrade drops the tables and functions.

## Progress log
- `2026-11-18` — Built in the S50 sequential stack (DEC-5620). Partial: the CAS statement-line catalogue loads as template content through the methodology import endpoint (never in a migration); its import file and the retention record-type rows are database content, loaded with the package service (C-02-T19). Gates and tests run once at the S50 end pass (build first, test last).
